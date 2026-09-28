"""Prometheus metrics registry and definitions for the ASP backend.

Uses a single, explicit CollectorRegistry (rather than the prometheus_client
default global registry) so every metric this service exposes lives in one
obvious place.
"""

from __future__ import annotations

import json
from pathlib import Path

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

from common.utils.asp_logging import get_logger
from services.monitoring.drift import CONTRACT_FILE

logger = get_logger(__name__)

REGISTRY = CollectorRegistry()

# --- API monitoring ----------------------------------------------------------

http_requests_total = Counter(
    "http_requests_total",
    "Total number of HTTP requests received.",
    ["method", "path", "status_code"],
    registry=REGISTRY,
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds.",
    ["method", "path"],
    registry=REGISTRY,
)

# --- Model monitoring ---------------------------------------------------------

predictions_total = Counter(
    "predictions_total",
    "Total number of predictions served, by predicted class.",
    ["severity_code", "model_version"],
    registry=REGISTRY,
)

prediction_confidence = Histogram(
    "prediction_confidence",
    "Predicted class probability (confidence) of served predictions.",
    ["model_version"],
    buckets=(0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0),
    registry=REGISTRY,
)

prediction_duration_seconds = Histogram(
    "prediction_duration_seconds",
    "Time spent in model inference only (excludes HTTP/auth overhead).",
    ["model_version"],
    registry=REGISTRY,
)

model_loaded = Gauge(
    "model_loaded",
    "Whether a model is currently loaded and ready to serve (1) or not (0).",
    ["model_version", "alias"],
    registry=REGISTRY,
)

model_reload_total = Counter(
    "model_reload_total",
    "Total number of model reload attempts.",
    ["status"],  # "success" | "failure"
    registry=REGISTRY,
)

model_f1_score = Gauge(
    "model_f1_score",
    "F1 score of the currently promoted model, from the latest drift/quality-gate report.",
    ["model_version"],
    registry=REGISTRY,
)

model_drift_share = Gauge(
    "model_drift_share",
    "Share of features flagged as drifted in the latest drift report.",
    ["model_version"],
    registry=REGISTRY,
)

model_dataset_drift_detected = Gauge(
    "model_dataset_drift_detected",
    "Whether dataset-level drift was detected in the latest drift report (1) or not (0).",
    ["model_version"],
    registry=REGISTRY,
)


def refresh_drift_metrics(model_version: str) -> None:
    """Read the latest drift contract file (written by services/monitoring/drift.py)
    and update the corresponding Gauges.

    Called on-demand whenever /metrics is scraped, so exported values are always
    as fresh as the last drift run -- no background thread needed.
    """
    if not Path(CONTRACT_FILE).is_file():
        logger.debug(f"No drift contract file yet at {CONTRACT_FILE}; skipping drift metrics refresh.")
        return

    try:
        # Caveat: drift contract describes the model that was evaluated during the last training/gate run,
        # while model_version here is whatever's currently loaded in the backend.
        # These can technically diverge (e.g., gate ran, but reload hasn't happened yet, or reload failed and fell back)
        with open(CONTRACT_FILE) as f:
            contract = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(f"Failed to read drift contract file {CONTRACT_FILE}: {exc}")
        return

    if contract.get("f1_score") is not None:
        model_f1_score.labels(model_version=model_version).set(contract["f1_score"])
    if contract.get("drift_share") is not None:
        model_drift_share.labels(model_version=model_version).set(contract["drift_share"])
    if contract.get("dataset_drift") is not None:
        model_dataset_drift_detected.labels(model_version=model_version).set(int(contract["dataset_drift"]))
