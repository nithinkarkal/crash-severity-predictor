"""Tests for metrics registry."""

import json
from pathlib import Path
from unittest.mock import patch

from services.backend.src.core import metrics


def test_refresh_drift_metrics_missing_contract(tmp_path: Path) -> None:
    """Missing contract file should be ignored without raising an exception."""

    contract_path = tmp_path / "latest_metrics.json"

    with patch.object(metrics, "CONTRACT_FILE", contract_path):
        metrics.refresh_drift_metrics("model-v1")

    # The function should simply return when no contract exists.
    assert not contract_path.exists()


def test_refresh_drift_metrics_updates_all_gauges(tmp_path: Path) -> None:
    """A complete contract updates all drift-related gauges."""

    contract_path = tmp_path / "latest_metrics.json"
    contract = {
        "f1_score": 0.82,
        "drift_share": 0.25,
        "dataset_drift": True,
    }
    contract_path.write_text(json.dumps(contract))

    with patch.object(metrics, "CONTRACT_FILE", contract_path):
        metrics.refresh_drift_metrics("model-v1")

    assert metrics.model_f1_score.labels(model_version="model-v1")._value.get() == 0.82
    assert metrics.model_drift_share.labels(model_version="model-v1")._value.get() == 0.25
    assert metrics.model_dataset_drift_detected.labels(model_version="model-v1")._value.get() == 1


def test_refresh_drift_metrics_dataset_drift_false(tmp_path: Path) -> None:
    """dataset_drift=False should be exported as 0."""

    contract_path = tmp_path / "latest_metrics.json"
    contract = {
        "f1_score": 0.75,
        "drift_share": 0.10,
        "dataset_drift": False,
    }
    contract_path.write_text(json.dumps(contract))

    with patch.object(metrics, "CONTRACT_FILE", contract_path):
        metrics.refresh_drift_metrics("model-v2")

    assert metrics.model_f1_score.labels(model_version="model-v2")._value.get() == 0.75
    assert metrics.model_drift_share.labels(model_version="model-v2")._value.get() == 0.10
    assert metrics.model_dataset_drift_detected.labels(model_version="model-v2")._value.get() == 0


def test_refresh_drift_metrics_partial_contract(tmp_path: Path) -> None:
    """Only metrics present in the contract should be updated."""

    contract_path = tmp_path / "latest_metrics.json"
    contract = {
        "f1_score": 0.91,
    }
    contract_path.write_text(json.dumps(contract))

    with patch.object(metrics, "CONTRACT_FILE", contract_path):
        metrics.refresh_drift_metrics("model-partial")

    assert metrics.model_f1_score.labels(model_version="model-partial")._value.get() == 0.91


def test_refresh_drift_metrics_empty_contract(tmp_path: Path) -> None:
    """An empty contract should not update any gauges."""

    contract_path = tmp_path / "latest_metrics.json"
    contract_path.write_text("{}")

    with patch.object(metrics, "CONTRACT_FILE", contract_path):
        metrics.refresh_drift_metrics("model-empty")

    # No values should be created for this model version because the
    # contract contains none of the supported metrics.
    assert "model-empty" not in metrics.model_f1_score._metrics
    assert "model-empty" not in metrics.model_drift_share._metrics
    assert "model-empty" not in metrics.model_dataset_drift_detected._metrics


def test_refresh_drift_metrics_invalid_json(tmp_path: Path) -> None:
    """Invalid JSON should be ignored without raising an exception."""

    contract_path = tmp_path / "latest_metrics.json"
    contract_path.write_text("{invalid json")

    with patch.object(metrics, "CONTRACT_FILE", contract_path):
        metrics.refresh_drift_metrics("model-invalid")

    assert "model-invalid" not in metrics.model_f1_score._metrics


def test_refresh_drift_metrics_read_error(tmp_path: Path) -> None:
    """An OSError while reading the contract should be handled gracefully."""

    contract_path = tmp_path / "latest_metrics.json"

    with patch.object(metrics, "CONTRACT_FILE", contract_path):
        with patch("builtins.open", side_effect=OSError("permission denied")):
            metrics.refresh_drift_metrics("model-error")

    assert "model-error" not in metrics.model_f1_score._metrics


def test_refresh_drift_metrics_uses_supplied_model_version(
    tmp_path: Path,
) -> None:
    """Metrics should be labelled with the supplied backend model version."""

    contract_path = tmp_path / "latest_metrics.json"
    contract = {
        "f1_score": 0.88,
        "drift_share": 0.15,
        "dataset_drift": True,
    }
    contract_path.write_text(json.dumps(contract))

    with patch.object(metrics, "CONTRACT_FILE", contract_path):
        metrics.refresh_drift_metrics("accident-severity-predictor@production (v7)")

    assert metrics.model_f1_score.labels(model_version="accident-severity-predictor@production (v7)")._value.get() == 0.88
