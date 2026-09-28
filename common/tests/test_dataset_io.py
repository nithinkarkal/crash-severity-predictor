"""
Tests for dataset_io
"""

import pandas as pd
import pytest

from common.data.dataset_io import load_processed_csv, load_raw_csv


@pytest.fixture
def raw_csv(tmp_path):
    path = tmp_path / "raw.csv"
    pd.DataFrame({"a": [1, 2], "b": ["x;y", "z"]}).to_csv(path, sep=";", index=False)
    return path


@pytest.fixture
def processed_csv(tmp_path):
    path = tmp_path / "processed.csv"
    pd.DataFrame({"feat": [0.1, 0.2], "target": [0, 1]}).to_csv(path, index=False)
    return path


def test_load_raw_csv(raw_csv):
    df = load_raw_csv(raw_csv)
    assert len(df) == 2
    assert list(df.columns) == ["a", "b"]


def test_load_raw_csv_semicolon(raw_csv):
    df = load_raw_csv(raw_csv)
    assert df["b"].iloc[0] == "x;y"


def test_load_raw_csv_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_raw_csv(tmp_path / "nope.csv")


def test_load_processed_csv(processed_csv):
    df = load_processed_csv(processed_csv)
    assert len(df) == 2
    assert df["feat"].iloc[0] == 0.1


def test_load_processed_csv_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_processed_csv(tmp_path / "nope.csv")
