"""
Dataset & code lineage for MLflow runs.

WHY THIS EXISTS
---------------
When you have dozens of experiments in MLflow/DagsHub, a natural question is:
"which exact dataset and which exact code produced *this* model?" Without an
explicit record you can only guess by timestamp. This module answers that
question by attaching a small set of **lineage tags** to every MLflow run:

  CODE  version  ->  git commit / branch / dirty-flag
  DATA  version  ->  DVC content hashes read from ``dvc.lock``

Because DVC stores an immutable md5 for every pipeline output, the
``data/processed`` hash *is* the fingerprint of the training data. Pair it with
the git commit and any run becomes fully reproducible.

DESIGN NOTES
------------
* Every value is returned as a **string** (MLflow tags must be strings).
* Every lookup **degrades gracefully** to ``"unknown"`` and never raises, so
  collecting lineage can NEVER break a training run.
* Works both locally (reads ``.git`` + ``dvc.lock``) and inside a container
  where ``.git`` may be absent (falls back to the ``GIT_COMMIT`` / ``GIT_BRANCH``
  / ``DVC_DATA_HASH`` environment variables if they are provided).
"""

from __future__ import annotations

import hashlib
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from common.utils.asp_logging import get_logger
from common.utils.paths import DATA_PROCESSING_CONFIG, PROJECT_ROOT

logger = get_logger(__name__)

UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------
def _run_git(args: list[str], root: str) -> str:
    """Run a git command in ``root`` and return its stripped stdout ("" on error)."""
    try:
        out = subprocess.check_output(
            ["git", *args],
            cwd=root,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip()
    except Exception:  # git missing, not a repo, etc. — lineage must never fail
        return ""


def _git_lineage(root: str) -> dict[str, str]:
    """Collect git commit / branch / dirty-flag (env vars win, for containers)."""
    commit = os.environ.get("GIT_COMMIT") or _run_git(["rev-parse", "HEAD"], root)
    branch = os.environ.get("GIT_BRANCH") or _run_git(["rev-parse", "--abbrev-ref", "HEAD"], root)

    # "dirty" = there are uncommitted changes at training time (only knowable with a .git)
    if commit and not os.environ.get("GIT_COMMIT"):
        dirty = bool(_run_git(["status", "--porcelain"], root))
        dirty_str = "true" if dirty else "false"
    else:
        dirty_str = UNKNOWN

    return {
        "git_commit": commit or UNKNOWN,
        "git_commit_short": (commit[:8] if commit else UNKNOWN),
        "git_branch": branch or UNKNOWN,
        "git_dirty": dirty_str,
    }


# ---------------------------------------------------------------------------
# DVC helpers
# ---------------------------------------------------------------------------
def _find_out_md5(stages: dict, stage: str, path_prefix: str) -> str:
    """Return the md5 of a given output path inside a dvc.lock stage, else UNKNOWN."""
    try:
        for out in stages.get(stage, {}).get("outs", []):
            if str(out.get("path", "")).startswith(path_prefix):
                return str(out.get("md5", UNKNOWN))
    except Exception:
        pass
    return UNKNOWN


def _parse_lock_with_regex(text: str, stage: str, path_prefix: str) -> str:
    """Fallback parser (no PyYAML): find ``stage`` -> outs -> path -> next md5."""
    lines = text.splitlines()
    in_stage = in_outs = at_path = False
    for line in lines:
        stripped = line.strip()
        if stripped == f"{stage}:":
            in_stage, in_outs, at_path = True, False, False
            continue
        if in_stage and stripped == "outs:":
            in_outs = True
            continue
        if in_stage and in_outs and stripped.startswith("- path:") and path_prefix in stripped:
            at_path = True
            continue
        if at_path and stripped.startswith("md5:"):
            return stripped.split("md5:", 1)[1].strip()
        # a new top-level stage key ends our search scope
        if in_stage and line and not line[0].isspace() and stripped != f"{stage}:":
            in_stage = in_outs = at_path = False
    return UNKNOWN


def _dvc_lineage(root: str) -> dict[str, str]:
    """Read DVC content hashes from ``dvc.lock`` (the immutable data fingerprints)."""
    tags = {
        "dvc_processed_data_md5": UNKNOWN,
        "dvc_raw_data_md5": UNKNOWN,
        "dvc_lock_md5": UNKNOWN,
    }

    lock = Path(root) / "dvc.lock"
    if not lock.exists():
        # container fallback: whoever launched us may pass the hash explicitly
        env_hash = os.environ.get("DVC_DATA_HASH")
        if env_hash:
            tags["dvc_processed_data_md5"] = env_hash
        return tags

    text = lock.read_text(encoding="utf-8")
    # a single fingerprint of the whole lock file (changes if ANY tracked input changes)
    tags["dvc_lock_md5"] = hashlib.md5(text.encode("utf-8")).hexdigest()  # content fingerprint, not security

    stages: dict = {}
    try:
        import yaml  # provided transitively by dvc/mlflow; optional here

        stages = (yaml.safe_load(text) or {}).get("stages", {})
    except Exception:
        stages = {}

    if stages:
        tags["dvc_processed_data_md5"] = _find_out_md5(stages, "make_dataset", "data/processed")
        tags["dvc_raw_data_md5"] = _find_out_md5(stages, "download_data", "data/raw")
    else:
        # no yaml available -> regex fallback
        tags["dvc_processed_data_md5"] = _parse_lock_with_regex(text, "make_dataset", "data/processed")
        tags["dvc_raw_data_md5"] = _parse_lock_with_regex(text, "download_data", "data/raw")

    return tags


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def collect_lineage(project_root: Path | str = PROJECT_ROOT) -> dict[str, str]:
    """Collect dataset + code lineage as a flat dict of string MLflow tags.

    Returns keys: git_commit, git_commit_short, git_branch, git_dirty,
    dvc_processed_data_md5, dvc_raw_data_md5, dvc_lock_md5, data_years,
    exclusive_test_year, lineage_logged_at.
    """
    root = str(project_root)

    tags: dict[str, str] = {}
    tags.update(_git_lineage(root))
    tags.update(_dvc_lineage(root))

    # a little extra context that is cheap and useful in the MLflow UI
    tags["data_years"] = ",".join(str(y) for y in DATA_PROCESSING_CONFIG.get("years", []))
    tags["exclusive_test_year"] = str(DATA_PROCESSING_CONFIG.get("exclusive_test_year", UNKNOWN))
    tags["lineage_logged_at"] = datetime.now(UTC).isoformat()

    # final safety: MLflow tags must be non-empty strings
    return {k: (str(v) if v not in (None, "") else UNKNOWN) for k, v in tags.items()}
