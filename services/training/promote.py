"""
Model promotion step for the retraining pipeline (Airflow "Option B").

Why this module exists
----------------------
The training entrypoint (``services.training.train``) trains a model, logs it to
MLflow and **registers** it as a new candidate version. It intentionally does NOT
decide whether that candidate becomes the production model — that decision is
governed by the ``asp_retraining`` Airflow DAG as two explicit, visible steps:

    STEP 5  compare_against_champion  ->  python -m services.training.promote compare
    STEP 6  promote_to_production     ->  python -m services.training.promote promote

Keeping promotion in the orchestrator (not the training script) is the cleaner
MLOps separation: the *pipeline* governs what reaches production, and each step is
its own task in the DAG with its own log, retry and status.

Both steps reuse the tested helpers in ``common.utils.mlflow`` — nothing about the
promotion logic is reimplemented here.

  * ``compare``  : read-only. Finds the freshly registered candidate version, reads
                   its evaluation metric, compares it to the current ``production``
                   model, logs the verdict and writes a small decision file to
                   ``artifacts/reports/promotion_decision.json`` (a simple, auditable
                   hand-off between the two tasks via the shared mounted volume).
  * ``promote``  : calls ``promote_if_better`` — promotes the candidate to the
                   ``production`` alias (and moves the old one to ``fallback`` for
                   rollback) only if it beats the champion on the metric.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from mlflow import MlflowClient
from mlflow.exceptions import MlflowException

from common.utils.asp_logging import get_logger
from common.utils.mlflow import promote_if_better, setup_mlflow
from common.utils.paths import METRIC_DIR, MODEL_CONFIG, REPORT_DIR

logger = get_logger(__name__)

PROD_ALIAS = "production"
METRIC_NAME = "f1_score"
DECISION_FILE = REPORT_DIR / "promotion_decision.json"


def latest_candidate_version(client: MlflowClient, registry_model_name: str) -> Any:
    """Return the highest-numbered registered version (the candidate just trained)."""

    versions = client.search_model_versions(f"name='{registry_model_name}'")
    if not versions:
        raise RuntimeError(f"No registered versions for '{registry_model_name}'. Run the training step first.")
    return max(versions, key=lambda v: int(v.version))


def latest_metrics(metrics_dir: Path = METRIC_DIR) -> dict[str, Any]:
    """Load the most recent ``*_metrics.json`` written by the evaluation step."""

    files = list(Path(metrics_dir).glob("*_metrics.json"))
    if not files:
        raise FileNotFoundError(f"No '*_metrics.json' found in {metrics_dir}. Run the training/evaluation step first.")
    newest = max(files, key=lambda p: p.stat().st_mtime)
    with open(newest) as f:
        data: dict[str, Any] = json.load(f)
    return data


def current_production_metric(
    client: MlflowClient,
    registry_model_name: str,
    metric_name: str = METRIC_NAME,
) -> float | None:
    """Return the champion's metric value, or ``None`` if there is no production model / metric."""

    try:
        current = client.get_model_version_by_alias(registry_model_name, PROD_ALIAS)
    except MlflowException:
        return None

    run = client.get_run(current.run_id)
    value = run.data.metrics.get(metric_name)
    return float(value) if value is not None else None


def compare() -> bool:
    """STEP 5 — read-only comparison of the candidate vs the current production model.

    Writes ``artifacts/reports/promotion_decision.json`` and returns whether the
    candidate is better (True also when there is no production model yet).
    """

    setup_mlflow()
    client = MlflowClient()
    name = MODEL_CONFIG["model_registry_name"]

    candidate = latest_candidate_version(client, name)
    new_metric = float(latest_metrics()[METRIC_NAME])
    current_metric = current_production_metric(client, name)

    is_better = current_metric is None or new_metric > current_metric

    if current_metric is None:
        logger.info(
            f"STEP 5: no current '{PROD_ALIAS}' model. Candidate v{candidate.version} ({METRIC_NAME}={new_metric:.4f}) would be promoted by default."
        )
    else:
        verdict = "BETTER than" if is_better else "NOT better than"
        logger.info(
            f"STEP 5: candidate v{candidate.version} ({METRIC_NAME}={new_metric:.4f}) is {verdict} "
            f"current production ({METRIC_NAME}={current_metric:.4f})."
        )

    decision = {
        "candidate_version": candidate.version,
        "metric_name": METRIC_NAME,
        "new_metric": new_metric,
        "current_metric": current_metric,
        "is_better": is_better,
    }
    DECISION_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DECISION_FILE, "w") as f:
        json.dump(decision, f, indent=2)
    logger.info(f"STEP 5: wrote decision -> {DECISION_FILE}")

    return is_better


def promote() -> bool:
    """STEP 6 — promote the candidate to production if it beats the champion.

    Reuses ``common.utils.mlflow.promote_if_better`` (compare + promote + fallback
    rollback). Returns True if promotion happened.
    """

    setup_mlflow()
    client = MlflowClient()
    name = MODEL_CONFIG["model_registry_name"]

    candidate = latest_candidate_version(client, name)
    metrics = latest_metrics()

    promoted = promote_if_better(
        registered_version=candidate,
        eval_out={"metrics": metrics},
        registry_model_name=name,
        metric_name=METRIC_NAME,
    )

    if promoted:
        logger.info(f"STEP 6: candidate v{candidate.version} promoted to '{PROD_ALIAS}'.")
    else:
        logger.info(f"STEP 6: candidate v{candidate.version} NOT promoted; current production kept.")

    return promoted


def main(argv: list[str] | None = None) -> None:
    """CLI: ``python -m services.training.promote {compare|promote}``."""

    argv = argv if argv is not None else sys.argv[1:]
    command = argv[0] if argv else ""

    if command == "compare":
        compare()
    elif command == "promote":
        promote()
    else:
        raise SystemExit("usage: python -m services.training.promote {compare|promote}")


if __name__ == "__main__":
    main()
