"""Demo metrics exporter — NK monitoring sandbox.

Emits the SAME Prometheus metric names the real ASP backend exposes
(services/backend/src/core/metrics.py), but with random, plausible values.
That way the Grafana dashboards light up without running the whole app — and
the exact same dashboards work against the real backend later (identical names).

Serves Prometheus text format on http://0.0.0.0:8010/metrics.
A background thread nudges the numbers every few seconds so the graphs move.
"""

from __future__ import annotations

import random
import threading
import time

from prometheus_client import Counter, Gauge, Histogram, start_http_server

PORT = 8010
MODEL_VERSION = "asp-model-demo-2024"

# --- API metrics (mirror the backend) ----------------------------------------
http_requests_total = Counter(
    "http_requests_total",
    "Total number of HTTP requests received.",
    ["method", "path", "status_code"],
)
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds.",
    ["method", "path"],
)

# --- Model metrics (mirror the backend) --------------------------------------
predictions_total = Counter(
    "predictions_total",
    "Total number of predictions served, by predicted class.",
    ["severity_code", "model_version"],
)
prediction_confidence = Histogram(
    "prediction_confidence",
    "Predicted class probability (confidence) of served predictions.",
    ["model_version"],
    buckets=(0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0),
)
prediction_duration_seconds = Histogram(
    "prediction_duration_seconds",
    "Time spent in model inference only.",
    ["model_version"],
)
model_loaded = Gauge(
    "model_loaded",
    "Whether a model is loaded and ready (1) or not (0).",
    ["model_version", "alias"],
)
model_reload_total = Counter(
    "model_reload_total",
    "Total number of model reload attempts.",
    ["status"],
)

# --- Drift metrics (NK's contribution, read from the drift contract normally) -
model_f1_score = Gauge("model_f1_score", "F1 of the currently promoted model.", ["model_version"])
model_drift_share = Gauge("model_drift_share", "Share of features flagged as drifted.", ["model_version"])
model_dataset_drift_detected = Gauge(
    "model_dataset_drift_detected", "Dataset-level drift detected (1) or not (0).", ["model_version"]
)

# Endpoints/classes we pretend to serve.
PATHS = ["/api/v1/predict", "/api/v1/health", "/api/v1/model/reload"]
SEVERITY = ["0", "1"]  # grav is binarised


def _seed_static() -> None:
    """Values that don't move much."""
    model_loaded.labels(model_version=MODEL_VERSION, alias="production").set(1)
    model_f1_score.labels(model_version=MODEL_VERSION).set(0.70)
    model_drift_share.labels(model_version=MODEL_VERSION).set(0.042)
    model_dataset_drift_detected.labels(model_version=MODEL_VERSION).set(0)


def _simulate_once() -> None:
    """One tick of fake traffic."""
    # API traffic: mostly 200s, occasional 4xx/5xx.
    for path in PATHS:
        for _ in range(random.randint(1, 8)):
            status = random.choices(["200", "400", "500"], weights=[92, 6, 2])[0]
            http_requests_total.labels(method="POST", path=path, status_code=status).inc()
            http_request_duration_seconds.labels(method="POST", path=path).observe(random.uniform(0.02, 1.8))

    # Predictions + confidence + inference time.
    for _ in range(random.randint(1, 6)):
        cls = random.choice(SEVERITY)
        predictions_total.labels(severity_code=cls, model_version=MODEL_VERSION).inc()
        prediction_confidence.labels(model_version=MODEL_VERSION).observe(random.uniform(0.55, 0.99))
        prediction_duration_seconds.labels(model_version=MODEL_VERSION).observe(random.uniform(0.005, 0.08))

    # Rare model reload.
    if random.random() < 0.05:
        model_reload_total.labels(status=random.choice(["success", "failure"])).inc()

    # Drift metrics drift slowly around their seed values.
    model_f1_score.labels(model_version=MODEL_VERSION).set(round(random.uniform(0.66, 0.74), 3))
    model_drift_share.labels(model_version=MODEL_VERSION).set(round(random.uniform(0.02, 0.09), 3))


def _loop() -> None:
    _seed_static()
    while True:
        _simulate_once()
        time.sleep(3)


if __name__ == "__main__":
    start_http_server(PORT)  # exposes /metrics on 0.0.0.0:PORT
    print(f"[demo-exporter] serving ASP demo metrics on :{PORT}/metrics")
    threading.Thread(target=_loop, daemon=True).start()
    while True:
        time.sleep(3600)
