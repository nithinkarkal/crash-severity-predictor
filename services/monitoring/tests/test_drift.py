"""
Unit tests for the drift step (services.monitoring.drift).

Evidently is never imported here: the one function that uses it (`_build_report`)
is mocked, so these tests run in the normal suite with no heavy dependency. We test
the pure helpers (threshold, F1 read, report summary, contract) and the gate logic.
"""

import json
from unittest.mock import MagicMock, patch

import pandas as pd

from services.monitoring import drift


def _write_metrics(dirpath, f1):
    dirpath.mkdir(parents=True, exist_ok=True)
    (dirpath / "model_20260101000000_metrics.json").write_text(json.dumps({"accuracy": 0.8, "precision": 0.7, "recall": 0.7, "f1_score": f1}))


def _write_frames(dirpath):
    dirpath.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"atm": [1, 2, 1, 2], "nb_veh": [1, 2, 1, 2], "grav": [0, 1, 0, 1]}).to_csv(dirpath / "reference_raw.csv", index=False)
    pd.DataFrame({"atm": [2, 2, 1, 1], "nb_veh": [2, 2, 1, 1], "grav": [1, 1, 0, 0]}).to_csv(dirpath / "current_raw.csv", index=False)


def test_categorical_features_present_only():
    df = pd.DataFrame({"atm": [1], "col": [2], "nb_veh": [3], "grav": [0]})
    cats = drift.categorical_features(df)
    assert "atm" in cats and "col" in cats
    assert "nb_veh" not in cats and "grav" not in cats  # numeric + target excluded


def test_f1_threshold_env(monkeypatch):
    monkeypatch.setenv("ASP_F1_THRESHOLD", "0.7")
    assert drift.f1_threshold() == 0.7
    monkeypatch.setenv("ASP_F1_THRESHOLD", "not-a-number")
    assert drift.f1_threshold() == drift.DEFAULT_F1_THRESHOLD
    monkeypatch.delenv("ASP_F1_THRESHOLD", raising=False)
    assert drift.f1_threshold() == drift.DEFAULT_F1_THRESHOLD


def test_latest_f1_reads_newest(tmp_path):
    _write_metrics(tmp_path, 0.73)
    assert drift.latest_f1(tmp_path) == 0.73


def test_latest_f1_none_when_missing(tmp_path):
    assert drift.latest_f1(tmp_path) is None


def test_reduce_for_drift_drops_high_cardinality_and_samples():
    n = 300
    ref = pd.DataFrame(
        {
            "atm": [1, 2] * (n // 2),  # low cardinality -> kept
            "com": list(range(n)),  # 300 unique -> dropped (> MAX_CARDINALITY)
            "grav": [0, 1] * (n // 2),  # target -> always kept
        }
    )
    r, c, dropped = drift.reduce_for_drift(ref, ref.copy())
    assert "com" in dropped
    assert "atm" in r.columns and "grav" in r.columns and "com" not in r.columns

    big = pd.concat([ref] * 500, ignore_index=True)  # 150k rows
    rb, cb, _ = drift.reduce_for_drift(big, big)
    assert len(rb) == drift.SAMPLE_ROWS


def test_summarize_report():
    report_dict = {
        "metrics": [
            {"result": {"dataset_drift": True, "number_of_drifted_columns": 3, "number_of_columns": 10, "share_of_drifted_columns": 0.3}},
            {"result": {"column_name": "grav", "drift_detected": False, "drift_score": 0.12}},
        ]
    }
    s = drift.summarize_report(report_dict)
    assert s["dataset_drift"] is True
    assert s["n_drifted_features"] == 3
    assert s["drift_share"] == 0.3
    assert s["target_drift_detected"] is False
    assert s["target_drift_score"] == 0.12


def test_build_contract_pass_and_fail():
    d = {
        "dataset_drift": True,
        "drift_share": 0.2,
        "n_drifted_features": 2,
        "n_features": 10,
        "target_drift_detected": False,
        "target_drift_score": 0.1,
    }
    assert drift.build_contract(d, 0.90, 0.65, 2024)["passed"] is True
    assert drift.build_contract(d, 0.50, 0.65, 2024)["passed"] is False
    assert drift.build_contract(d, None, 0.65, 2024)["passed"] is False


@patch("services.monitoring.drift._build_report")
def test_run_gate_passes(mock_build, tmp_path, monkeypatch):
    proc, metrics, reports = tmp_path / "processed", tmp_path / "metrics", tmp_path / "drift"
    _write_frames(proc)
    _write_metrics(metrics, 0.80)
    monkeypatch.setattr(drift, "DRIFT_DIR", reports)
    monkeypatch.setattr(drift, "CONTRACT_FILE", reports / "latest_metrics.json")
    monkeypatch.delenv("ASP_F1_THRESHOLD", raising=False)

    fake = MagicMock()
    fake.as_dict.return_value = {
        "metrics": [{"result": {"dataset_drift": False, "number_of_drifted_columns": 0, "number_of_columns": 2, "share_of_drifted_columns": 0.0}}]
    }
    mock_build.return_value = fake

    assert drift.run(processed_dir=proc, metrics_dir=metrics) == 0
    contract = json.loads((reports / "latest_metrics.json").read_text())
    assert contract["passed"] is True
    assert contract["f1_score"] == 0.80
    fake.save_html.assert_called_once()


@patch("services.monitoring.drift._build_report")
def test_run_gate_fails_on_low_f1(mock_build, tmp_path, monkeypatch):
    proc, metrics, reports = tmp_path / "processed", tmp_path / "metrics", tmp_path / "drift"
    _write_frames(proc)
    _write_metrics(metrics, 0.40)
    monkeypatch.setattr(drift, "DRIFT_DIR", reports)
    monkeypatch.setattr(drift, "CONTRACT_FILE", reports / "latest_metrics.json")
    monkeypatch.delenv("ASP_F1_THRESHOLD", raising=False)

    fake = MagicMock()
    fake.as_dict.return_value = {"metrics": []}
    mock_build.return_value = fake

    assert drift.run(processed_dir=proc, metrics_dir=metrics) == 1


def test_run_fails_when_frames_missing(tmp_path):
    assert drift.run(processed_dir=tmp_path / "nope", metrics_dir=tmp_path) == 1
