"""
Backend prediction service.

Loads a registered model from the MLflow Model Registry
and makes predictions on incoming requests.
"""

import time

import pandas as pd
from fastapi import HTTPException

from common.utils.asp_logging import get_logger
from common.utils.mlflow import load_registered_model, setup_mlflow
from common.utils.paths import MODEL_CONFIG
from services.backend.src.core.metrics import model_loaded, prediction_confidence, prediction_duration_seconds, predictions_total
from services.backend.src.schemas.prediction import PredictionRequest, PredictionResponse

logger = get_logger(__name__)

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

    # build DataFrame from request - alias "int" instead of "int_"
    input_data = request.model_dump(by_alias=True)

    # id_usager appears in exported features...
    # add id_usager if missing (model expects it but it's an internal ID)
    if "id_usager" in features and "id_usager" not in input_data:
        input_data["id_usager"] = 0  # placeholder, not used for prediction

    df = pd.DataFrame([input_data])

    # ensure correct column order and presence
    try:
        df = df[features]
    except KeyError as exc:
        missing = set(features) - set(input_data.keys())
        extra = set(input_data.keys()) - set(features)
        logger.error(f"Feature mismatch. Missing: {missing}, Extra: {extra}")
        raise HTTPException(
            status_code=422,
            detail=f"Feature mismatch with trained model. Missing: {missing}, Extra: {extra}",
        ) from exc

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

    severity_map = {
        0: "Unharmed / Lightly injured",
        1: "Injured (hospitalized) / Killed",
    }

    return PredictionResponse(
        severity=severity_map.get(prediction, "Unknown"),
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
