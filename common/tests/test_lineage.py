"""Tests for common.utils.lineage — dataset & code lineage tagging."""

from __future__ import annotations

from common.utils.lineage import collect_lineage

# A minimal but realistic dvc.lock snippet (two stages, one output each).
SAMPLE_LOCK = """\
schema: '2.0'
stages:
  download_data:
    cmd: uv run python -m common.data.download_data
    outs:
    - path: data/raw/
      hash: md5
      md5: 7a5dd7dd0e8cb18a912c5e37ae281547.dir
      size: 131546316
      nfiles: 16
  make_dataset:
    cmd: mkdir -p data/processed && uv run python -m common.data.make_dataset
    outs:
    - path: data/processed/
      hash: md5
      md5: 496d188249cc62daa5c56ece4733ec8a.dir
      size: 175715571
      nfiles: 6
"""

EXPECTED_KEYS = {
    "git_commit",
    "git_commit_short",
    "git_branch",
    "git_dirty",
    "dvc_processed_data_md5",
    "dvc_raw_data_md5",
    "dvc_lock_md5",
    "data_years",
    "exclusive_test_year",
    "lineage_logged_at",
}


def test_collect_lineage_returns_string_tags():
    """All lineage tags are present and are non-empty strings (MLflow requires strings)."""
    tags = collect_lineage()
    assert isinstance(tags, dict) and tags
    assert EXPECTED_KEYS.issubset(tags.keys())
    for key, value in tags.items():
        assert isinstance(key, str)
        assert isinstance(value, str) and value != ""


def test_dvc_hashes_parsed_from_lock(tmp_path):
    """The DVC data hashes are read from a dvc.lock in the given project root."""
    (tmp_path / "dvc.lock").write_text(SAMPLE_LOCK, encoding="utf-8")

    tags = collect_lineage(project_root=tmp_path)

    assert tags["dvc_processed_data_md5"] == "496d188249cc62daa5c56ece4733ec8a.dir"
    assert tags["dvc_raw_data_md5"] == "7a5dd7dd0e8cb18a912c5e37ae281547.dir"
    assert tags["dvc_lock_md5"] != "unknown"


def test_missing_lock_degrades_gracefully(tmp_path):
    """With no dvc.lock (and no env override) the data hash is 'unknown', never an error."""
    tags = collect_lineage(project_root=tmp_path)
    assert tags["dvc_processed_data_md5"] == "unknown"
