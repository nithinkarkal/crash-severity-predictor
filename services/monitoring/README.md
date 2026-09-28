# Monitoring — Drift Detection

Data/target **drift detection with an F1 quality gate**, run as the `detect_drift` step of the
retraining DAG (after `train`, before `compare`). Compares the new annual batch against the
baseline years with [Evidently](https://www.evidentlyai.com/) and blocks promotion of a degraded model.

## What it does

- Loads the raw, pre-scale frames `data/processed/reference_raw.csv` (baseline) and
  `current_raw.csv` (new batch); target = `grav`.
- Runs Evidently `DataDriftPreset` + `TargetDriftPreset`.
- Reads the model's F1 from the latest `artifacts/metrics/*_metrics.json` (written by training).
- **Gate:** exits non-zero if F1 < `ASP_F1_THRESHOLD` (default `0.65`) → the DAG stops, model isn't promoted.

## Outputs (`artifacts/reports/drift/`)

| File | Purpose |
|------|---------|
| `drift_report_<year>.html` | Visual Evidently report |
| `drift_report_<year>.json` | Full machine-readable report |
| `latest_metrics.json` | Stable metrics contract → Prometheus / Grafana / frontend |

Contract keys: `dataset_drift`, `drift_share`, `n_drifted_features`, `target_drift_detected`,
`target_drift_score`, `f1_score`, `f1_threshold`, `passed`.

## Run it yourself

```bash
docker build -f infra/airflow/Dockerfile.drift -t asp-drift:latest infra/airflow
docker run --rm -v "${PWD}:/app" -w /app asp-drift:latest python -m services.monitoring.drift
```

Unit tests (Evidently mocked): `uv run pytest services/monitoring/tests -q`

Evidently is isolated in the `asp-drift` image (pinned `evidently>=0.4.30,<0.5`) so the main
project env / CI are unaffected.

## Docs

Full walkthrough (how it works, the categorical-scaling gotcha, do-it-yourself steps, Windows notes):
`infra/airflow/docs/phase-9-drift-detection.md`.
