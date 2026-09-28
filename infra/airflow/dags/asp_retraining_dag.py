"""
ASP RETRAINING DAG — the full production retraining pipeline (8 steps).

This is the project's single DAG — it lays out the full retraining pipeline in order.
Most steps are IMPLEMENTED; the API-reload step depends on a backend endpoint that does
not exist yet, so it is a clearly-marked PLACEHOLDER that succeeds as a no-op until the
endpoint is added — the DAG runs end-to-end today and shows the whole flow.

Step map (your 8-task spec):
  1. check_and_ingest_data     -> ingest new yearly data            [IMPLEMENTED, Docker]
     (+ build_dataset)         -> build processed X/y (needed prep) [IMPLEMENTED, Docker]
  3. validate_data             -> data quality + shape checks       [IMPLEMENTED, Docker+runner]
  2. version_dataset_dvc       -> version dataset with DVC          [IMPLEMENTED, needs creds]
  4. train_and_log_mlflow      -> train + evaluate + REGISTER cand. [IMPLEMENTED, Docker]
  5. compare_against_champion  -> compare candidate vs champion     [IMPLEMENTED, Docker (promote compare)]
  6. promote_to_production     -> promote in MLflow Registry        [IMPLEMENTED, Docker (promote promote)]
  7. reload_fastapi            -> tell the API to load new model    [IMPLEMENTED — POSTs /api/v1/model/reload]
  8. success/failure alerts    -> Slack notifications (+ logging)   [IMPLEMENTED as callbacks]

Scheduled to run once a year (00:00 on 1 January) to match the annual BAAC data batch;
comment `schedule` / uncomment `schedule=None` in the DAG below to trigger manually only.

Promotion design (Option B): the training step only trains + logs + REGISTERS a
candidate model version. The DAG then GOVERNS promotion as two explicit steps that
run `services.training.promote` (compare, then promote) — reusing the tested
`promote_if_better` helper. Keeping promotion in the orchestrator (not the training
script) is the cleaner MLOps separation. Steps 5 & 6 therefore run as DockerOperator
tasks in the training image, exactly like train. Only STEP 7 (API reload) remains a
placeholder — it needs a reload endpoint the backend does not expose yet.

NOTE on ordering: your spec lists version(2) before validate(3). We intentionally run
`validate_data` BEFORE `version_dataset_dvc` so we never version a dataset that failed
QA. Swap the two lines at the bottom if you must match the exact spec order.

Prereqs (see infra/airflow/README.md):
  - Build images: asp-backend:latest, asp-training:latest, asp-airflow-runner:latest
  - Set HOST_PROJECT_ROOT (+ optional AWS_* DagsHub creds, FASTAPI_RELOAD_URL) in infra/airflow/.env
"""

from __future__ import annotations

import logging
import os
from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.docker.operators.docker import DockerOperator
from docker.types import Mount

log = logging.getLogger("airflow.task")

# ---------------------------------------------------------------------------
# Configuration (from environment; see infra/airflow/.env)
# ---------------------------------------------------------------------------
HOST_PROJECT_ROOT = os.environ.get("HOST_PROJECT_ROOT", "/absolute/path/to/accident-severity-predictor")

BACKEND_IMAGE = os.environ.get("ASP_BACKEND_IMAGE", "asp-backend:latest")
TRAINING_IMAGE = os.environ.get("ASP_TRAINING_IMAGE", "asp-training:latest")
RUNNER_IMAGE = os.environ.get("ASP_RUNNER_IMAGE", "asp-airflow-runner:latest")
DRIFT_IMAGE = os.environ.get("ASP_DRIFT_IMAGE", "asp-drift:latest")

# F1 floor for the drift/quality gate (detect_drift). Below this, promotion is blocked.
F1_THRESHOLD = os.environ.get("ASP_F1_THRESHOLD", "0.65")

VENV_PYTHON = "/app/.venv/bin/python"  # interpreter inside the asp-backend / asp-training images

# DagsHub S3 credentials for the DVC task (empty by default -> that task will fail loudly,
# which is the correct signal that creds are missing).
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "")

# Where the running FastAPI backend exposes its "reload the model" endpoint (STEP 7).
FASTAPI_RELOAD_URL = os.environ.get("FASTAPI_RELOAD_URL", "")

# Slack incoming-webhook URL for success/failure alerts (STEP 8). Empty -> alerts log only.
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")

# Mounts for tasks that run the project images (data/ + artifacts/, same as the app).
APP_MOUNTS = [
    Mount(source=f"{HOST_PROJECT_ROOT}/data", target="/app/data", type="bind"),
    Mount(source=f"{HOST_PROJECT_ROOT}/artifacts", target="/app/artifacts", type="bind"),
]

# Settings shared by every DockerOperator task.
DOCKER_COMMON = dict(
    api_version="auto",
    docker_url="unix://var/run/docker.sock",
    mount_tmp_dir=False,
    auto_remove="success",
    network_mode="bridge",
    dns=["8.8.8.8", "8.8.4.4"],  # <-- add: containers use public DNS
)

