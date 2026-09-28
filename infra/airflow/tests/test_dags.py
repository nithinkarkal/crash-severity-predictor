"""
DAG-integrity tests for the ASP Airflow feature.

These assert that both DAGs *parse* with no import errors and have the expected
tasks and wiring — the pytest equivalent of `airflow dags list-import-errors`, but
checked in CI. They require Airflow (+ the Docker provider) to import the DAG files.

Airflow is NOT a core project dependency (it lives in the asp-airflow image), so this
module is skipped cleanly when Airflow isn't installed. To run it:
    uv sync --group airflow-tests      # install airflow into the test env
    uv run pytest infra/airflow/tests/test_dags.py
or run it inside the asp-airflow container, which already has Airflow.
"""

import os
from pathlib import Path

import pytest

# Skip the whole module unless Airflow is importable (keeps the default suite green
# for teammates who haven't installed the airflow-tests group).
pytest.importorskip("airflow")

os.environ.setdefault("AIRFLOW__CORE__LOAD_EXAMPLES", "False")

from airflow.models import DagBag  # noqa: E402  (import after importorskip on purpose)

DAG_FOLDER = str(Path(__file__).resolve().parents[1] / "dags")

EXPECTED_RETRAINING_TASKS = {
    "check_and_ingest_data",
    "build_dataset",
    "validate_data",
    "version_dataset_dvc",
    "train_and_log_mlflow",
    "detect_drift",
    "compare_against_champion",
    "promote_to_production",
    "reload_fastapi",
}


@pytest.fixture(scope="module")
def dagbag() -> DagBag:
    return DagBag(dag_folder=DAG_FOLDER, include_examples=False)


def test_dags_import_without_errors(dagbag: DagBag) -> None:
    """No syntax/import errors and cycles (a cycle surfaces here as an import error)."""
    assert dagbag.import_errors == {}, dagbag.import_errors


def test_retraining_dag_registered(dagbag: DagBag) -> None:
    # The project ships a single DAG: asp_retraining.
    assert "asp_retraining" in set(dagbag.dag_ids)
    assert "asp_pipeline" not in set(dagbag.dag_ids)


def test_retraining_tasks_present(dagbag: DagBag) -> None:
    dag = dagbag.get_dag("asp_retraining")
    assert set(dag.task_ids) == EXPECTED_RETRAINING_TASKS


def test_retraining_promotion_is_dag_governed(dagbag: DagBag) -> None:
    """Option B + drift gate: train -> detect_drift -> compare -> promote -> reload."""
    dag = dagbag.get_dag("asp_retraining")
    # drift/quality gate runs after train and before the promotion decision
    assert dag.get_task("detect_drift").upstream_task_ids == {"train_and_log_mlflow"}
    assert dag.get_task("compare_against_champion").upstream_task_ids == {"detect_drift"}
    assert dag.get_task("promote_to_production").upstream_task_ids == {"compare_against_champion"}
    assert dag.get_task("reload_fastapi").upstream_task_ids == {"promote_to_production"}
    # never version a dataset that failed QA
    assert dag.get_task("version_dataset_dvc").upstream_task_ids == {"validate_data"}


def test_retraining_scheduled_yearly(dagbag: DagBag) -> None:
    """asp_retraining runs once a year (00:00 on 1 Jan), matching the annual data batch."""
    assert dagbag.get_dag("asp_retraining").schedule_interval == "0 0 1 1 *"
