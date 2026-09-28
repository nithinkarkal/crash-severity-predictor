"""
cleaning functions for each raw data table: caracteristiques, lieux, vehicules, usagers.
"""

import numpy as np
import pandas as pd


def correct_id_anomaly(df: pd.DataFrame) -> pd.DataFrame:
    """correct the 2022 Accident_id anomaly"""
    if df.get("Accident_Id", None) is not None:
        df["Num_Acc"] = df.Accident_Id
        df = df.drop(columns=["Accident_Id"])

    return df

def clean_object_columns(df:pd.DataFrame) -> pd.DataFrame:
    """"get rid of non-breaking spaces"""
    obj_cols = df.select_dtypes(include=[object, "string"]).columns
    df[obj_cols] = df[obj_cols].apply(
        lambda s: s.str.replace("\xa0", "", regex=False).str.strip()
    )
    return df


def process_users(df: pd.DataFrame) -> pd.DataFrame:
    """clean raw usagers csv"""
    df = correct_id_anomaly(df)
    df = clean_object_columns(df)

    # Target: 1 Unharmed, 2 Killed, 3 Injured(hosp.), 4 Lightly injured
    # -> 0: Unharmed/Lightly injured, 1: Injured(hosp.)/Killed
    df["grav"] = df["grav"].replace([1, 2, 3, 4], [0, 1, 1, 0])

    df["year_acc"] = df["Num_Acc"].astype(str).str[:4].astype(int)
    df["victim_age"] = df["year_acc"] - df["an_nais"]
    df.loc[(df["victim_age"] > 120) | (df["victim_age"] < 0), "victim_age"] = np.nan

    # drop birth col
    df = df.drop(columns=["an_nais"])

    nb_victim = df.groupby("Num_Acc").size().rename("nb_victim")
    df = df.merge(nb_victim, on="Num_Acc", how="inner")

    return df


def process_vehicles(df: pd.DataFrame) -> pd.DataFrame:
    """clean raw vehicules csv."""
    df = correct_id_anomaly(df)
    df = clean_object_columns(df)

    catv_value = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20,
                  21, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 50, 60, 80, 99]
    catv_value_new = [0, 1, 1, 2, 1, 1, 6, 2, 5, 5, 5, 5, 5, 4, 4, 4, 4, 4, 3, 3, 4, 4, 1, 1,
                      1, 1, 1, 6, 6, 3, 3, 3, 3, 1, 1, 1, 1, 1, 0, 0]
    df["catv"] = df["catv"].replace(catv_value, catv_value_new)

    nb_vehicles = df.groupby("Num_Acc").size().rename("nb_vehicles")
    df = df.merge(nb_vehicles, on="Num_Acc", how="inner")

    return df


def process_characteristics(df: pd.DataFrame) -> pd.DataFrame:
    """clean raw caracteristiques csv."""
    df = correct_id_anomaly(df)
    df = clean_object_columns(df)

    df["dep"] = df["dep"].str.replace("2A", "201").str.replace("2B", "202")
    df["com"] = df["com"].str.replace("2A", "201").str.replace("2B", "202")

    df["hour"] = df["hrmn"].astype(str).str[:-3]
    df = df.drop(columns=["hrmn", "an"])

    cols = ["dep", "com", "hour"]
    df[cols] = df[cols].apply(pd.to_numeric, errors="coerce").astype("Int64")

    df["lat"] = df["lat"].str.replace(",", ".").astype(float)
    df["long"] = df["long"].str.replace(",", ".").astype(float)

    weather_map = {1: 0, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 1, 8: 0, 9: 0}
    df["atm"] = df["atm"].replace(weather_map)

    return df


def process_places(df: pd.DataFrame) -> pd.DataFrame:
    """clean raw lieux csv."""
    df = correct_id_anomaly(df)
    df = clean_object_columns(df)
    return df
