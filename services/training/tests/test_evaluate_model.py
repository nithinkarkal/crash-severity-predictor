"""
Tests for evaluate_model
"""

from pathlib import Path

import joblib
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestClassifier

from services.training.src.evaluate_model import _latest_model_path, run_evaluation


@pytest.fixture
def eval_setup(tmp_path: Path) -> tuple[Path, Path, Path, Path, str]:
    model_dir = tmp_path / "models"
    model_dir.mkdir()

    # create model
    x = pd.DataFrame({"f1": [1.0, 3.0, 5.0, 7.0], "f2": [2.0, 4.0, 6.0, 8.0]})
    y = pd.Series([0, 1, 0, 1])
    model = RandomForestClassifier(n_estimators=10, random_state=42)
    model.fit(x, y)
    joblib.dump(model, model_dir / "test_model_20260721120000.joblib")

    # test data
    proc = tmp_path / "processed"
    proc.mkdir()
    pd.DataFrame({"f1": [1.0, 3.0, 5.0], "f2": [2.0, 4.0, 6.0]}).to_csv(proc / "X_test.csv", index=False)
    pd.Series([0, 1, 0]).to_csv(proc / "y_test.csv", index=False)

    # output dirs
    metrics_dir = tmp_path / "metrics"
    reports_dir = tmp_path / "reports"
    metrics_dir.mkdir()
    reports_dir.mkdir()

    return proc, model_dir, metrics_dir, reports_dir, "test_model"


@pytest.fixture
def versioned_models(tmp_path: Path) -> Path:
    """create multiple versioned models."""
    model_dir = tmp_path / "models"
    model_dir.mkdir()

    x = [[1, 2], [3, 4]]
    y = [0, 1]

    for i in range(3):
        model = RandomForestClassifier(n_estimators=5, random_state=i)
        model.fit(x, y)
        joblib.dump(model, model_dir / f"model_20260720{i:02d}0000.joblib")

        import time

        time.sleep(0.5)  # ensure different mtimes

    return model_dir


def test_latest_model_path_versioned(versioned_models: Path) -> None:
    """return most recent versioned model."""
    path = _latest_model_path(versioned_models, "model")
    assert "model_" in path.name
    assert path.name.endswith(".joblib")


def test_latest_model_path_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        _latest_model_path(tmp_path, "nonexistent")


def test_eval_returns_all(eval_setup: tuple) -> None:
    proc, m_dir, met_dir, rep_dir, name = eval_setup
    eval_out = run_evaluation(name, proc, m_dir, met_dir, rep_dir)
    assert isinstance(eval_out["metrics"], dict)
    assert isinstance(eval_out["artifacts"], dict)
    assert "accuracy" in eval_out["metrics"]
    assert "precision" in eval_out["metrics"]
    assert "recall" in eval_out["metrics"]
    assert "f1_score" in eval_out["metrics"]
    assert "confusion_matrix" in eval_out["artifacts"]


def test_eval_saves_metrics_json(eval_setup: tuple) -> None:
    proc, m_dir, met_dir, rep_dir, name = eval_setup
    run_evaluation(name, proc, m_dir, met_dir, rep_dir)
    assert any(met_dir.glob("*_metrics.json"))


def test_eval_saves_confusion_matrix(eval_setup: tuple) -> None:
    proc, m_dir, met_dir, rep_dir, name = eval_setup
    run_evaluation(name, proc, m_dir, met_dir, rep_dir)
    assert any(rep_dir.glob("*_confusion_matrix.png"))


def test_eval_metrics_are_floats_0_to_1(eval_setup: tuple) -> None:
    proc, m_dir, met_dir, rep_dir, name = eval_setup
    eval_out = run_evaluation(name, proc, m_dir, met_dir, rep_dir)
    for v in eval_out["metrics"].values():
        assert isinstance(v, float)
        assert 0 <= v <= 1


def test_eval_missing_model(eval_setup: tuple, tmp_path: Path) -> None:
    proc, _, met_dir, rep_dir, _ = eval_setup
    with pytest.raises(FileNotFoundError):
        run_evaluation("missing", proc, tmp_path / "empty", met_dir, rep_dir)


def test_eval_missing_test_data(eval_setup: tuple, tmp_path: Path) -> None:
    _, m_dir, met_dir, rep_dir, name = eval_setup
    with pytest.raises(FileNotFoundError):
        run_evaluation(name, tmp_path / "empty", m_dir, met_dir, rep_dir)
