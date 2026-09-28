from pathlib import Path

import pytest

from common.utils.paths import (
    API_CONFIG,
    ARTIFACTS_DIR,
    DATA_DIR,
    DATA_PROCESSING_CONFIG,
    MODEL_CONFIG,
    MODEL_DIR,
    PROCESSED_DATA_DIR,
    PROJECT_ROOT,
    RAW_DATA_DIR,
    REQUIRED_DIRS,
)


def test_project_root_is_absolute() -> None:
    assert PROJECT_ROOT.is_absolute()


def test_project_root_contains_common() -> None:
    assert (PROJECT_ROOT / "common").exists()


def test_data_dir_is_child_of_root() -> None:
    assert PROCESSED_DATA_DIR.is_relative_to(DATA_DIR)
    assert RAW_DATA_DIR.is_relative_to(DATA_DIR)


def test_model_dir_is_child_of_artifacts() -> None:
    assert (ARTIFACTS_DIR / "models").is_relative_to(ARTIFACTS_DIR)


def test_required_dirs_not_empty() -> None:
    assert len(REQUIRED_DIRS) > 0


@pytest.mark.parametrize("expected", [RAW_DATA_DIR, PROCESSED_DATA_DIR, MODEL_DIR])
def test_required_dirs_contains(expected: Path) -> None:
    assert expected in REQUIRED_DIRS


def test_api_config_has_url() -> None:
    assert API_CONFIG["dataset_url"].startswith("https://")


def test_data_processing_years_are_integers() -> None:
    assert all(isinstance(y, int) for y in DATA_PROCESSING_CONFIG["years"])


def test_data_processing_test_size_valid() -> None:
    assert 0 < DATA_PROCESSING_CONFIG["test_size"] < 1


def test_model_config_has_name() -> None:
    assert isinstance(MODEL_CONFIG["model_name"], str)
    assert len(MODEL_CONFIG["model_name"]) > 0


def test_model_config_has_registry_name() -> None:
    assert isinstance(MODEL_CONFIG["model_registry_name"], str)
    assert len(MODEL_CONFIG["model_registry_name"]) > 0


def test_model_config_top_n_positive() -> None:
    assert MODEL_CONFIG["top_n_features"] > 0
