"""
Tests for the model-promotion step (services.training.promote).

These cover the DAG's STEP 5 (compare) and STEP 6 (promote) logic. All MLflow
access is mocked — no network, no registry, no DagsHub.
"""

import json
from unittest.mock import MagicMock, patch

from mlflow.exceptions import MlflowException

from services.training import promote as promote_mod


def _version(number: str, run_id: str = "run-x") -> MagicMock:
    v = MagicMock()
    v.version = number
    v.run_id = run_id
    return v


def test_latest_candidate_version_picks_highest() -> None:
    """The candidate is the highest-numbered registered version."""

    client = MagicMock()
    client.search_model_versions.return_value = [
        _version("1"),
        _version("3"),
        _version("2"),
    ]

    result = promote_mod.latest_candidate_version(client, "accident-severity-predictor")

    assert result.version == "3"
    client.search_model_versions.assert_called_once_with("name='accident-severity-predictor'")


def test_current_production_metric_none_when_no_alias() -> None:
    """No production alias yet -> None (so the candidate wins by default)."""

    client = MagicMock()
    client.get_model_version_by_alias.side_effect = MlflowException("not found")

    assert promote_mod.current_production_metric(client, "m") is None


def test_current_production_metric_reads_run() -> None:
    """The champion's metric is read from its producing run."""

    client = MagicMock()
    client.get_model_version_by_alias.return_value = _version("2", run_id="run-2")

    run = MagicMock()
    run.data.metrics = {"f1_score": 0.8}
    client.get_run.return_value = run

    assert promote_mod.current_production_metric(client, "m") == 0.8
    client.get_run.assert_called_once_with("run-2")


@patch("services.training.promote.latest_metrics")
@patch("services.training.promote.MlflowClient")
@patch("services.training.promote.setup_mlflow")
def test_compare_no_production_returns_true(
    mock_setup,
    mock_client_cls,
    mock_latest_metrics,
    tmp_path,
    monkeypatch,
) -> None:
    """With no current production model, compare() is True and writes a decision file."""

    client = MagicMock()
    mock_client_cls.return_value = client
    client.search_model_versions.return_value = [_version("1")]
    client.get_model_version_by_alias.side_effect = MlflowException("none")
    mock_latest_metrics.return_value = {"f1_score": 0.9}

    decision_file = tmp_path / "promotion_decision.json"
    monkeypatch.setattr(promote_mod, "DECISION_FILE", decision_file)

    assert promote_mod.compare() is True

    written = json.loads(decision_file.read_text())
    assert written["is_better"] is True
    assert written["current_metric"] is None
    assert written["candidate_version"] == "1"


@patch("services.training.promote.latest_metrics")
@patch("services.training.promote.MlflowClient")
@patch("services.training.promote.setup_mlflow")
def test_compare_worse_returns_false(
    mock_setup,
    mock_client_cls,
    mock_latest_metrics,
    tmp_path,
    monkeypatch,
) -> None:
    """A weaker candidate -> compare() is False."""

    client = MagicMock()
    mock_client_cls.return_value = client
    client.search_model_versions.return_value = [_version("3", run_id="run-3")]
    client.get_model_version_by_alias.return_value = _version("2", run_id="run-2")
    run = MagicMock()
    run.data.metrics = {"f1_score": 0.95}
    client.get_run.return_value = run
    mock_latest_metrics.return_value = {"f1_score": 0.90}

    monkeypatch.setattr(promote_mod, "DECISION_FILE", tmp_path / "d.json")

    assert promote_mod.compare() is False


@patch("services.training.promote.promote_if_better")
@patch("services.training.promote.latest_metrics")
@patch("services.training.promote.MlflowClient")
@patch("services.training.promote.setup_mlflow")
def test_promote_calls_promote_if_better(
    mock_setup,
    mock_client_cls,
    mock_latest_metrics,
    mock_promote_if_better,
) -> None:
    """promote() delegates to the tested promote_if_better helper with the candidate."""

    client = MagicMock()
    mock_client_cls.return_value = client
    candidate = _version("3")
    client.search_model_versions.return_value = [candidate]
    mock_latest_metrics.return_value = {"f1_score": 0.9}
    mock_promote_if_better.return_value = True

    assert promote_mod.promote() is True

    mock_promote_if_better.assert_called_once_with(
        registered_version=candidate,
        eval_out={"metrics": {"f1_score": 0.9}},
        registry_model_name="accident-severity-predictor",
        metric_name="f1_score",
    )
