"""
Model training
"""

import json
from datetime import datetime
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from common.data.dataset_io import load_processed_csv
from common.utils.asp_logging import get_logger

logger = get_logger(__name__)


def _generate_model_name(base_name: str) -> str:
    """generate a timestamped model name: model -> model_20260722125017"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{base_name}_{timestamp}"


def _resolve_base_model_name(model_name: str, model_dir: Path) -> str:
    """
    if model_name is a full timestamped name (e.g. model_20260722125017),
    extract the base name. If no models exist, use model_name as-is.
    """
    # ff model_name contains underscore, it might be timestamped
    if "_" in model_name:
        # check if it's an existing model file
        existing = model_dir / f"{model_name}.joblib"
        if existing.exists():
            # extract base name (everything before last underscore)
            return model_name.rsplit("_", 1)[0]

    return model_name


def run_training(
    processed_data_dir: str | Path,
    model_out_dir: str | Path,
    reports_dir: str | Path,
    model_name: str,
    model_parameters: dict,
    top_n_features: int = 20,
) -> dict:
    """train RandomForest and save artifacts."""

    processed_data_dir = Path(processed_data_dir)
    model_out_dir = Path(model_out_dir)

    logger.info("Loading processed training dataset...")
    X_train = load_processed_csv(processed_data_dir / "X_train.csv")
    y_train = load_processed_csv(processed_data_dir / "y_train.csv").squeeze()

    model = RandomForestClassifier(**model_parameters)

    logger.info("Training RandomForest model...")
    model.fit(X_train, y_train)

    # resolve base name (handle timestamped input names)
    base_name = _resolve_base_model_name(model_name, model_out_dir)
    final_model_name = _generate_model_name(base_name)

    logger.info(f"Saving model as '{final_model_name}' (base: {base_name})")

    artifact_paths = save_model_artifacts(
        model=model,
        features=list(X_train.columns),
        model_parameters=model_parameters,
        reports_dir=reports_dir,
        model_out_dir=model_out_dir,
        model_name=final_model_name,
        top_n_features=top_n_features,
    )

    logger.info("Training completed.")
    return {
        "model": model,
        "model_name": final_model_name,
        "parameters": model_parameters,
        "artifacts": artifact_paths,
        "input_example": X_train.iloc[:5],
    }


def save_model_artifacts(
    model: RandomForestClassifier,
    features: list[str],
    model_parameters: dict,
    model_out_dir: str | Path,
    reports_dir: str | Path,
    model_name: str,
    top_n_features: int = 20,
) -> dict[str, Path]:
    """save model, features list, parameters and a feature-importance plot. Return the output paths."""

    model_out_dir = Path(model_out_dir)
    reports_dir = Path(reports_dir)

    model_out_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    model_path = model_out_dir / f"{model_name}.joblib"
    features_path = model_out_dir / f"{model_name}_features.json"
    params_path = model_out_dir / f"{model_name}_parameters.json"
    importance_path = reports_dir / f"{model_name}_feature_importance.png"

    logger.info(f"Saving model: {model_path}")
    joblib.dump(model, model_path)

    logger.info(f"Saving features: {features_path}")
    with open(features_path, "w") as f:
        json.dump(features, f, indent=4)

    with open(params_path, "w") as f:
        json.dump(model_parameters, f, indent=4)

    feature_importance = (
        pd.Series(model.feature_importances_, index=features).sort_values(ascending=False).head(top_n_features).sort_values(ascending=True)
    )
    fig, ax = plt.subplots(figsize=(8, max(4, len(feature_importance) * 0.3)))
    feature_importance.plot.barh(ax=ax)
    ax.set_title(f"{model_name} - Feature Importance")
    ax.set_xlabel("Importance")
    plt.tight_layout()

    logger.info(f"Saving feature importance plot: {importance_path}")
    plt.savefig(importance_path, dpi=300)
    plt.close(fig)

    return {
        "model": model_path,
        "features": features_path,
        "parameters": params_path,
        "feature_importance": importance_path,
    }
