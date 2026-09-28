"""
Utility function to read pd csv file
"""
from pathlib import Path

import pandas as pd


def load_raw_csv(path: str | Path) -> pd.DataFrame:
    """read csv file"""
    return pd.read_csv(path, sep=";", low_memory=False)


def load_processed_csv(path: str | Path) -> pd.DataFrame:
    """read processed csv files (comma-separated)"""
    return pd.read_csv(path)
