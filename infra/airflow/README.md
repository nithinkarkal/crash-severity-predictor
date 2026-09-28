# Airflow Orchestration (ASP)

Self-contained Apache Airflow setup that runs the model **retraining pipeline**. Isolated under
`infra/airflow/` — it does not touch `docker-compose.yaml`, `dvc.yaml`, or any service code. Each
step launches one of the project's images as a short-lived sibling container.

## Pipeline

One DAG — **`asp_retraining`** (`dags/asp_retraining_dag.py`), fully implemented:

```
ingest → build → validate → version(DVC) → train+register
       → detect_drift(F1 gate) → compare → promote → reload → alerts
```

- **Schedule:** yearly, `0 0 1 1 *` (00:00 on 1 Jan). Comment it / uncomment `schedule=None` for manual-only.
- **Promotion (Option B):** training only registers a candidate; the DAG promotes via
  `services.training.promote` (compare → promote).
- **Drift gate:** `detect_drift` blocks promotion if F1 on the new batch < `ASP_F1_THRESHOLD`.

## Files

| File | Purpose |
|------|---------|
| `dags/asp_retraining_dag.py` | The retraining DAG |
| `docker-compose.airflow.yml` | Airflow (standalone) + Docker socket mount |
| `Dockerfile.runner` | Helper image for the DVC + validation tasks |
| `Dockerfile.drift` | Isolated Evidently image for `detect_drift` |
| `.env.example` | Config template — copy to `.env` |

## Prerequisites

Docker Desktop running, and the four images built once from the repo root:

```bash
docker compose --profile build-only build                                          # asp-training
docker compose build backend                                                       # asp-backend
docker build -f infra/airflow/Dockerfile.runner -t asp-airflow-runner:latest infra/airflow
docker build -f infra/airflow/Dockerfile.drift  -t asp-drift:latest         infra/airflow
```

## Quickstart

From inside `infra/airflow/`:

```bash
cp .env.example .env          # set HOST_PROJECT_ROOT to the ABSOLUTE repo path
                              # Windows: forward slashes (C:/Users/you/.../accident-severity-predictor)
docker compose -f docker-compose.airflow.yml up -d --build
docker compose -f docker-compose.airflow.yml logs airflow | grep -i password   # admin password
# open http://localhost:8080  (user: admin) → enable & trigger "asp_retraining"
docker compose -f docker-compose.airflow.yml down                              # stop (keeps data)
```

## Config (`.env`)

| Var | For |
|-----|-----|
| `HOST_PROJECT_ROOT` | Absolute repo path bind-mounted into each task (required) |
| `DAGSHUB_USER_TOKEN`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | DVC push + training (DagsHub) |
| `ASP_F1_THRESHOLD` | Drift/quality gate floor (default `0.65`) |
| `FASTAPI_RELOAD_URL` | Backend reload endpoint for the `reload` step (lenient if unset) |
| `SLACK_WEBHOOK_URL` | Success/failure alerts (logs only if unset) |

## Docs

- `docs/phase-8-airflow-orchestration.md` — the DAG + Option B promotion; **§8.9 = common
  Windows/Docker-Desktop run issues** (DNS, `UID`/`GID`, DagsHub creds, mounts).
- `docs/phase-9-drift-detection.md` — the `detect_drift` step (Evidently drift + F1 gate).
- `docs/HOW-TO-VERIFY.md` — run-it-yourself checklist and health checks.
