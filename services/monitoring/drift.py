"""
Data & target drift detection + F1 quality gate for the retraining pipeline.

WHAT THIS DOES (in plain terms)
-------------------------------
When a new year of accident data arrives, we want to answer three questions BEFORE
we let a freshly trained model go to production:

  1. Did the input data change?      -> "data drift"  (e.g. more rain `atm`, different `col`)
  2. Did the answer change?          -> "target drift" (more/fewer severe accidents `grav`)
  3. Is the model still good enough? -> F1 on the new batch vs a minimum threshold

We use **Evidently** to produce a human-readable HTML report + a machine-readable JSON
report, then we run a simple **quality gate**: if the model's F1 on the new batch is below
a threshold, this script exits with a non-zero code. Inside Airflow that turns the task
RED and stops the pipeline, so a degraded model is never promoted. (Same "fail the task to
stop the pipeline" idea as infra/airflow/scripts/validate_data.py.)

WHERE THE DATA COMES FROM
-------------------------
  reference = data/processed/reference_raw.csv   (baseline years, e.g. 2021-2023, + grav)
  current   = data/processed/current_raw.csv     (the new annual batch, e.g. 2024, + grav)
Both are the RAW (pre-normalization) frames written by make_dataset -> save_drift_frames,
so the categorical columns (atm, col, catr, ...) are still real categories, not scaled
floats. That makes the drift report meaningful.

  f1_score  = read from artifacts/metrics/<model>_metrics.json (already computed on the
              new batch by the evaluation step). We reuse it instead of re-predicting, to
              keep this step small and this image tiny.

WHAT IT WRITES
--------------
  artifacts/reports/drift/drift_report_<year>.html   (open in a browser)
  artifacts/reports/drift/drift_report_<year>.json   (full Evidently output)
  artifacts/reports/drift/latest_metrics.json        (the small, STABLE "contract" that
                                                      Prometheus / Grafana / the frontend
                                                      will read later)

RUNTIME
-------
Runs inside the dedicated `asp-drift` image (Evidently is isolated there so it never
clashes with the project's pinned pandas/numpy). Evidently is imported lazily inside the
functions that need it, so the pure-Python helpers below can be unit-tested without it.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from common.utils.asp_logging import get_logger
from common.utils.paths import DATA_PROCESSING_CONFIG, METRIC_DIR, PROCESSED_DATA_DIR, REPORT_DIR

logger = get_logger(__name__)

# --- configuration ---------------------------------------------------------
TARGET = "grav"  # the (binary) target column
METRIC_NAME = "f1_score"  # the metric the gate checks
DEFAULT_F1_THRESHOLD = 0.65  # promotion is blocked below this (override via env)

# Drift on high-cardinality / ID-like columns (commune code `com`, coordinates
# `lat`/`long`, ...) is both extremely slow and meaningless, so we skip any column with
# more than MAX_CARDINALITY distinct values. We also sample rows so the report is fast
# on the full multi-year baseline.
MAX_CARDINALITY = 50
SAMPLE_ROWS = 40000

DRIFT_DIR = REPORT_DIR / "drift"
CONTRACT_FILE = DRIFT_DIR / "latest_metrics.json"

# Categorical columns to mark for Evidently. Mirrors CAT_COLS in
# common/data/merge_data.py — duplicated here on purpose so this module (and the tiny
# drift image) does NOT import merge_data, which would pull in scikit-learn.
CATEGORICAL_COLS = [
    "place",
    "catu",
    "sexe",
    "secu1",
    "catv",
    "obsm",
    "motor",
    "catr",
    "circ",
    "surf",
    "situ",
    "jour",
    "mois",
    "lum",
    "dep",
    "com",
    "agg",
    "int",
    "atm",
    "col",
    "lat",
    "long",
    "hour",
]


def f1_threshold() -> float:
    """The F1 gate threshold, from ASP_F1_THRESHOLD if set, else the default."""
    raw = os.environ.get("ASP_F1_THRESHOLD", "")
    try:
        return float(raw) if raw else DEFAULT_F1_THRESHOLD
    except ValueError:
        logger.warning(f"Invalid ASP_F1_THRESHOLD={raw!r}; using default {DEFAULT_F1_THRESHOLD}")
        return DEFAULT_F1_THRESHOLD


def categorical_features(df: pd.DataFrame) -> list[str]:
    """Categorical columns present in the frame (excluding the target)."""
    return [c for c in CATEGORICAL_COLS if c in df.columns and c != TARGET]


def reduce_for_drift(
    reference: pd.DataFrame,
    current: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """Make the drift analysis fast and meaningful.

    - Drop columns (except the target) with more than MAX_CARDINALITY distinct values —
      e.g. commune code `com`, coordinates `lat`/`long`. Drift tests on those are slow and
      not interpretable.
    - Randomly sample down to SAMPLE_ROWS rows so a multi-year baseline runs in seconds.

    Returns the reduced (reference, current) frames and the list of dropped columns.
    """
    keep = [c for c in reference.columns if c == TARGET or reference[c].nunique(dropna=True) <= MAX_CARDINALITY]
    dropped = [c for c in reference.columns if c not in keep]

    ref = reference[keep]
    cur = current[[c for c in keep if c in current.columns]]

    if len(ref) > SAMPLE_ROWS:
        ref = ref.sample(SAMPLE_ROWS, random_state=42)
    if len(cur) > SAMPLE_ROWS:
        cur = cur.sample(SAMPLE_ROWS, random_state=42)

    return ref, cur, dropped


def latest_f1(metrics_dir: Path = METRIC_DIR) -> float | None:
    """Read the F1 from the most recent artifacts/metrics/*_metrics.json (or None)."""
    files = list(Path(metrics_dir).glob("*_metrics.json"))
    if not files:
        return None
    newest = max(files, key=lambda p: p.stat().st_mtime)
    with open(newest) as f:
        data = json.load(f)
    value = data.get(METRIC_NAME)
    return float(value) if value is not None else None


def _build_report(reference: pd.DataFrame, current: pd.DataFrame) -> Any:
    """Build + run an Evidently Report (data drift + target drift). Evidently imported here."""
    from evidently import ColumnMapping
    from evidently.metric_preset import DataDriftPreset, TargetDriftPreset
    from evidently.report import Report

    mapping = ColumnMapping(
        target=TARGET,
        task="classification",
        categorical_features=categorical_features(reference),
    )
    report = Report(metrics=[DataDriftPreset(), TargetDriftPreset()])
    report.run(reference_data=reference, current_data=current, column_mapping=mapping)
    return report


def summarize_report(report_dict: dict[str, Any]) -> dict[str, Any]:
    """Pull the few headline numbers we care about out of Evidently's report dict.

    Evidently's JSON structure varies a little by version, so we scan defensively and
    fall back to None for anything we can't find.
    """
    out: dict[str, Any] = {
        "dataset_drift": None,
        "n_drifted_features": None,
        "n_features": None,
        "drift_share": None,
        "target_drift_detected": None,
        "target_drift_score": None,
    }
    for metric in report_dict.get("metrics", []):
        result = metric.get("result", {}) or {}
        if "dataset_drift" in result:  # DataDriftPreset summary
            out["dataset_drift"] = result.get("dataset_drift")
            out["n_drifted_features"] = result.get("number_of_drifted_columns")
            out["n_features"] = result.get("number_of_columns")
            out["drift_share"] = result.get("share_of_drifted_columns")
        if result.get("column_name") == TARGET and "drift_score" in result:  # target drift
            out["target_drift_detected"] = result.get("drift_detected")
            out["target_drift_score"] = result.get("drift_score")
    return out


def _as_float(value: Any) -> float | None:
    """Coerce numpy/None values to a plain Python float (keeps the JSON clean & serializable)."""
    return None if value is None else float(value)


def _as_int(value: Any) -> int | None:
    """Coerce numpy/None values to a plain Python int."""
    return None if value is None else int(value)


def _as_bool(value: Any) -> bool | None:
    return None if value is None else bool(value)


def build_contract(drift: dict[str, Any], f1: float | None, threshold: float, year: Any) -> dict[str, Any]:
    """Assemble the small, STABLE metrics JSON that downstream consumers will read.

    All numeric fields are coerced to plain Python types so the JSON is always
    serializable regardless of which numpy types Evidently returns.
    """
    f1 = _as_float(f1)
    passed = f1 is not None and f1 >= threshold
    return {
        "year": year,
        "dataset_drift": _as_bool(drift.get("dataset_drift")),
        "drift_share": _as_float(drift.get("drift_share")),
        "n_drifted_features": _as_int(drift.get("n_drifted_features")),
        "n_features": _as_int(drift.get("n_features")),
        "target_drift_detected": _as_bool(drift.get("target_drift_detected")),
        "target_drift_score": _as_float(drift.get("target_drift_score")),
        "f1_score": f1,
        "f1_threshold": threshold,
        "passed": passed,
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def run(processed_dir: Path = PROCESSED_DATA_DIR, metrics_dir: Path = METRIC_DIR) -> int:
    """Full drift step. Returns an exit code: 0 = pass, 1 = fail (blocks promotion)."""
    processed_dir = Path(processed_dir)
    reference_path = processed_dir / "reference_raw.csv"
    current_path = processed_dir / "current_raw.csv"

    if not reference_path.is_file() or not current_path.is_file():
        logger.error(
            f"Missing {reference_path.name} / {current_path.name}. Rebuild the dataset "
            "(make_dataset with overwrite=True) so the raw drift frames are created."
        )
        return 1

    year = DATA_PROCESSING_CONFIG.get("exclusive_test_year", "current")
    DRIFT_DIR.mkdir(parents=True, exist_ok=True)

    logger.info(f"Loading reference ({reference_path}) and current ({current_path}) ...")
    reference = pd.read_csv(reference_path)
    current = pd.read_csv(current_path)

    reference, current, dropped = reduce_for_drift(reference, current)
    logger.info(f"Drift on {reference.shape[1]} columns, ref={len(reference)} rows / cur={len(current)} rows (skipped high-cardinality: {dropped})")

    logger.info("Building Evidently drift report (data drift + target drift) ...")
    report = _build_report(reference, current)

    html_path = DRIFT_DIR / f"drift_report_{year}.html"
    json_path = DRIFT_DIR / f"drift_report_{year}.json"
    report.save_html(str(html_path))
    report_dict = report.as_dict()
    with open(json_path, "w") as f:
        json.dump(report_dict, f, indent=2, default=str)
    logger.info(f"Saved report -> {html_path.name}, {json_path.name}")

    drift = summarize_report(report_dict)
    threshold = f1_threshold()
    f1 = latest_f1(metrics_dir)
    contract = build_contract(drift, f1, threshold, year)

    with open(CONTRACT_FILE, "w") as f:
        json.dump(contract, f, indent=2)
    logger.info(f"Wrote contract -> {CONTRACT_FILE.name}: {contract}")

    # --- the quality gate ---------------------------------------------------
    if f1 is None:
        logger.error("No F1 found in artifacts/metrics/*_metrics.json — run training first.")
        return 1
    if f1 < threshold:
        logger.error(f"GATE FAILED: F1={f1:.4f} < threshold={threshold:.4f}. Blocking promotion.")
        return 1

    logger.info(f"GATE PASSED: F1={f1:.4f} >= threshold={threshold:.4f}.")
    return 0


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
