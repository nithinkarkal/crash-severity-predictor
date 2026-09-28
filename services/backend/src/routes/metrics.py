from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from services.backend.src.core.metrics import REGISTRY, refresh_drift_metrics
from services.backend.src.services.prediction_service import get_model_status

router = APIRouter(tags=["Monitoring"])


@router.get("/metrics")
def metrics() -> Response:
    """Expose all Prometheus metrics for scraping. Deliberately outside /api/v1
    and without auth, so Prometheus can scrape it without a bearer token."""
    status = get_model_status()
    model_version = status["name"] or "unknown"
    refresh_drift_metrics(model_version)
    return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)
