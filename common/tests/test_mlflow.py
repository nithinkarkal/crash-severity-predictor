"""
Tests for MLflow helpers.
"""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, call, mock_open, patch

import pytest
from mlflow.exceptions import MlflowException

from common.utils.mlflow import (
    _log_named_artifact,
    load_registered_model,
    log_run,
    promote_if_better,
    register_model,
    setup_mlflow,
)


@patch("common.utils.mlflow.mlflow.set_experiment")
@patch("common.utils.mlflow.dagshub.init")
def test_setup_mlflow(
    mock_dagshub_init,
    mock_set_experiment,
) -> None:
    """setup_mlflow initializes DagsHub and selects the experiment."""

    setup_mlflow()

    mock_dagshub_init.assert_called_once_with(
        repo_owner="Rackkoun",
        repo_name="accident-severity-predictor",
        mlflow=True,
    )

    mock_set_experiment.assert_called_once_with("asp-training")


@patch("common.utils.mlflow.copy2")
@patch("common.utils.mlflow.mlflow.log_artifact")
def test_log_named_artifact(
    mock_log_artifact,
    mock_copy2,
) -> None:
    """_log_named_artifact copies a file to a temporary name before logging it."""

    source = Path("artifacts/models/features.json")

    _log_named_artifact(
        local_path=source,
        artifact_path="model",
        artifact_name="features.json",
    )

    mock_copy2.assert_called_once()

    copied_source = mock_copy2.call_args.args[0]
    copied_destination = Path(mock_copy2.call_args.args[1])

    assert copied_source == source
    assert copied_destination.name == "features.json"

    mock_log_artifact.assert_called_once()

    logged_path = Path(mock_log_artifact.call_args.args[0])

    assert logged_path.name == "features.json"
    assert mock_log_artifact.call_args.kwargs["artifact_path"] == "model"


@patch("mlflow.sklearn.log_model")
@patch("common.utils.mlflow._log_named_artifact")
@patch("common.utils.mlflow.mlflow.log_metrics")
@patch("common.utils.mlflow.mlflow.log_params")
@patch("common.utils.mlflow.mlflow.set_tag")
def test_log_run(
    mock_set_tag,
    mock_log_params,
    mock_log_metrics,
    mock_log_named_artifact,
    mock_log_model,
) -> None:
    """
    log_run logs tags, parameters, metrics, artifacts and the trained model.

    Note:
        _log_named_artifact() copies artifacts into a temporary directory before
        logging them, so the full local path is not deterministic. Therefore
        only the destination artifact path and filename are verified.
    """

    mock_model = MagicMock()
    mock_input_example = MagicMock()
    mock_model_info = MagicMock()
    mock_log_model.return_value = mock_model_info

    train_out: dict[str, Any] = {
        "model": mock_model,
        "model_name": "rf_20260730153000",
        "parameters": {
            "n_estimators": 100,
            "max_depth": 10,
        },
        "artifacts": {
            "model": Path("artifacts/models/model.joblib"),
            "parameters": Path("artifacts/models/parameters.json"),
            "features": Path("artifacts/models/features.json"),
            "feature_importance": Path("artifacts/reports/feature_importance.png"),
        },
        "input_example": mock_input_example,
    }

    eval_out: dict[str, Any] = {
        "metrics": {
            "accuracy": 0.95,
            "precision": 0.94,
            "recall": 0.93,
            "f1_score": 0.94,
        },
        "artifacts": {
            "confusion_matrix": Path("artifacts/reports/confusion_matrix.png"),
        },
    }

    result = log_run(train_out, eval_out)

    # Two tags are written:
    # - the timestamp as MLflow run name
    # - the original local model name
    mock_set_tag.assert_has_calls(
        [
            call("mlflow.runName", "20260730153000"),
            call("local_model_name", "rf_20260730153000"),
        ]
    )
    assert mock_set_tag.call_count == 2

    mock_log_params.assert_called_once_with(train_out["parameters"])

    mock_log_metrics.assert_called_once_with(eval_out["metrics"])

    # Three non-model artifacts should be logged.
    assert mock_log_named_artifact.call_count == 3

    mock_log_named_artifact.assert_has_calls(
        [
            call(
                local_path=train_out["artifacts"]["features"],
                artifact_path="model",
                artifact_name="features.json",
            ),
            call(
                local_path=train_out["artifacts"]["feature_importance"],
                artifact_path="reports",
                artifact_name="feature_importance.png",
            ),
            call(
                local_path=eval_out["artifacts"]["confusion_matrix"],
                artifact_path="reports",
                artifact_name="confusion_matrix.png",
            ),
        ]
    )

    mock_log_model.assert_called_once_with(
        sk_model=mock_model,
        artifact_path="model",
        input_example=mock_input_example,
    )

    assert result is mock_model_info


