"""
Unit tests for the data-quality gate used by the retraining DAG's `validate_data`
task (`infra/airflow/scripts/validate_data.py`).

The script is standalone (imports nothing from the project) and reads its CSVs from
a module-level ``PROCESSED`` path, exiting non-zero on the first failed check. We load
it by file path and point ``PROCESSED`` at a tmp dir, then exercise the pass case plus
each failure branch. No Airflow needed — this is plain pandas.
"""

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_data.py"


def _load_script():
    """Import validate_data.py by path (it is a script, not a package module)."""
    spec = importlib.util.spec_from_file_location("validate_data_under_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_valid_dataset(folder: Path) -> None:
    """Write a minimal, internally consistent processed dataset."""
    folder.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"f1": [1, 2, 3, 4], "f2": [5, 6, 7, 8]}).to_csv(folder / "X_train.csv", index=False)
    pd.DataFrame({"f1": [9, 10], "f2": [11, 12]}).to_csv(folder / "X_test.csv", index=False)
    pd.DataFrame({"target": [0, 1, 0, 1]}).to_csv(folder / "y_train.csv", index=False)
    pd.DataFrame({"target": [1, 0]}).to_csv(folder / "y_test.csv", index=False)


@pytest.fixture
def validate(tmp_path, monkeypatch):
    """Return (module, processed_dir) with PROCESSED pointed at a fresh tmp dir."""
    module = _load_script()
    processed = tmp_path / "processed"
    monkeypatch.setattr(module, "PROCESSED", processed)
    return module, processed


def test_valid_dataset_passes(validate) -> None:
    module, processed = validate
    _write_valid_dataset(processed)
    # main() returns cleanly (no SystemExit) when everything is valid.
    module.main()


def test_missing_file_fails(validate) -> None:
    module, processed = validate
    _write_valid_dataset(processed)
    (processed / "y_test.csv").unlink()
    with pytest.raises(SystemExit):
        module.main()


def test_empty_dataset_fails(validate) -> None:
    module, processed = validate
    _write_valid_dataset(processed)
    pd.DataFrame({"f1": [], "f2": []}).to_csv(processed / "X_train.csv", index=False)
    pd.DataFrame({"target": []}).to_csv(processed / "y_train.csv", index=False)
    with pytest.raises(SystemExit):
        module.main()


def test_row_count_mismatch_fails(validate) -> None:
    module, processed = validate
    _write_valid_dataset(processed)
    # y_train now has 3 rows vs X_train's 4
    pd.DataFrame({"target": [0, 1, 0]}).to_csv(processed / "y_train.csv", index=False)
    with pytest.raises(SystemExit):
        module.main()


def test_column_mismatch_fails(validate) -> None:
    module, processed = validate
    _write_valid_dataset(processed)
    # X_test has a different feature schema than X_train
    pd.DataFrame({"f1": [9, 10], "DIFFERENT": [11, 12]}).to_csv(processed / "X_test.csv", index=False)
    with pytest.raises(SystemExit):
        module.main()


def test_non_binary_target_fails(validate) -> None:
    module, processed = validate
    _write_valid_dataset(processed)
    # target contains a 2 -> not the expected {0, 1}
    pd.DataFrame({"target": [0, 1, 2, 1]}).to_csv(processed / "y_train.csv", index=False)
    with pytest.raises(SystemExit):
        module.main()
