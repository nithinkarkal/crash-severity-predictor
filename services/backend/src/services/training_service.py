"""
Backend training service.
Launches the training Docker container via subprocess.
"""

import os
import subprocess
import time
from datetime import UTC, datetime
from typing import Any

from common.utils.asp_logging import get_logger

logger = get_logger(__name__)

TRAINING_IMAGE = "asp-training:latest"

# In-memory status of the most recent training run. Lives in the backend process, so it
# survives between requests (single-process uvicorn) and lets the GUI poll progress.
_TRAINING_STATUS: dict[str, Any] = {
    "state": "idle",  # idle | running | succeeded | failed
    "started_at": None,
    "finished_at": None,
    "duration_seconds": None,
    "model_name": None,
    "version": None,
    "metrics": {},
    "message": "No training run has been triggered yet.",
    "error": None,
}


def get_training_status() -> dict[str, Any]:
    """Return a copy of the latest training run's status."""
    return dict(_TRAINING_STATUS)


def set_training_status(**updates: Any) -> None:
    """Merge updates into the training status store."""
    _TRAINING_STATUS.update(updates)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


# Paths resolved by the HOST Docker daemon (must be absolute host paths)
DEFAULT_HOST_DATA_DIR = os.getenv("HOST_DATA_DIR", os.path.join(os.getcwd(), "data"))
DEFAULT_HOST_ARTIFACTS_DIR = os.getenv("HOST_ARTIFACTS_DIR", os.path.join(os.getcwd(), "artifacts"))


def _is_absolute_host_path(path: str) -> bool:
    """True for POSIX (/x) or Windows drive (C:/x, C:\\x) absolute paths."""
    return path.startswith("/") or (len(path) >= 2 and path[1] == ":")


def _build_command(
    model_name: str,
    host_data_dir: str,
    host_artifacts_dir: str,
) -> list[str]:
    """Build the `docker run` command with host bind mounts.

    Uses `--mount type=bind,source=...,target=...` (not `-v src:dst`): the key=value form
    parses Windows source paths like `C:/Users/...` correctly, whereas `-v` splits on the
    drive colon and misreads the target as an invalid mount "mode".
    """
    return [
        "docker",
        "run",
        "--rm",
        "--network",
        "asp-network",
        "--mount",
        f"type=bind,source={host_data_dir},target=/app/data",
        "--mount",
        f"type=bind,source={host_artifacts_dir},target=/app/artifacts",
        "-e",
        f"MODEL_NAME={model_name}",
        "-e",
        "DAGSHUB_USER_TOKEN",
        TRAINING_IMAGE,
    ]


def run_training_container(
    model_name: str | None = None,
    host_data_dir: str | None = None,
    host_artifacts_dir: str | None = None,
    timeout_seconds: int | None = None,
) -> dict:
    """
    launch training container.

    Args:
        model_name: Base model name. If None, training script uses default from MODEL_CONFIG.
        host_data_dir: Absolute host path for data.
        host_artifacts_dir: Absolute host path for artifacts.
        timeout_seconds: Optional timeout.

    Returns:
        Dict with status, duration, and output.
    """
    data_dir = host_data_dir or DEFAULT_HOST_DATA_DIR
    artifacts_dir = host_artifacts_dir or DEFAULT_HOST_ARTIFACTS_DIR

    # Only absolutize genuinely relative paths. Absolute HOST_* values (incl. Windows drive
    # paths like C:/Users/...) must be passed through untouched — os.path.abspath() would
    # mangle a Windows path when this code runs inside the Linux backend container.
    if not _is_absolute_host_path(data_dir):
        data_dir = os.path.abspath(data_dir)
    if not _is_absolute_host_path(artifacts_dir):
        artifacts_dir = os.path.abspath(artifacts_dir)

    # train service resolve model name
    resolved_name = model_name or "model"

    logger.info(
        f"Starting training container (image={TRAINING_IMAGE}, model_name={resolved_name}, host_data={data_dir}, host_artifacts={artifacts_dir})"
    )

    command = _build_command(resolved_name, data_dir, artifacts_dir)
    logger.debug(f"Docker command: {' '.join(command)}")

    start = time.time()

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout_seconds,
        )
        duration = time.time() - start

        logger.info(f"Training container finished in {duration:.2f}s")
        return {
            "status": "success",
            "duration_seconds": round(duration, 2),
            "model_name": resolved_name,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    except subprocess.CalledProcessError as exc:
        duration = time.time() - start
        logger.error(f"Training container failed after {duration:.2f}s")
        logger.error(f"stdout: {exc.stdout}")
        logger.error(f"stderr: {exc.stderr}")
        raise RuntimeError(f"Training container failed (exit code {exc.returncode}). stderr: {exc.stderr[:500]}") from exc

    except subprocess.TimeoutExpired as exc:
        logger.error(f"Training container timed out after {timeout_seconds}s")
        raise RuntimeError(f"Training container exceeded timeout of {timeout_seconds}s") from exc

    except FileNotFoundError as exc:
        logger.error("Docker CLI not found. Is docker-ce-cli installed?")
        raise RuntimeError(
            "Docker CLI not found in backend container. Ensure docker-ce-cli is installed and /var/run/docker.sock is mounted."
        ) from exc