@patch("common.utils.mlflow.mlflow.register_model")
def test_register_model(mock_register_model) -> None:
    """register_model registers the logged model under the default registry."""

    mock_model_info = MagicMock()
    mock_model_info.model_uri = "runs:/abc123/model"

    mock_registered_version = MagicMock()
    mock_registered_version.version = "3"
    mock_register_model.return_value = mock_registered_version

    result = register_model(mock_model_info)

    mock_register_model.assert_called_once_with(
        model_uri="runs:/abc123/model",
        name="accident-severity-predictor",
    )

    assert result is mock_registered_version


@patch("common.utils.mlflow.mlflow.register_model")
def test_register_model_custom_name(mock_register_model) -> None:
    """register_model respects a custom registry name."""

    mock_model_info = MagicMock()
    mock_model_info.model_uri = "runs:/abc123/model"

    result = register_model(
        mock_model_info,
        registry_model_name="custom-model",
    )

    mock_register_model.assert_called_once_with(
        model_uri="runs:/abc123/model",
        name="custom-model",
    )

    assert result is mock_register_model.return_value


@patch("common.utils.mlflow.MlflowClient")
def test_promote_if_better_no_current_production(
    mock_mlflow_client_cls,
) -> None:
    """
    If no production model exists yet, the new version is promoted directly.
    """

    mock_client = MagicMock()
    mock_mlflow_client_cls.return_value = mock_client
    mock_client.get_model_version_by_alias.side_effect = MlflowException("not found")

    registered_version = MagicMock()
    registered_version.version = "1"

    eval_out = {"metrics": {"f1_score": 0.9}}

    result = promote_if_better(
        registered_version,
        eval_out,
    )

    assert result is True

    mock_client.get_model_version_by_alias.assert_called_once_with(
        "accident-severity-predictor",
        "production",
    )

    mock_client.set_registered_model_alias.assert_called_once_with(
        "accident-severity-predictor",
        "production",
        "1",
    )


@patch("common.utils.mlflow.MlflowClient")
def test_promote_if_better_new_version_is_better(
    mock_mlflow_client_cls,
) -> None:
    """
    A better model should:
      - move the current production model to the fallback alias
      - promote the new model to production
    """

    mock_client = MagicMock()
    mock_mlflow_client_cls.return_value = mock_client

    current_prod = MagicMock()
    current_prod.version = "2"
    current_prod.run_id = "run-2"

    mock_client.get_model_version_by_alias.return_value = current_prod

    current_run = MagicMock()
    current_run.data.metrics = {"f1_score": 0.85}
    mock_client.get_run.return_value = current_run

    registered_version = MagicMock()
    registered_version.version = "3"

    eval_out = {"metrics": {"f1_score": 0.9}}

    result = promote_if_better(
        registered_version,
        eval_out,
    )

    assert result is True

    mock_client.get_run.assert_called_once_with("run-2")

    mock_client.set_registered_model_alias.assert_has_calls(
        [
            call(
                "accident-severity-predictor",
                "fallback",
                "2",
            ),
            call(
                "accident-severity-predictor",
                "production",
                "3",
            ),
        ]
    )