default_args = {
    "owner": "asp-team",
    "retries": 0,
}


# ---------------------------------------------------------------------------
# Step 7 callable — tell the running backend to serve the newly promoted model.
# (Steps 5 & 6 are REAL DockerOperator tasks running services.training.promote.)
# ---------------------------------------------------------------------------
def _reload_fastapi(**context) -> None:
    """STEP 7 — signal the running FastAPI backend to reload the newly promoted model.

    POSTs to the backend's reload endpoint (POST /api/v1/model/reload), which force-
    reloads the current 'production' model from the MLflow registry — so the promoted
    champion is served without restarting the API. Set FASTAPI_RELOAD_URL in
    infra/airflow/.env (e.g. http://host.docker.internal:8000/api/v1/model/reload).

    Behaviour is LENIENT: if the URL is unset or the backend is unreachable, we log a
    warning and let the DAG succeed (the model still goes live on the backend's next
    start). Switch the `log.warning` below to `raise` if you want a failed reload to
    fail the pipeline.
    """
    if not FASTAPI_RELOAD_URL:
        log.info("STEP 7: FASTAPI_RELOAD_URL not set — skipping reload.")
        log.info("  -> set it in infra/airflow/.env to serve the new model without a backend restart.")
        return
    try:
        import requests  # available in the Airflow image

        resp = requests.post(FASTAPI_RELOAD_URL, timeout=10)
        log.info(f"STEP 7: reload signal -> {FASTAPI_RELOAD_URL} returned {resp.status_code}")
    except Exception as exc:  # noqa: BLE001 - lenient: a failed reload must not fail the DAG
        log.warning(f"STEP 7: reload call failed (is the backend running on :8000?): {exc}")


# ---------------------------------------------------------------------------
# Alerting (step 8) — DAG-level success/failure callbacks -> Slack
# ---------------------------------------------------------------------------
def _notify_slack(text: str) -> None:
    """POST a message to a Slack incoming webhook.

    LENIENT: if SLACK_WEBHOOK_URL is unset or Slack is unreachable, we just log and
    move on — alerting must never fail the pipeline. Create a webhook at
    https://api.slack.com/messaging/webhooks and put its URL in SLACK_WEBHOOK_URL.
    """
    if not SLACK_WEBHOOK_URL:
        log.info(f"ALERT (Slack skipped — no SLACK_WEBHOOK_URL): {text}")
        return
    try:
        import requests  # available in the Airflow image

        resp = requests.post(SLACK_WEBHOOK_URL, json={"text": text}, timeout=10)
        log.info(f"ALERT -> Slack returned {resp.status_code}")
    except Exception as exc:  # noqa: BLE001 - alerting must never fail the DAG
        log.warning(f"ALERT: Slack notification failed: {exc}")


def _on_success(context) -> None:
    msg = f":white_check_mark: ASP retraining SUCCEEDED — run '{context['run_id']}'."
    log.info(msg)
    _notify_slack(msg)


def _on_failure(context) -> None:
    ti = context.get("task_instance")
    where = ti.task_id if ti else "unknown"
    msg = f":x: ASP retraining FAILED at task '{where}' — run '{context['run_id']}'."
    log.error(msg)
    _notify_slack(msg)


