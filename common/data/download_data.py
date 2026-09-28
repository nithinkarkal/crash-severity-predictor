"""
Dataset downloader
"""

from pathlib import Path
from typing import Any

import requests

from common.data.check_structure import file_exists
from common.utils.asp_logging import get_logger
from common.utils.paths import API_CONFIG, DATA_PROCESSING_CONFIG, RAW_DATA_DIR

logger = get_logger(__name__)


def download_raw_data(
        year: int = 2021,
        dataset_api: str = API_CONFIG["dataset_url"],
        dataset_slug: str = API_CONFIG["dataset_slug"],
        output_dir: str | Path = RAW_DATA_DIR,
        overwrite: bool = False
) -> list[Path]:
    """download the raw csv files for a given years"""

    dataset_url = dataset_api + dataset_slug
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Fetching dataset metadata from {dataset_url}...")
    response = requests.get(dataset_url)
    if response.status_code != 200:
        raise Exception(f"Download dataset failed with status code ({response.status_code})")

    logger.info("Dataset metadata fetched successfully.")

    dataset = response.json()
    resources: list[dict[str, Any]] = dataset["resources"]
    output_paths = []

    for resource in resources:
        title = resource.get("title", "")
        url = resource.get("url", "")

        if not title.endswith(".csv") or str(year) not in title or "baac" in title:
            continue

        output_path = output_dir / title

        if file_exists(output_path) and not overwrite:
            logger.info(f"File already exists, skipping: {output_path}")
            output_paths.append(output_path)
            continue

        logger.info(f"Downloading {title}...")
        with requests.get(url, stream=True) as req:
            req.raise_for_status()
            with open(output_path, "wb") as f:
                for chunk in req.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

        output_paths.append(output_path)

    return output_paths


if __name__ == "__main__":

    for year in DATA_PROCESSING_CONFIG["years"]:
        download_raw_data(year=year)
    logger.info("Download completed!")