@patch("common.utils.mlflow.MlflowClient")
def test_promote_if_better_new_version_is_worse(
    mock_mlflow_client_cls,
) -> None:
    """A worse model should not replace the current production model."""

    mock_client = MagicMock()
    mock_mlflow_client_cls.return_value = mock_client

    current_prod = MagicMock()
    current_prod.version = "2"
    current_prod.run_id = "run-2"

    mock_client.get_model_version_by_alias.return_value = current_prod

    current_run = MagicMock()
    current_run.data.metrics = {"f1_score": 0.95}
    mock_client.get_run.return_value = current_run

    registered_version = MagicMock()
    registered_version.version = "3"

    eval_out = {"metrics": {"f1_score": 0.9}}

    result = promote_if_better(
        registered_version,
        eval_out,
    )

    assert result is False
    mock_client.set_registered_model_alias.assert_not_called()


@patch("common.utils.mlflow.MlflowClient")
def test_promote_if_better_missing_current_metric(
    mock_mlflow_client_cls,
) -> None:
    """
    If the production model has no comparison metric, no promotion is performed.
    """

    mock_client = MagicMock()
    mock_mlflow_client_cls.return_value = mock_client

    current_prod = MagicMock()
    current_prod.version = "2"
    current_prod.run_id = "run-2"

    mock_client.get_model_version_by_alias.return_value = current_prod

    current_run = MagicMock()
    current_run.data.metrics = {}

    mock_client.get_run.return_value = current_run

    registered_version = MagicMock()
    registered_version.version = "3"

    eval_out = {"metrics": {"f1_score": 0.9}}

    result = promote_if_better(
        registered_version,
        eval_out,
    )

    assert result is False
    mock_client.set_registered_model_alias.assert_not_called()


@patch("common.utils.mlflow.MlflowClient")
def test_promote_if_better_lower_is_better(
    mock_mlflow_client_cls,
) -> None:
    """
    Metrics such as log_loss are better when their value is smaller.
    """

    mock_client = MagicMock()
    mock_mlflow_client_cls.return_value = mock_client

    current_prod = MagicMock()
    current_prod.version = "2"
    current_prod.run_id = "run-2"

    mock_client.get_model_version_by_alias.return_value = current_prod

    current_run = MagicMock()
    current_run.data.metrics = {"log_loss": 0.5}
    mock_client.get_run.return_value = current_run

    registered_version = MagicMock()
    registered_version.version = "3"

    eval_out = {"metrics": {"log_loss": 0.3}}

    result = promote_if_better(
        registered_version,
        eval_out,
        metric_name="log_loss",
        higher_is_better=False,
    )

    assert result is True

    mock_client.set_registered_model_alias.assert_has_calls(
        [
            call(
                "accident-severity-predictor",
                "fallback",
                "2",
            ),
            call(
                "accident-severity-predictor",
                "production",
                "3",
            ),
        ]
    )


@patch("common.utils.mlflow.json.load")
@patch("builtins.open", new_callable=mock_open)
@patch("common.utils.mlflow.mlflow.sklearn.load_model")
@patch("common.utils.mlflow.MlflowClient")
def test_load_registered_model(
    mock_client_cls,
    mock_load_model,
    mock_file,
    mock_json_load,
) -> None:
    """
    load_registered_model should return the model, feature list and metadata
    from the production alias.
    """

    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    version = MagicMock()
    version.version = "4"
    version.run_id = "run-123"

    mock_client.get_model_version_by_alias.return_value = version
    mock_client.download_artifacts.return_value = "/tmp/features.json"

    model = MagicMock()
    mock_load_model.return_value = model

    mock_json_load.return_value = [
        "age",
        "speed",
    ]

    result = load_registered_model()

    mock_client.get_model_version_by_alias.assert_called_once_with(
        "accident-severity-predictor",
        "production",
    )

    mock_load_model.assert_called_once_with("models:/accident-severity-predictor@production")

    mock_client.download_artifacts.assert_called_once()

    assert result == {
        "model": model,
        "features": ["age", "speed"],
        "version": "4",
        "run_id": "run-123",
    }


@patch("common.utils.mlflow.MlflowClient")
def test_load_registered_model_missing_alias(
    mock_client_cls,
) -> None:
    """
    A RuntimeError should be raised when the requested alias does not exist.
    """

    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    mock_client.get_model_version_by_alias.side_effect = MlflowException("not found")

    with pytest.raises(RuntimeError):
        load_registered_model()
