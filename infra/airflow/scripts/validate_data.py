"""
Data-quality validation for the ASP processed dataset.

Runs inside the asp-airflow-runner container (which has pandas). The DAG bind-mounts
the repo's data/ folder to /data, so this script reads /data/processed/*.csv.

It performs a series of simple, readable checks and EXITS NON-ZERO on the first
failure — which makes the Airflow task go red, stopping the pipeline before a bad
dataset is trained on. Prints a green summary if everything passes.

This is a STANDALONE script (it imports nothing from the project) so it stays
decoupled and easy to run/understand on its own.
"""

import sys
from pathlib import Path

import pandas as pd

# Where the DAG mounts the processed data (see asp_retraining_dag.py).
PROCESSED = Path("/data/processed")
REQUIRED_FILES = ["X_train.csv", "X_test.csv", "y_train.csv", "y_test.csv"]


def fail(message: str) -> None:
    """Print an error and exit non-zero (fails the Airflow task)."""
    print(f"[VALIDATION] FAIL: {message}")
    sys.exit(1)


def main() -> None:
    print(f"[VALIDATION] checking {PROCESSED} ...")

    # 1) all four files must exist
    for name in REQUIRED_FILES:
        if not (PROCESSED / name).is_file():
            fail(f"missing file: {name}")

    x_train = pd.read_csv(PROCESSED / "X_train.csv")
    x_test = pd.read_csv(PROCESSED / "X_test.csv")
    y_train = pd.read_csv(PROCESSED / "y_train.csv")
    y_test = pd.read_csv(PROCESSED / "y_test.csv")

    # 2) datasets must not be empty
    if len(x_train) == 0 or len(x_test) == 0:
        fail("x_train or x_test is empty")

    # 3) features and labels must have matching row counts
    if len(x_train) != len(y_train):
        fail(f"row mismatch: x_train={len(x_train)} vs y_train={len(y_train)}")
    if len(x_test) != len(y_test):
        fail(f"row mismatch: x_test={len(x_test)} vs y_test={len(y_test)}")

    # 4) train and test must have the SAME feature columns, in the same order
    if list(x_train.columns) != list(x_test.columns):
        fail("x_train and x_test have different columns")

    # 5) no feature column may be entirely null
    all_null = x_train.columns[x_train.isna().all()].tolist()
    if all_null:
        fail(f"columns are entirely null: {all_null}")

    # 6) the target must be the expected binary {0, 1}
    target_values = set(pd.unique(y_train.iloc[:, 0]))
    if not target_values.issubset({0, 1}):
        fail(f"unexpected target values (expected 0/1): {sorted(target_values)}")

    print(f"[VALIDATION] PASS: x_train={x_train.shape}, x_test={x_test.shape}, features={x_train.shape[1]}, target_classes={sorted(target_values)}")


if __name__ == "__main__":
    main()
