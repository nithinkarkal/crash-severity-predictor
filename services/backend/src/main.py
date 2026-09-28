"""
Backend service entrypoint with model lifecycle management.
"""

import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from starlette.responses import Response

from common.utils.asp_logging import get_logger
from services.backend.src.core.metrics import http_request_duration_seconds, http_requests_total
from services.backend.src.routes import auth, health, metrics, predict, reload, train
from services.backend.src.services.prediction_service import load_model

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[Any]:
    """load latest model on startup if available."""
    try:
        load_model()
    except Exception as e:
        logger.exception(f"Unable to load model at startup: {e}")
    yield
    logger.info("Shutting down backend...")


app = FastAPI(
    title="Accident Severity Predictor API",
    description="""
    ML API for predicting French road accident severity (BAAC dataset).

    Endpoints:
    - **POST /api/v1/login** — Authenticate and get access token
    - **POST /api/v1/train** — Trigger model training (launches Docker container)
    - **POST /api/v1/predict** — Predict severity from accident features
    - **POST /api/v1/model/reload** — Reload the current 'production' model (used after retraining promotes a new champion)
    - **GET /api/v1/health** — Check service and model status
    - **GET /metrics** — Prometheus metrics (internal network only, not exposed via nginx)
    """,
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(auth.router)
app.include_router(health.router)
app.include_router(train.router)
app.include_router(predict.router)
app.include_router(reload.router)
app.include_router(metrics.router)


@app.middleware("http")
async def prometheus_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    if request.url.path == "/metrics":
        return await call_next(request)

    start = time.perf_counter()
    status_code = 500  # assume failure unless call_next succeeds
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        duration = time.perf_counter() - start
        route = request.scope.get("route")
        path = route.path if route else "unmatched"
        http_requests_total.labels(method=request.method, path=path, status_code=status_code).inc()
        http_request_duration_seconds.labels(method=request.method, path=path).observe(duration)


@app.get("/")
async def root() -> dict:
    return {
        "message": "Accident Severity Predictor API",
        "docs": "/docs",
        "auth": "/api/v1/login",
        "health": "/api/v1/health",
        "train": "/api/v1/train",
        "predict": "/api/v1/predict",
        "reload": "/api/v1/model/reload",
    }
