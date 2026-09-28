"""
Tests for clean_data
"""

import pandas as pd
import pytest

from common.data.clean_data import (
    clean_object_columns,
    correct_id_anomaly,
    process_characteristics,
    process_places,
    process_users,
    process_vehicles,
)


@pytest.fixture
def users_df():
    return pd.DataFrame(
        {
            "Num_Acc": [2021000001, 2021000001, 2021000002],
            "num_veh": ["A01", "B01", "A02"],
            "id_vehicule": [1, 2, 1],
            "grav": [1, 2, 3],
            "an_nais": [1990, 1985, 2000],
            "place": [1, 2, 1],
            "catu": [1, 1, 1],
            "sexe": [1, 2, 1],
            "trajet": [1, 1, 1],
            "secu1": [1, 1, 1],
        }
    )


@pytest.fixture
def vehicles_df():
    return pd.DataFrame(
        {
            "Num_Acc": [2021000001, 2021000001, 2021000002],
            "num_veh": ["A01", "B01", "A02"],
            "id_vehicule": [1, 2, 1],
            "catv": [1, 7, 99],  # mapping: 1->1, 7->2, 99->0
            "motor": [1, 1, 1],
            "obsm": [1, 1, 1],
        }
    )


@pytest.fixture
def characteristics_df():
    return pd.DataFrame(
        {
            "Num_Acc": [2021000001, 2021000002],
            "dep": ["75", "2A"],
            "com": ["75001", "2A001"],
            "hrmn": ["08:30", "14:45"],
            "an": [2021, 2021],
            "lat": ["48.8566", "41.9260"],
            "long": ["2.3522", "8.7376"],
            "atm": [1, 2],
        }
    )


def test_correct_id_anomaly():
    df = pd.DataFrame({"Accident_Id": [1, 2], "col": ["a", "b"]})
    result = correct_id_anomaly(df)
    assert "Num_Acc" in result.columns
    assert "Accident_Id" not in result.columns


def test_correct_id_anomaly_no_change():
    df = pd.DataFrame({"Num_Acc": [1, 2], "col": ["a", "b"]})
    result = correct_id_anomaly(df)
    assert list(result.columns) == ["Num_Acc", "col"]


def test_clean_object_columns():
    df = pd.DataFrame({"text": ["not\xa0clean", "normal"], "num": [1, 2]})
    result = clean_object_columns(df)
    assert result["text"].iloc[0] == "notclean"
    assert result["text"].iloc[1] == "normal"


def test_process_users_gravity_mapping(users_df):
    result = process_users(users_df)
    assert list(result["grav"]) == [0, 1, 1]


def test_process_users_victim_age(users_df):
    result = process_users(users_df)
    assert result["victim_age"].iloc[0] == 31
    assert "an_nais" not in result.columns


def test_process_users_outlier_age():
    df = pd.DataFrame(
        {
            "Num_Acc": [2021000001],
            "num_veh": ["A"],
            "id_vehicule": [1],
            "grav": [1],
            "an_nais": [1800],
            "place": [1],
            "catu": [1],
            "sexe": [1],
            "trajet": [1],
            "secu1": [1],
        }
    )
    result = process_users(df)
    assert pd.isna(result["victim_age"].iloc[0])


def test_process_users_victim_count(users_df):
    result = process_users(users_df)
    assert result["nb_victim"].iloc[0] == 2
    assert result["nb_victim"].iloc[2] == 1


def test_process_vehicles_category(vehicles_df):
    result = process_vehicles(vehicles_df)
    assert list(result["catv"]) == [1, 2, 0]


def test_process_vehicles_count(vehicles_df):
    result = process_vehicles(vehicles_df)
    assert result["nb_vehicles"].iloc[0] == 2
    assert result["nb_vehicles"].iloc[2] == 1


def test_process_characteristics_corsica(characteristics_df):
    result = process_characteristics(characteristics_df)
    assert result["dep"].iloc[0] == 75
    assert result["dep"].iloc[1] == 201


def test_process_characteristics_hour(characteristics_df):
    result = process_characteristics(characteristics_df)
    assert result["hour"].iloc[0] == 8
    assert result["hour"].iloc[1] == 14


def test_process_characteristics_coordinates(characteristics_df):
    result = process_characteristics(characteristics_df)
    assert result["lat"].iloc[0] == 48.8566
    assert result["long"].iloc[1] == 8.7376


def test_process_characteristics_weather(characteristics_df):
    result = process_characteristics(characteristics_df)
    assert result["atm"].iloc[0] == 0
    assert result["atm"].iloc[1] == 1


def test_process_places():
    df = pd.DataFrame({"Num_Acc": [1, 2], "catr": [1, 2]})
    result = process_places(df)
    assert len(result) == 2
    assert "Num_Acc" in result.columns
