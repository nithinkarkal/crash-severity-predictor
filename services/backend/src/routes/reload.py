"""
Backend model-reload endpoint.

Lets an external caller — specifically the Airflow retraining DAG's `reload_fastapi`
step — tell the *running* API to drop its cached model and reload the current
'production' model from the MLflow registry. This is what makes a newly promoted
champion go live immediately, without restarting the backend.

Why it's needed: the API loads the 'production' model into an in-memory cache once
(on startup / first request) and never re-checks. When the retraining pipeline
promotes a new model (changes the registry 'production' alias), a long-running API
keeps serving the OLD cached model until it is told to reload — which is exactly
what this endpoint does (it reuses the existing `load_model(force_reload=True)`).
"""

from fastapi import APIRouter, HTTPException

from common.utils.asp_logging import get_logger
from services.backend.src.core.metrics import model_reload_total
from services.backend.src.services.prediction_service import get_model_status, load_model

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Model"])


@router.post("/model/reload")
def reload_model() -> dict:
    """Force-reload the current 'production' model from the MLflow registry.

    Called after the retraining pipeline promotes a new champion, so the live API
    serves it without a restart. Returns the loaded-model status. If loading fails
    (no model / registry unreachable), `load_model` raises an HTTP 503.
    """
    logger.info("Reload requested: force-reloading the 'production' model...")
    try:
        load_model(force_reload=True)
    except HTTPException:  # reuses the existing loader; raises HTTP 503 on failure
        model_reload_total.labels(status="failure").inc()
        raise
    model_reload_total.labels(status="success").inc()

    status = get_model_status()
    logger.info(f"Reload complete: now serving {status['name']}")
    return {"status": "reloaded", "model": status}
