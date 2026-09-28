"""
Backend prediction service.

Loads a registered model from the MLflow Model Registry
and makes predictions on incoming requests.
"""

import time

import numpy as np
import pandas as pd
from fastapi import HTTPException

from common.utils.asp_logging import get_logger
from common.utils.mlflow import load_registered_model, setup_mlflow
from common.utils.paths import MODEL_CONFIG
from services.backend.src.core.metrics import model_loaded, prediction_confidence, prediction_duration_seconds, predictions_total
from services.backend.src.schemas.prediction import (
    ExplanationResponse,
    FeatureContribution,
    PredictionRequest,
    PredictionResponse,
)

logger = get_logger(__name__)

# human-readable labels for the binary target (0 = light, 1 = severe/fatal)
SEVERITY_MAP = {
    0: "Unharmed / Lightly injured",
    1: "Injured (hospitalized) / Killed",
}

# in-memory cache for loaded model
_model_cache: dict = {
    "model": None,
    "features": None,
    "name": None,
    "alias": None,
}


def load_model(
    alias: str = "production",
    force_reload: bool = False,
) -> None:
    """
    Load a registered model from the MLflow Model Registry into cache.

    Args:
        alias:
            Model alias to load ("production" or "fallback").
        force_reload:
            Reload even if already cached.
    """

    global _model_cache

    if _model_cache["model"] is not None and _model_cache["alias"] == alias and not force_reload:
        logger.debug("Model already loaded, skipping.")
        return

    try:
        setup_mlflow()

        loaded = load_registered_model(
            registry_model_name=MODEL_CONFIG["model_registry_name"],
            alias=alias,
        )

        _model_cache["model"] = loaded["model"]
        _model_cache["features"] = loaded["features"]
        _model_cache["name"] = f"{MODEL_CONFIG['model_registry_name']}@{alias} (v{loaded['version']})"
        _model_cache["alias"] = alias
        logger.info(f"Loaded {_model_cache['name']} ({len(_model_cache['features'])} features)")
        model_loaded.labels(model_version=_model_cache["name"], alias=alias).set(1)

    except Exception as exc:
        logger.exception("Failed to load registered model.")
        model_loaded.labels(model_version="none", alias=alias).set(0)

        _model_cache = {
            "model": None,
            "features": None,
            "name": None,
            "alias": None,
        }

        raise HTTPException(
            status_code=503,
            detail=f"Unable to load model from MLflow registry: {exc}",
        ) from exc


def predict_accident(request: PredictionRequest) -> PredictionResponse:
    """make a severity prediction from input features.

    Args:
        request: Validated Pydantic model with all required features.

    Returns:
        PredictionResponse with severity label, code, and probability.

    Raises:
        HTTPException: If model is not loaded or prediction fails.
    """
    global _model_cache

    # lazy load model if not cached
    if _model_cache["model"] is None:
        load_model()

    model = _model_cache["model"]
    features = _model_cache["features"]
    model_name = _model_cache["name"]

    df = _build_input_frame(request, features)

    # predict
    start = time.perf_counter()
    prediction = int(model.predict(df)[0])

    # probability (RandomForest supports predict_proba)
    probability = None
    if hasattr(model, "predict_proba"):
        proba = model.predict_proba(df)[0]
        probability = float(proba[prediction])
    duration = time.perf_counter() - start

    predictions_total.labels(severity_code=str(prediction), model_version=model_name or "unknown").inc()
    prediction_duration_seconds.labels(model_version=model_name or "unknown").observe(duration)
    if probability is not None:
        prediction_confidence.labels(model_version=model_name or "unknown").observe(probability)

    return PredictionResponse(
        severity=SEVERITY_MAP.get(prediction, "Unknown"),
        severity_code=prediction,
        probability=probability,
        model_used=model_name or "unknown",
    )


def get_model_status() -> dict:
    """return current model loading status (for health checks)."""
    return {
        "loaded": _model_cache["model"] is not None,
        "name": _model_cache["name"],
        "alias": _model_cache["alias"],
        "features_count": len(_model_cache["features"]) if _model_cache["features"] else 0,
    }


