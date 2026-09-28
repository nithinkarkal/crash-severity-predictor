"""
Tests for Prometheus middleware and startup/lifespan behavior of the backend.
"""

import asyncio
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.backend.src import main
from services.backend.src.core.metrics import REGISTRY


def _counter_value(
    method: str,
    path: str,
    status_code: int,
) -> float:
    """Return the current HTTP request counter value."""

    samples = REGISTRY.get_sample_value(
        "http_requests_total",
        {
            "method": method,
            "path": path,
            "status_code": str(status_code),
        },
    )

    return samples if samples is not None else 0.0


def _histogram_count(
    method: str,
    path: str,
) -> float:
    """Return the number of observations for an HTTP duration histogram."""

    samples = REGISTRY.get_sample_value(
        "http_request_duration_seconds_count",
        {
            "method": method,
            "path": path,
        },
    )

    return samples if samples is not None else 0.0


# ---------------------------------------------------------------------------
# Prometheus middleware
# ---------------------------------------------------------------------------


def test_prometheus_middleware_records_successful_request(
    client: TestClient,
) -> None:
    """Successful requests increment the counter and record duration."""

    method = "GET"
    path = "/"

    counter_before = _counter_value(method, path, 200)
    duration_before = _histogram_count(method, path)

    response = client.get(path)

    assert response.status_code == 200

    counter_after = _counter_value(method, path, 200)
    duration_after = _histogram_count(method, path)

    assert counter_after == counter_before + 1
    assert duration_after == duration_before + 1


def test_prometheus_middleware_uses_route_template(
    client: TestClient,
) -> None:
    """Metrics use the matched FastAPI route rather than the raw request path."""

    method = "GET"
    path = "/api/v1/health"

    counter_before = _counter_value(method, path, 200)

    response = client.get(path)

    assert response.status_code == 200

    counter_after = _counter_value(method, path, 200)

    assert counter_after == counter_before + 1


def test_prometheus_middleware_records_unmatched_route(
    client: TestClient,
) -> None:
    """An unmatched route is recorded using the 'unmatched' path label."""

    method = "GET"
    metric_path = "unmatched"

    counter_before = _counter_value(method, metric_path, 404)

    response = client.get("/this-route-does-not-exist")

    assert response.status_code == 404

    counter_after = _counter_value(method, metric_path, 404)

    assert counter_after == counter_before + 1


def test_prometheus_middleware_does_not_record_metrics_endpoint(
    client: TestClient,
) -> None:
    """The /metrics endpoint is deliberately excluded from HTTP metrics."""

    method = "GET"
    path = "/metrics"

    counter_before = _counter_value(method, path, 200)
    duration_before = _histogram_count(method, path)

    response = client.get(path)

    assert response.status_code == 200

    counter_after = _counter_value(method, path, 200)
    duration_after = _histogram_count(method, path)

    assert counter_after == counter_before
    assert duration_after == duration_before


def test_prometheus_middleware_records_500_when_request_raises() -> None:
    """An exception from downstream code should be recorded as HTTP 500."""

    method = "GET"
    path = "/test-error"

    counter_before = _counter_value(method, path, 500)
    duration_before = _histogram_count(method, path)

    async def failing_endpoint() -> None:
        raise RuntimeError("test failure")

    test_app = FastAPI()
    test_app.add_api_route(
        path,
        failing_endpoint,
        methods=["GET"],
    )

    test_app.middleware("http")(main.prometheus_middleware)

    test_client = TestClient(
        test_app,
        raise_server_exceptions=False,
    )

    response = test_client.get(path)

    assert response.status_code == 500

    counter_after = _counter_value(method, path, 500)
    duration_after = _histogram_count(method, path)

    assert counter_after == counter_before + 1
    assert duration_after == duration_before + 1


# ---------------------------------------------------------------------------
# Application lifespan
# ---------------------------------------------------------------------------


def test_lifespan_loads_model() -> None:
    """Application startup should attempt to load the model."""

    with patch("services.backend.src.main.load_model") as mock_load_model:

        async def run_lifespan() -> None:
            async with main.lifespan(main.app):
                pass

        asyncio.run(run_lifespan())

    mock_load_model.assert_called_once_with()


def test_lifespan_continues_when_model_loading_fails() -> None:
    """A model-loading failure should not prevent application startup."""

    with patch(
        "services.backend.src.main.load_model",
        side_effect=RuntimeError("MLflow unavailable"),
    ) as mock_load_model:

        async def run_lifespan() -> None:
            async with main.lifespan(main.app):
                pass

        asyncio.run(run_lifespan())

    mock_load_model.assert_called_once_with()
