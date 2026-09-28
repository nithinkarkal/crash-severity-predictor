"""
evaluate model
"""

import json
from pathlib import Path

import joblib
import matplotlib
import matplotlib.pyplot as plt
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
)

from common.data.dataset_io import load_processed_csv
from common.utils.asp_logging import get_logger

matplotlib.use("Agg")

logger = get_logger(__name__)


def _latest_model_path(model_dir: Path, model_name: str) -> Path:
    """return the latest version of a trained model."""

    files = list(model_dir.glob(f"{model_name}_*.joblib"))

    if not files:
        raise FileNotFoundError(f"No trained model found for '{model_name}_*.joblib'")

    return max(files, key=lambda p: p.stat().st_mtime)


def run_evaluation(
    model_name: str,
    processed_data_dir: str | Path,
    model_dir: str | Path,
    metrics_dir: str | Path,
    reports_dir: str | Path,
) -> dict:
    """evaluate a trained model on the test set and save metrics + confusion matrix. Return the metrics dict."""

    model_dir = Path(model_dir)
    # create metrics dir if not exists
    metrics_dir = Path(metrics_dir)
    metrics_dir.mkdir(parents=True, exist_ok=True)

    model_path = _latest_model_path(model_dir, model_name)

    logger.info(f"Loading model: {model_path}")
    model = joblib.load(model_path)

    # Extract actual model name from filename for outputs
    actual_model_name = model_path.stem
    logger.info(f"Evaluating model: {actual_model_name}")
    processed_data_dir = Path(processed_data_dir)

    logger.info("Loading test dataset...")
    X_test = load_processed_csv(processed_data_dir / "X_test.csv")
    y_test = load_processed_csv(processed_data_dir / "y_test.csv").squeeze()

    logger.info("Running predictions...")
    y_pred = model.predict(X_test)

    metrics = {
        "accuracy": accuracy_score(y_test, y_pred),
        "precision": precision_score(y_test, y_pred),
        "recall": recall_score(y_test, y_pred),
        "f1_score": f1_score(y_test, y_pred),
    }

    logger.info(
        "Evaluation completed | "
        f"Accuracy={metrics['accuracy']:.4f} | "
        f"Precision={metrics['precision']:.4f} | "
        f"Recall={metrics['recall']:.4f} | "
        f"F1={metrics['f1_score']:.4f}"
    )

    metrics_path = Path(metrics_dir) / f"{actual_model_name}_metrics.json"

    logger.info("Saving metrics...")
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=4)

    fig, ax = plt.subplots(figsize=(6, 6))
    ConfusionMatrixDisplay.from_predictions(
        y_test,
        y_pred,
        cmap="Blues",
        normalize="true",
        ax=ax,
        colorbar=False,
    )
    plt.tight_layout()

    confusion_matrix_path = Path(reports_dir) / f"{actual_model_name}_confusion_matrix.png"

    logger.info("Generating confusion matrix...")
    plt.savefig(confusion_matrix_path, dpi=300)
    plt.close(fig)

    logger.info("Evaluation completed.")
    return {
        "metrics": metrics,
        "artifacts": {
            "confusion_matrix": confusion_matrix_path,
        },
    }
