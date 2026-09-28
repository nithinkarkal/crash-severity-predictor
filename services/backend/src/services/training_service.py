"""
Backend training service.
Launches the training Docker container via subprocess.
"""

import os
import subprocess
import time

from common.utils.asp_logging import get_logger

logger = get_logger(__name__)

TRAINING_IMAGE = "asp-training:latest"

# Paths resolved by the HOST Docker daemon (must be absolute host paths)
DEFAULT_HOST_DATA_DIR = os.getenv("HOST_DATA_DIR", os.path.join(os.getcwd(), "data"))
DEFAULT_HOST_ARTIFACTS_DIR = os.getenv("HOST_ARTIFACTS_DIR", os.path.join(os.getcwd(), "artifacts"))


def _build_command(
    model_name: str,
    host_data_dir: str,
    host_artifacts_dir: str,
) -> list[str]:
    """build docker run command with host bind mounts."""
    return [
        "docker",
        "run",
        "--rm",
        "--network",
        "asp-network",
        # "--user",
        # f"{os.getuid()}:{os.getgid()}",
        "-v",
        f"{host_data_dir}:/app/data",
        "-v",
        f"{host_artifacts_dir}:/app/artifacts",
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

    # ensure abs path
    data_dir = os.path.abspath(data_dir)
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
