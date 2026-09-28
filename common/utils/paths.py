"""
centralized config for project dir structure and API
"""

from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# data
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
EXTERNAL_DATA_DIR = DATA_DIR / "external"

# artifacts
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
MODEL_DIR = ARTIFACTS_DIR / "models"
METRIC_DIR = ARTIFACTS_DIR / "metrics"
REPORT_DIR = ARTIFACTS_DIR / "reports"

# services
SERVICES_DIR = PROJECT_ROOT / "services"
BACKEND_DIR = SERVICES_DIR / "backend"
FRONTEND_DIR = SERVICES_DIR / "frontend"
TRAINING_DIR = SERVICES_DIR / "training"

# common
COMMON_DIR = PROJECT_ROOT / "common"
DATA_SCRIPTS_DIR = COMMON_DIR / "data"
UTILS_DIR = COMMON_DIR / "utils"

# download dataset api url configuration
API_CONFIG: dict[str, str] = {
    "dataset_url": "https://www.data.gouv.fr/api/1/datasets/",
    "dataset_slug": "bases-de-donnees-annuelles-des-accidents-corporels-de-la-circulation-routiere-annees-de-2005-a-2024/",
}

# preprocessing config
DATA_PROCESSING_CONFIG: dict[str, Any] = {
    "years": [2021, 2022, 2023, 2024],
    "exclusive_test_year": 2024,
    "test_size": 0.3,
    "random_state": 42,
}

# model config
MODEL_CONFIG: dict[str, Any] = {
    "model_name": "model",
    "model_registry_name": "accident-severity-predictor",
    "model_parameters": {
        "random_state": 42,
        "n_estimators": 100,
        "max_depth": 20,
        "min_samples_leaf": 2,
        "min_samples_split": 5,
        "n_jobs": -1,
    },
    "top_n_features": 20,
}

REQUIRED_DIRS = [RAW_DATA_DIR, PROCESSED_DATA_DIR, EXTERNAL_DATA_DIR, MODEL_DIR, METRIC_DIR, REPORT_DIR]
