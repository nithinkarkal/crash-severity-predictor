"""
Functions for checking and creating expected dirs/files
"""

from collections.abc import Sequence
from pathlib import Path

from common.utils.asp_logging import get_logger

logger = get_logger(__name__)

def dir_exists(dir_path: str | Path) -> bool:
    """true if dir_path exists and is dir"""
    return Path(dir_path).is_dir()

def file_exists(file_path: str | Path) -> bool:
    """true if file_path exists and if is file"""
    return Path(file_path).is_file()


def create_dir(dir_path: str | Path) -> bool:
    """create dir if missing and return path"""
    dir_path = Path(dir_path)
    if dir_path.exists():
        return False

    dir_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"Created directory: {dir_path}")

    return True


def ensure_directories(dirs: Sequence[str | Path]) -> int:
    """create missing dir and return the number of created."""
    created = 0
    for d in dirs:
        if create_dir(d):
            created += 1
    return created
