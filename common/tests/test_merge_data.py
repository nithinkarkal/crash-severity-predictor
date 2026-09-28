"""
Tests for merge_data
"""

import numpy as np
import pandas as pd
import pytest

from common.data.merge_data import (
    collect_raw_data_paths,
    merge_datasets,
    process_features,
    process_merged_dataset,
    save_datasets,
    split_data,
)


@pytest.fixture
def users_df():
    return pd.DataFrame(
        {
            "Num_Acc": [1, 1, 2],
            "num_veh": ["A", "B", "A"],
            "id_vehicule": [1, 2, 1],
            "grav": [0, 1, 0],
        }
    )


@pytest.fixture
def vehicles_df():
    return pd.DataFrame(
        {
            "Num_Acc": [1, 1, 2],
            "num_veh": ["A", "B", "A"],
            "id_vehicule": [1, 2, 1],
            "catv": [1, 2, 5],
        }
    )


@pytest.fixture
def places_df():
    return pd.DataFrame({"Num_Acc": [1, 2], "catr": [1, 2]})


@pytest.fixture
def characteristics_df():
    return pd.DataFrame({"Num_Acc": [1, 2], "dep": [75, 13]})


@pytest.fixture
def year_data():
    return {
        2021: pd.DataFrame({"grav": [0, 1, 0], "feat1": [1, 2, 3]}),
        2022: pd.DataFrame({"grav": [0, 1], "feat1": [4, 5]}),
    }


def test_collect_raw_data_paths(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    for year in [2021, 2022]:
        for table in ["caracteristiques", "usagers", "vehicules", "lieux"]:
            (raw / f"{table}-{year}.csv").touch()

    paths = collect_raw_data_paths(raw)
    assert "car" in paths
    assert paths["car"][2021] is not None


def test_collect_raw_data_paths_empty(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    paths = collect_raw_data_paths(empty)
    assert len(paths) == 0


def test_merge_datasets(users_df, vehicles_df, places_df, characteristics_df):
    result = merge_datasets(users_df, vehicles_df, places_df, characteristics_df)
    assert len(result) == 2


def test_merge_deduplicates_by_severity(users_df, vehicles_df, places_df, characteristics_df):
    result = merge_datasets(users_df, vehicles_df, places_df, characteristics_df)
    accident1 = result[result["Num_Acc"] == 1]
    assert len(accident1) == 1
    assert accident1["grav"].iloc[0] == 1  # Higher severity kept


def test_process_merged_replaces_sentinels():
    df = pd.DataFrame(
        {
            "grav": [0, 1],
            "catv": [0, 5],
            "secu1": [1, -1],
            "motor": [0, -1],
            "circ": [1, 1],
            "surf": [1, 1],
            "situ": [1, 1],
            "vma": [1, 1],
            "atm": [1, 1],
            "col": [1, 1],
            # added col below to solve key error:
            # KeyError: "['senc', 'larrout', 'actp', 'manv',...
            "trajet": [1, 1],
            "obsm": [1, 1],
            "senc": [1, 1],
            "larrout": [1.0, 1.0],
            "actp": [1, 1],
            "manv": [1, 1],
            "choc": [1, 1],
            "nbv": [1, 1],
            "prof": [1, 1],
            "plan": [1, 1],
            "Num_Acc": [1, 2],
            "id_vehicule": [1, 2],
            "num_veh": ["A", "B"],
            "pr": [1, 1],
            "pr1": [1, 1],
            "voie": [1, 1],
            "secu2": [1, 1],
            "secu3": [1, 1],
            "adr": ["a", "b"],
            "v1": [1, 1],
            "lartpc": [1.0, 1.0],
            "occutc": [1, 1],
            "v2": [1, 1],
            "vosp": [1, 1],
            "locp": [1, 1],
            "etatp": [1, 1],
            "infra": [1, 1],
            "obs": [1, 1],
        }
    )
    result = process_merged_dataset(df)

    assert pd.isna(result["catv"].iloc[0])  # 0 -> NaN
    assert result["catv"].iloc[1] == 5  # 1 -> 5
    assert pd.isna(result["secu1"].iloc[1])  # -1 -> NaN
    assert result["secu1"].iloc[0] == 1  # 0 -> 1
    assert pd.isna(result["motor"].iloc[0])  # 0 -> NaN
    assert pd.isna(result["motor"].iloc[1])  # -1 -> NaN


def test_split_data_exclusive_year(year_data):
    X_train, X_test, y_train, y_test = split_data(year_data, exclusive_test_year=2022)
    assert len(X_test) == 2
    assert len(X_train) == 3


def test_split_data_random(year_data):
    X_train, X_test, y_train, y_test = split_data(year_data, test_size=0.4, random_state=42)
    assert len(X_train) + len(X_test) == 5


def test_process_features_imputation():
    X_train = pd.DataFrame(
        {
            "place": [1, 2, np.nan],  # CAT_COLS
            "catu": [1, 1, np.nan],
            "num_feat": [1.0, np.nan, 3.0],  # num
        }
    )
    X_test = pd.DataFrame(
        {
            "place": [np.nan, 2],
            "catu": [1, np.nan],
            "num_feat": [np.nan, 2.0],
        }
    )

    X_tr, X_te = process_features(X_train, X_test)
    assert not X_tr.isnull().any().any()
    assert not X_te.isnull().any().any()


def test_save_datasets(tmp_path):
    X_train = pd.DataFrame({"a": [1, 2]})
    X_test = pd.DataFrame({"a": [3]})
    y_train = pd.Series([0, 1])
    y_test = pd.Series([0])

    out = tmp_path / "processed"
    out.mkdir(parents=True, exist_ok=True)
    save_datasets(X_train, X_test, y_train, y_test, out)

    assert (out / "X_train.csv").exists()
    assert (out / "X_test.csv").exists()
    assert (out / "y_train.csv").exists()
    assert (out / "y_test.csv").exists()