def _build_input_frame(request: PredictionRequest, features: list[str]) -> pd.DataFrame:
    """Turn a validated request into a single-row DataFrame ordered like the model's features.

    Raises HTTPException(422) if the request columns don't match the trained model.
    """
    # alias "int" instead of "int_"
    input_data = request.model_dump(by_alias=True)

    # id_usager can appear in the exported feature list but is an internal ID, not a real
    # signal — add a harmless placeholder so column selection succeeds.
    if "id_usager" in features and "id_usager" not in input_data:
        input_data["id_usager"] = 0

    df = pd.DataFrame([input_data])
    try:
        return df[features]
    except KeyError as exc:
        missing = set(features) - set(input_data.keys())
        extra = set(input_data.keys()) - set(features)
        logger.error(f"Feature mismatch. Missing: {missing}, Extra: {extra}")
        raise HTTPException(
            status_code=422,
            detail=f"Feature mismatch with trained model. Missing: {missing}, Extra: {extra}",
        ) from exc


def _class_contributions(values: np.ndarray, base: np.ndarray, cls: int) -> tuple[np.ndarray, float]:
    """Extract the per-feature SHAP contributions + base value for one class, one sample.

    Handles the shapes modern SHAP returns for a binary tree classifier:
      values: (1, n_features, n_classes)  |  base: (1, n_classes)
    and degrades sensibly for single-output shapes.
    """
    values = np.asarray(values)
    base = np.asarray(base)

    if values.ndim == 3:  # (n_samples, n_features, n_classes)
        contribs = values[0, :, cls]
        base_value = float(base[0, cls] if base.ndim == 2 else base[cls])
    elif values.ndim == 2:  # (n_samples, n_features) — single output
        contribs = values[0]
        base_value = float(base[0] if base.ndim >= 1 else base)
    else:  # unexpected — flatten defensively
        contribs = np.ravel(values)
        base_value = float(np.ravel(base)[0]) if np.size(base) else 0.0

    return contribs, base_value


def explain_accident(request: PredictionRequest, top_n: int = 10) -> ExplanationResponse:
    """Explain a single prediction with per-feature SHAP contributions.

    Returns the predicted class plus the ``top_n`` features (by absolute SHAP value)
    that pushed the model toward that class, with the sign of each contribution.
    """
    global _model_cache

    if _model_cache["model"] is None:
        load_model()

    model = _model_cache["model"]
    features = _model_cache["features"]
    model_name = _model_cache["name"]

    df = _build_input_frame(request, features)

    prediction = int(model.predict(df)[0])
    probability = None
    if hasattr(model, "predict_proba"):
        probability = float(model.predict_proba(df)[0][prediction])

    # SHAP is imported lazily so the normal /predict path never pays for it.
    try:
        import shap

        explainer = shap.TreeExplainer(model)
        explanation = explainer(df)
        contribs, base_value = _class_contributions(explanation.values, explanation.base_values, prediction)
    except Exception as exc:
        logger.exception("SHAP explanation failed.")
        raise HTTPException(status_code=500, detail=f"Failed to compute explanation: {exc}") from exc

    # pair each feature with its value + contribution, then rank by |contribution|
    row_values = df.iloc[0].tolist()
    ranked = sorted(
        zip(features, contribs, row_values, strict=True),
        key=lambda item: abs(item[1]),
        reverse=True,
    )

    top_features = [
        FeatureContribution(
            feature=str(name),
            value=float(value),
            shap_value=float(shap_value),
            direction="increases" if shap_value >= 0 else "decreases",
        )
        for name, shap_value, value in ranked[:top_n]
    ]

    return ExplanationResponse(
        severity=SEVERITY_MAP.get(prediction, "Unknown"),
        severity_code=prediction,
        probability=probability,
        base_value=base_value,
        top_features=top_features,
        model_used=model_name or "unknown",
    )
