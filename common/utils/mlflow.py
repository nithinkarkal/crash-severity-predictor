"""
mlflow tracking setup, run logging & model registry
"""

import json
from pathlib import Path
from shutil import copy2
from tempfile import TemporaryDirectory
from typing import Any, cast

import dagshub
import mlflow
from mlflow import MlflowClient
from mlflow.entities.model_registry import ModelVersion

from common.utils.asp_logging import get_logger

logger = get_logger(__name__)


def _log_named_artifact(
    local_path: Path,
    artifact_path: str,
    artifact_name: str,
) -> None:
    """log a local file to mlflow with a specific artifact name."""
    with TemporaryDirectory() as tmpdir:
        renamed = Path(tmpdir) / artifact_name
        copy2(local_path, renamed)

        mlflow.log_artifact(
            str(renamed),
            artifact_path=artifact_path,
        )


def setup_mlflow(
    experiment_name: str = "asp-training",
) -> None:
    """setup mlflow for dagshub."""

    logger.info("Initializing DagsHub MLflow tracking...")

    # Increase HTTP timeout
    dagshub.common.config.http_timeout = 300

    dagshub.init(
        repo_owner="Rackkoun",
        repo_name="accident-severity-predictor",
        mlflow=True,
    )

    logger.info(f"Using MLflow experiment '{experiment_name}'")
    mlflow.set_experiment(experiment_name)


def log_run(
    train_out: dict[str, Any],
    eval_out: dict[str, Any],
) -> mlflow.models.model.ModelInfo:
    """log training and evaluation outputs, including the model artifact."""

    logger.info("Logging parameters, metrics and artifacts to MLflow...")

    # Set run name to the timestamped part of the model name (e.g. model_20260722125017 -> 20260722125017)
    mlflow.set_tag("mlflow.runName", train_out["model_name"].rsplit("_", 1)[1])

    mlflow.set_tag("local_model_name", train_out["model_name"])
    mlflow.log_params(train_out["parameters"])
    mlflow.log_metrics(eval_out["metrics"])

    _log_named_artifact(
        local_path=train_out["artifacts"]["features"],
        artifact_path="model",
        artifact_name="features.json",
    )

    _log_named_artifact(
        local_path=train_out["artifacts"]["feature_importance"],
        artifact_path="reports",
        artifact_name="feature_importance.png",
    )

    _log_named_artifact(
        local_path=eval_out["artifacts"]["confusion_matrix"],
        artifact_path="reports",
        artifact_name="confusion_matrix.png",
    )

    model_info = cast(
        mlflow.models.model.ModelInfo,
        mlflow.sklearn.log_model(
            sk_model=train_out["model"],
            artifact_path="model",
            input_example=train_out["input_example"],
        ),
    )

    logger.info("MLflow logging completed.")
    return model_info


def register_model(
    model_info: mlflow.models.model.ModelInfo,
    registry_model_name: str = "accident-severity-predictor",
) -> ModelVersion:
    """register an already-logged model in the MLflow Model Registry."""

    logger.info(f"Registering model at '{model_info.model_uri}' as '{registry_model_name}'...")

    registered_version = mlflow.register_model(
        model_uri=model_info.model_uri,
        name=registry_model_name,
    )

    logger.info(f"Model registered as '{registry_model_name}' version {registered_version.version}.")
    return registered_version


def promote_if_better(
    registered_version: ModelVersion,
    eval_out: dict[str, Any],
    registry_model_name: str = "accident-severity-predictor",
    metric_name: str = "f1_score",
    higher_is_better: bool = True,
) -> bool:
    """
    Compare the newly registered model version against the current
    production version (by alias) on a given metric, and promote it
    if it performs better. Returns True if promotion happened.
    """

    logger.info("Comparing new model version against current production version...")

    prod_alias = "production"
    fallback_alias = "fallback"

    client = MlflowClient()
    new_metric = float(eval_out["metrics"][metric_name])

    try:
        current_prod = client.get_model_version_by_alias(registry_model_name, prod_alias)
    except mlflow.exceptions.MlflowException:
        current_prod = None

    if current_prod is None:
        logger.info(
            f"No current 'production' version found for '{registry_model_name}'. \
                    Promoting version {registered_version.version} by default."
        )
        client.set_registered_model_alias(
            registry_model_name,
            prod_alias,
            registered_version.version,
        )
        return True

    # pull the metric from the run that produced the current production version
    current_run = client.get_run(current_prod.run_id)
    current_metric = current_run.data.metrics.get(metric_name)

    if current_metric is None:
        logger.warning(
            f"Current '{prod_alias}' version (v{current_prod.version}) has no '{metric_name}' logged. Skipping comparison, keeping it in place."
        )
        return False
    current_metric = float(current_metric)

    is_better = new_metric > current_metric if higher_is_better else new_metric < current_metric

    logger.info(
        f"Comparing new version {registered_version.version} ({metric_name}={new_metric:.4f}) "
        f"against current '{prod_alias}' version {current_prod.version} ({metric_name}={current_metric:.4f})"
    )

    if is_better:
        # Set old model on fallback alias for safety, in case we need to roll back
        client.set_registered_model_alias(
            registry_model_name,
            fallback_alias,
            current_prod.version,
        )
        # Promote new model to production alias
        client.set_registered_model_alias(
            registry_model_name,
            prod_alias,
            registered_version.version,
        )

        logger.info(
            f"Version {registered_version.version} outperforms current '{prod_alias}' ({new_metric:.4f} vs {current_metric:.4f}). \
                Promoted new to '{prod_alias}' and set old to '{fallback_alias}'."
        )
    else:
        logger.info(
            f"Version {registered_version.version} does not outperform current '{prod_alias}'."
            f"({new_metric:.4f} vs {current_metric:.4f}). Keeping current version."
        )

    return is_better


def load_registered_model(
    registry_model_name: str = "accident-severity-predictor",
    alias: str = "production",
) -> dict[str, Any]:
    """
    Load a registered model and its feature list from the MLflow Model Registry.

    Returns:
        {
            "model": sklearn model,
            "features": list[str],
            "version": str,
            "run_id": str,
        }
    """

    logger.info(f"Loading model '{registry_model_name}' with alias '{alias}' from MLflow...")

    client = MlflowClient()

    try:
        version = client.get_model_version_by_alias(
            registry_model_name,
            alias,
        )
    except mlflow.exceptions.MlflowException as exc:
        raise RuntimeError(f"No model with alias '{alias}' found for '{registry_model_name}'.") from exc

    model_uri = f"models:/{registry_model_name}@{alias}"

    model = mlflow.sklearn.load_model(model_uri)

    with TemporaryDirectory() as tmpdir:
        local_feature_path = client.download_artifacts(
            run_id=version.run_id,
            path="model/features.json",
            dst_path=tmpdir,
        )

        with open(local_feature_path) as f:
            features = json.load(f)

    logger.info(f"Loaded model '{registry_model_name}' (v{version.version}, alias='{alias}') with {len(features)} features.")

    return {
        "model": model,
        "features": features,
        "version": version.version,
        "run_id": version.run_id,
    }
