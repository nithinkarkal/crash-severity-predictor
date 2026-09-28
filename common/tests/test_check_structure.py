"""
Tests for check_structure
"""

from pathlib import Path

from common.data.check_structure import create_dir, dir_exists, ensure_directories, file_exists


def test_dir_exists_true(tmp_path: Path) -> None:
    """dir exists"""
    assert dir_exists(tmp_path) is True


def test_dir_exists_false(tmp_path: Path) -> None:
    """return false"""
    assert dir_exists(tmp_path / "missing") is False


def test_dir_exists_on_file(tmp_path: Path) -> None:
    """create a file and test as dir to simulate dir not exists"""
    f = tmp_path / "file.txt"
    f.touch()
    assert dir_exists(f) is False


def test_file_exists_true(tmp_path: Path) -> None:
    f = tmp_path / "file.txt"
    f.touch()
    assert file_exists(f) is True


def test_file_exists_false(tmp_path: Path) -> None:
    assert file_exists(tmp_path / "missing.txt") is False


def test_file_exists_on_dir(tmp_path: Path) -> None:
    assert file_exists(tmp_path) is False


def test_create_dir_new(tmp_path: Path) -> None:
    d = tmp_path / "new"
    assert create_dir(d) is True
    assert d.exists()


def test_create_dir_existing(tmp_path: Path) -> None:
    assert create_dir(tmp_path) is False


def test_create_dir_nested(tmp_path: Path) -> None:
    d = tmp_path / "a" / "b" / "c"
    assert create_dir(d) is True
    assert d.exists()


def test_ensure_directories_creates_all(tmp_path: Path) -> None:
    dirs = [tmp_path / "d1", tmp_path / "d2"]
    assert ensure_directories(dirs) == 2
    assert all(d.exists() for d in dirs)


def test_ensure_directories_skips_existing(tmp_path: Path) -> None:
    existing = tmp_path / "old"
    existing.mkdir()
    assert ensure_directories([existing, tmp_path / "new"]) == 1


def test_ensure_directories_all_exist(tmp_path: Path) -> None:
    assert ensure_directories([tmp_path]) == 0
