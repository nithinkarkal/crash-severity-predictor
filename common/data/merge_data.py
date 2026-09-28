"""
Merge cleaned tables, split train/test, inpute features and save datasets
"""

from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

CAT_COLS = [
    "place", "catu", "sexe", "secu1", "catv", "obsm", "motor", "catr", "circ",
    "surf", "situ", "jour", "mois", "lum", "dep", "com", "agg", "int", "atm",
    "col", "lat", "long", "hour",
]

DROP_COLS = [
    "senc", "larrout", "actp", "manv", "choc", "nbv", "prof", "plan", "Num_Acc",
    "id_vehicule", "num_veh", "pr", "pr1", "voie", "trajet", "secu2", "secu3",
    "adr", "v1", "lartpc", "occutc", "v2", "vosp", "locp", "etatp", "infra", "obs",
]

REPLACE_MINUS1_NA_COLS = [
    "trajet", "secu1", "catv", "obsm", "motor", "circ", "surf", "situ",
    "vma", "atm", "col"
]
REPLACE_0_NA_COLS = ["trajet", "catv", "motor"]


def collect_raw_data_paths(raw_data_dir: str | Path) -> defaultdict[str, dict[int, Path]]:
    """collect raw file paths ordered by table type ('usa','veh','car','lie') + year."""
    raw_data_dir = Path(raw_data_dir)
    files: defaultdict[str, dict[int, Path]] = defaultdict(dict)

    for file_path in raw_data_dir.glob("*.csv"):
        table = file_path.stem[:3].lower()
        year = int(file_path.stem[-4:])
        files[table][year] = file_path

    return files

def merge_datasets(
        df_users: pd.DataFrame,
        df_veh: pd.DataFrame,
        df_places: pd.DataFrame,
        df_caract: pd.DataFrame,
    ) -> pd.DataFrame:
    """merge the 4 cleaned tables into a single DataFrame (1 row / accident)."""

    fusion1 = df_users.merge(df_veh, on=["Num_Acc", "num_veh", "id_vehicule"], how="inner")
    fusion1 = fusion1.sort_values(by="grav", ascending=False)
    fusion1 = fusion1.drop_duplicates(subset=["Num_Acc"], keep="first")
    fusion2 = fusion1.merge(df_places, on="Num_Acc", how="left")

    df = fusion2.merge(df_caract, on="Num_Acc", how="left")

    return df


def process_merged_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """replace sentinel values (-1/0) by NaN and drop unused columns."""

    df[REPLACE_MINUS1_NA_COLS] = df[REPLACE_MINUS1_NA_COLS].replace(-1, np.nan)
    df[REPLACE_0_NA_COLS] = df[REPLACE_0_NA_COLS].replace(0, np.nan)
    df = df.drop(columns=DROP_COLS)

    return df

def split_data(
        df_collection: dict[int, pd.DataFrame],
        exclusive_test_year: int | None = None,
        test_size: float = 0.3,
        random_state: int = 42,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """create train/test splits. test_size/random_state only used if exclusive_test_year is None."""

    if exclusive_test_year:
        train = pd.concat(
            [df for year, df in df_collection.items() if year != exclusive_test_year],
            ignore_index=True,
        )
        X_train, y_train = train.drop(columns=["grav"]), train["grav"]

        test = df_collection[exclusive_test_year]
        X_test, y_test = test.drop(columns=["grav"]), test["grav"]
    else:
        df = pd.concat(df_collection.values(), ignore_index=True)
        X, y = df.drop(columns=["grav"]), df["grav"]
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state,
        )

    return X_train, X_test, y_train, y_test


def process_features(
        X_train: pd.DataFrame,
        X_test: pd.DataFrame,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """impute NaNs (median for numeric, mode for categorical)."""

    cat_cols = [c for c in CAT_COLS if c in X_train.columns]
    num_cols = [c for c in X_train.columns if c not in cat_cols]

    median_imputer = SimpleImputer(strategy="median")
    mode_imputer = SimpleImputer(strategy="most_frequent")

    X_train[num_cols] = median_imputer.fit_transform(X_train[num_cols])
    X_test[num_cols] = median_imputer.transform(X_test[num_cols])

    X_train[cat_cols] = mode_imputer.fit_transform(X_train[cat_cols])
    X_test[cat_cols] = mode_imputer.transform(X_test[cat_cols])

    return X_train, X_test

def save_datasets(
        X_train: pd.DataFrame,
        X_test: pd.DataFrame,
        y_train: pd.Series,
        y_test: pd.Series,
        processed_data_dir: str | Path,
    ) -> None:
    """save train/test datasets to processed_data_dir."""

    processed_data_dir = Path(processed_data_dir)
    for df, filename in zip([X_train, X_test, y_train, y_test],
                             ["X_train", "X_test", "y_train", "y_test"]):
        df.to_csv(processed_data_dir / f"{filename}.csv", index=False)


def save_drift_frames(
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        processed_data_dir: str | Path,
    ) -> None:
    """Save the PRE-normalization reference and current frames for drift detection.

    Drift detection (Evidently) is only meaningful on the RAW category codes
    (atm, col, catr, ...). The model's processed CSVs scale those columns to
    floats, which hides the categories. So here we snapshot the frames *before*
    normalization:

      reference_raw.csv -> baseline years (the training split, e.g. 2021-2023) + grav
      current_raw.csv   -> the new annual batch (the test split, e.g. 2024)     + grav

    The target column `grav` is added back so Evidently can also check target drift.
    """

    processed_data_dir = Path(processed_data_dir)

    reference = X_train.copy()
    reference["grav"] = y_train.to_numpy()

    current = X_test.copy()
    current["grav"] = y_test.to_numpy()

    reference.to_csv(processed_data_dir / "reference_raw.csv", index=False)
    current.to_csv(processed_data_dir / "current_raw.csv", index=False)
