"""
Preprocess dataset and save to disk
"""

from pathlib import Path

import pandas as pd

from common.data.check_structure import file_exists
from common.data.clean_data import (
    process_characteristics,
    process_places,
    process_users,
    process_vehicles,
)
from common.data.dataset_io import load_raw_csv
from common.data.merge_data import (
    collect_raw_data_paths,
    merge_datasets,
    process_features,
    process_merged_dataset,
    save_datasets,
    save_drift_frames,
    split_data,
)
from common.utils.asp_logging import get_logger
from common.utils.paths import DATA_PROCESSING_CONFIG, PROCESSED_DATA_DIR, RAW_DATA_DIR

logger = get_logger(__name__)

# The train/test files the pipeline consumes, plus the raw reference/current frames
# used by drift detection (so a rebuild also produces them).
PROCESSED_FILES = [
    "X_train.csv", "X_test.csv", "y_train.csv", "y_test.csv",
    "reference_raw.csv", "current_raw.csv",
]


def processed_data_exists(processed_data_dir: str | Path) -> bool:
    """true if any train/test file already exists (avoid overwriting silently)."""

    processed_data_dir = Path(processed_data_dir)

    return all(file_exists(processed_data_dir / filename) for filename in PROCESSED_FILES)


def process_yearly_data(raw_path_collection: dict, year: int) -> pd.DataFrame:
    """clean and merge the 4 raw tables of a given year into one DataFrame."""

    logger.info(f"Loading users ({year})...")
    path = raw_path_collection["usa"][year]
    if path is None:
        raise FileNotFoundError(
            f"Missing usagers dataset for {year}"
        )
    df_users = process_users(load_raw_csv(path))

    logger.info(f"Loading vehicles ({year})...")
    path = raw_path_collection["veh"][year]
    if path is None:
        raise FileNotFoundError(
            f"Missing vehicles dataset for {year}"
        )
    df_veh = process_vehicles(load_raw_csv(path))

    logger.info(f"Loading characteristics ({year})...")
    path = raw_path_collection["car"][year]
    if path is None:
        raise FileNotFoundError(
            f"Missing caracteristiques dataset for {year}"
        )
    df_caract = process_characteristics(load_raw_csv(path))

    logger.info(f"Loading places ({year})...")
    path = raw_path_collection["lie"][year]
    if path is None:
        raise FileNotFoundError(
            f"Missing lieux dataset for {year}"
        )
    df_places = process_places(load_raw_csv(path))

    logger.info(f"Merging datasets ({year})...")
    df = merge_datasets(df_users, df_veh, df_places, df_caract)
    df = process_merged_dataset(df)
    logger.info(f"Finished preprocessing {year}")

    return df


def process_data(
        years: list[int] = DATA_PROCESSING_CONFIG["years"],
        exclusive_test_year: int | None = DATA_PROCESSING_CONFIG["exclusive_test_year"],
        raw_data_dir: str | Path = RAW_DATA_DIR,
        processed_data_dir: str | Path = PROCESSED_DATA_DIR,
        test_size: float = DATA_PROCESSING_CONFIG["test_size"],
        random_state: int = DATA_PROCESSING_CONFIG["random_state"],
        overwrite: bool = False,
    ) -> None:
    """build train/test datasets from raw csv files and save them to processed_data_dir."""

    if processed_data_exists(processed_data_dir) and not overwrite:
        logger.info("Processed data already exists, skipping. Use overwrite=True to rebuild.")
        return

    logger.info("Collecting raw dataset paths...")
    raw_paths = collect_raw_data_paths(raw_data_dir)

    logger.info(f"Processing years: {years}")
    df_years = {}
    for year in years:
        logger.info(f"Processing dataset {year}...")
        df_years[year] = process_yearly_data(raw_paths, year)

    logger.info("Splitting dataset...")
    X_train, X_test, y_train, y_test = split_data(
        df_years, exclusive_test_year=exclusive_test_year,
        test_size=test_size, random_state=random_state,
    )

    # Snapshot the RAW (pre-normalization) frames for drift detection, before the
    # features get scaled. See save_drift_frames() for why.
    logger.info("Saving raw reference/current frames for drift detection...")
    save_drift_frames(X_train, y_train, X_test, y_test, processed_data_dir)

    logger.info("Processing features...")
    X_train, X_test = process_features(X_train, X_test)

    logger.info("Saving processed datasets...")
    save_datasets(X_train, X_test, y_train, y_test, processed_data_dir)
    logger.info("Dataset preprocessing completed.")


if __name__ == "__main__":
    process_data()