# ---------------------------------------------------------------------------
# The DAG
# ---------------------------------------------------------------------------
with DAG(
    dag_id="asp_retraining",
    description="Full ASP retraining pipeline: ingest -> validate -> version -> train -> compare -> promote -> reload.",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    # Retrain once a year, at 00:00 on 1 January — a new annual BAAC batch is published
    # each year, so this matches the data cadence. To disable the schedule and trigger
    # only manually, comment the line below and uncomment `schedule=None`.
    schedule="0 0 1 1 *",
    # schedule=None,
    catchup=False,  # don't back-fill every past 1-Jan since start_date
    on_success_callback=_on_success,  # STEP 8
    on_failure_callback=_on_failure,  # STEP 8
    tags=["asp", "mlops", "retraining"],
) as dag:
    # STEP 1 — check & ingest new yearly data (download raw CSVs from data.gouv.fr).
    check_and_ingest_data = DockerOperator(
        task_id="check_and_ingest_data",
        image=BACKEND_IMAGE,  # needs `requests` (backend group)
        entrypoint=[VENV_PYTHON],
        command=["-m", "common.data.download_data"],
        mounts=APP_MOUNTS,
        **DOCKER_COMMON,
    )

    # PREP — build the processed X/y dataset (clean + merge + split + scale).
    build_dataset = DockerOperator(
        task_id="build_dataset",
        image=TRAINING_IMAGE,
        # mkdir mirrors the dvc.yaml stage (`mkdir -p data/processed && ...`); the host
        # bind-mount shadows the dir the image created at build time, so create it here.
        entrypoint=["/bin/sh", "-c"],
        command=["mkdir -p /app/data/processed && /app/.venv/bin/python -m common.data.make_dataset"],
        mounts=APP_MOUNTS,
        **DOCKER_COMMON,
    )

    # STEP 3 — validate data quality & shapes (fails the pipeline if the data is bad).
    validate_data = DockerOperator(
        task_id="validate_data",
        image=RUNNER_IMAGE,
        entrypoint=["python"],
        command=["/scripts/validate_data.py"],
        mounts=[
            Mount(source=f"{HOST_PROJECT_ROOT}/data", target="/data", type="bind"),
            Mount(source=f"{HOST_PROJECT_ROOT}/infra/airflow/scripts", target="/scripts", type="bind"),
        ],
        **DOCKER_COMMON,
    )

    # STEP 2 — version the dataset (and artifacts) with DVC, then push to DagsHub.
    #          Runs `dvc commit` (record current pipeline outputs) + `dvc push` (upload).
    version_dataset_dvc = DockerOperator(
        task_id="version_dataset_dvc",
        image=RUNNER_IMAGE,
        entrypoint=["/bin/sh", "-c"],
        command=["cd /repo && dvc commit -f && dvc push"],
        working_dir="/repo",
        mounts=[Mount(source=HOST_PROJECT_ROOT, target="/repo", type="bind")],
        environment={
            "AWS_ACCESS_KEY_ID": AWS_ACCESS_KEY_ID,  # DagsHub S3 creds
            "AWS_SECRET_ACCESS_KEY": AWS_SECRET_ACCESS_KEY,
        },
        **DOCKER_COMMON,
    )

    # DagsHub token env, shared by the train/compare/promote tasks (they all talk to
    # MLflow via dagshub.init(), which needs the token in a headless container).
    MLFLOW_ENV = {"DAGSHUB_USER_TOKEN": os.environ.get("DAGSHUB_USER_TOKEN", "")}

    # STEP 4 — train + evaluate, then REGISTER the model as a new candidate version.
    #          (services.training.train no longer auto-promotes — the DAG governs that.)
    train_and_log_mlflow = DockerOperator(
        task_id="train_and_log_mlflow",
        image=TRAINING_IMAGE,
        entrypoint=[VENV_PYTHON],
        command=["-m", "services.training.train"],
        mounts=APP_MOUNTS,
        environment=MLFLOW_ENV,
        **DOCKER_COMMON,
    )

    # STEP 4.5 — drift & quality gate. Compares the new annual batch (current) vs the
    #            baseline years (reference) with Evidently, saves an HTML + JSON report,
    #            and FAILS (blocks promotion) if F1 on the new batch < ASP_F1_THRESHOLD.
    #            Runs in the tiny asp-drift image; the whole repo is mounted at /app so it
    #            can read data/processed + artifacts/metrics and write artifacts/reports/drift.
    detect_drift = DockerOperator(
        task_id="detect_drift",
        image=DRIFT_IMAGE,
        entrypoint=["python"],
        command=["-m", "services.monitoring.drift"],
        working_dir="/app",
        mounts=[Mount(source=HOST_PROJECT_ROOT, target="/app", type="bind")],
        environment={"ASP_F1_THRESHOLD": F1_THRESHOLD},
        **DOCKER_COMMON,
    )

    # STEP 5 — compare the candidate against the current champion (read-only).
    #          Logs the verdict and writes artifacts/reports/promotion_decision.json.
    compare_against_champion = DockerOperator(
        task_id="compare_against_champion",
        image=TRAINING_IMAGE,
        entrypoint=[VENV_PYTHON],
        command=["-m", "services.training.promote", "compare"],
        mounts=APP_MOUNTS,
        environment=MLFLOW_ENV,
        **DOCKER_COMMON,
    )

    # STEP 6 — promote the candidate to the 'production' alias IF it beats the champion
    #          (moves the old model to 'fallback' for rollback). Reuses promote_if_better.
    promote_to_production = DockerOperator(
        task_id="promote_to_production",
        image=TRAINING_IMAGE,
        entrypoint=[VENV_PYTHON],
        command=["-m", "services.training.promote", "promote"],
        mounts=APP_MOUNTS,
        environment=MLFLOW_ENV,
        **DOCKER_COMMON,
    )

    # STEP 7 — signal FastAPI to reload the new model (POSTs to /api/v1/model/reload).
    reload_fastapi = PythonOperator(
        task_id="reload_fastapi",
        python_callable=_reload_fastapi,
    )

    # --- Wire the pipeline ---------------------------------------------------
    # ingest -> build -> validate -> version -> train -> compare -> promote -> reload
    # (validate before version on purpose; see the note at the top of this file.)
    (
        check_and_ingest_data
        >> build_dataset
        >> validate_data
        >> version_dataset_dvc
        >> train_and_log_mlflow
        >> detect_drift
        >> compare_against_champion
        >> promote_to_production
        >> reload_fastapi
    )
