"""
Backend prediction service.

Loads a registered model from the MLflow Model Registry
and makes predictions on incoming requests.
"""

import json
import time
from typing import Any

import numpy as np
import pandas as pd
from fastapi import HTTPException

from common.utils.asp_logging import get_logger
from common.utils.mlflow import load_registered_model, setup_mlflow
from common.utils.paths import DATA_PROCESSING_CONFIG, METRIC_DIR, MODEL_CONFIG
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

# readable names for raw BAAC feature codes — used to phrase the plain-language summary
FEATURE_LABELS = {
    "place": "seating position",
    "catu": "road-user type",
    "sexe": "sex",
    "secu1": "safety equipment",
    "year_acc": "accident year",
    "victim_age": "victim age",
    "nb_victim": "number of casualties",
    "catv": "vehicle type",
    "obsm": "mobile obstacle hit",
    "motor": "engine type",
    "nb_vehicles": "vehicles involved",
    "catr": "road category",
    "circ": "traffic regime",
    "surf": "road surface",
    "situ": "location on road",
    "vma": "speed limit",
    "jour": "day of month",
    "mois": "month",
    "lum": "lighting conditions",
    "dep": "department",
    "com": "commune",
    "agg": "urban / rural area",
    "int": "intersection type",
    "atm": "weather",
    "col": "collision type",
    "lat": "latitude",
    "long": "longitude",
    "hour": "hour of day",
}


def _plain_language_summary(
    severity_code: int,
    probability: float | None,
    top_features: list[FeatureContribution],
    n: int = 3,
) -> str:
    """Turn the SHAP contributions into a short, human-readable sentence (no LLM).

    Example: "Likely a severe or fatal injury (83% confidence). Main factors increasing
    this risk: speed limit (vma=110), safety equipment (secu1=0). Factors lowering the
    risk: lighting conditions (lum=1)."
    """

    def phrase(fc: FeatureContribution) -> str:
        label = FEATURE_LABELS.get(fc.feature, fc.feature)
        value = int(fc.value) if float(fc.value).is_integer() else round(fc.value, 2)
        return f"{label} ({fc.feature}={value})"

    verdict = "Likely a severe or fatal injury" if severity_code == 1 else "Likely a light injury"
    confidence = f"{round(probability * 100)}% confidence" if probability is not None else "confidence unavailable"

    increasing = [phrase(f) for f in top_features if f.shap_value > 0][:n]
    lowering = [phrase(f) for f in top_features if f.shap_value < 0][:n]

    parts = [f"{verdict} ({confidence})."]
    if increasing:
        parts.append("Main factors increasing this risk: " + ", ".join(increasing) + ".")
    if lowering:
        parts.append("Factors lowering the risk: " + ", ".join(lowering) + ".")
    return " ".join(parts)


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


def _latest_training_metrics() -> tuple[dict[str, float], str]:
    """Read the most recent training metrics JSON from artifacts/metrics/ (local, no MLflow call).

    Returns (metrics, trained_at). Files are named model_<YYYYMMDDHHMMSS>_metrics.json, so the
    lexicographically last one is the newest run. Degrades to ({}, "unknown") on any problem.
    """
    try:
        files = sorted(METRIC_DIR.glob("model_*_metrics.json"))
        if not files:
            return {}, "unknown"

        latest = files[-1]
        raw = json.loads(latest.read_text())
        metrics = {str(k): float(v) for k, v in raw.items() if isinstance(v, (int, float))}

        trained_at = "unknown"
        for part in latest.stem.split("_"):
            if part.isdigit() and len(part) == 14:  # YYYYMMDDHHMMSS
                trained_at = f"{part[0:4]}-{part[4:6]}-{part[6:8]} {part[8:10]}:{part[10:12]}:{part[12:14]}"
                break

        return metrics, trained_at
    except Exception:
        logger.warning("Could not read training metrics from %s", METRIC_DIR)
        return {}, "unknown"


def get_model_info() -> dict[str, Any]:
    """Return metadata for the currently served model (for the /model/info endpoint).

    Uses the in-memory cache + project config, plus the model's own
    ``feature_importances_`` (RandomForest) — no MLflow round-trip required.
    """
    if _model_cache["model"] is None:
        load_model()

    model = _model_cache["model"]
    features = _model_cache["features"] or []
    name = _model_cache["name"] or ""
    alias = _model_cache["alias"] or "production"

    # cache name looks like "<registry>@<alias> (v<version>)" — pull the version out
    version = name.split("(v", 1)[1].rstrip(")") if "(v" in name else "unknown"

    # training window from config (all years except the held-out test year)
    years = DATA_PROCESSING_CONFIG.get("years", [])
    test_year = DATA_PROCESSING_CONFIG.get("exclusive_test_year")
    train_years = [y for y in years if y != test_year]
    dataset = f"BAAC {min(train_years)}-{max(train_years)}" if train_years else "BAAC"

    # per-feature importances straight from the RandomForest (real, no MLflow call)
    feature_importance: dict[str, float] = {}
    if model is not None and hasattr(model, "feature_importances_"):
        ranked = sorted(zip(features, model.feature_importances_, strict=False), key=lambda t: t[1], reverse=True)
        feature_importance = {str(f): round(float(v), 6) for f, v in ranked}

    metrics, trained_at = _latest_training_metrics()

    return {
        "registry_name": MODEL_CONFIG["model_registry_name"],
        "alias": alias,
        "version": str(version),
        "algorithm": type(model).__name__ if model is not None else "unknown",
        "trained_at": trained_at,
        "dataset": dataset,
        "features_count": len(features),
        "metrics": metrics,
        "parameters": dict(MODEL_CONFIG.get("model_parameters", {})),
        "feature_importance": feature_importance,
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

    summary = _plain_language_summary(prediction, probability, top_features)

    return ExplanationResponse(
        severity=SEVERITY_MAP.get(prediction, "Unknown"),
        severity_code=prediction,
        probability=probability,
        base_value=base_value,
        summary=summary,
        top_features=top_features,
        model_used=model_name or "unknown",
    )
