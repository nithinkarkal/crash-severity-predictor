"""Tests for training_service.

Mock subprocess to avoid actual Docker calls during tests.
"""

from subprocess import CalledProcessError, TimeoutExpired
from unittest.mock import MagicMock, patch

import pytest

from services.backend.src.services import training_service
from services.backend.src.services.training_service import (
    TRAINING_IMAGE,
    _build_command,
    run_training_container,
)


def test_build_command_structure() -> None:
    """command contains all required docker arguments."""
    cmd = _build_command("my-model", "/host/data", "/host/artifacts")

    assert cmd[0] == "docker"
    assert "--rm" in cmd
    assert "-v" in cmd
    assert "/host/data:/app/data" in cmd
    assert "/host/artifacts:/app/artifacts" in cmd
    assert "-e" in cmd
    assert "MODEL_NAME=my-model" in cmd
    assert TRAINING_IMAGE in cmd


@patch("services.backend.src.services.training_service.subprocess.run")
def test_run_success(mock_run: MagicMock) -> None:
    """container completes successfully."""
    mock_run.return_value = MagicMock(
        stdout="Training complete",
        stderr="",
        returncode=0,
    )

    result = run_training_container(
        model_name="model",
        host_data_dir="/host/data",
        host_artifacts_dir="/host/artifacts",
    )

    assert result["status"] == "success"
    assert result["duration_seconds"] >= 0
    mock_run.assert_called_once()


@patch("services.backend.src.services.training_service.subprocess.run")
def test_run_failure(mock_run: MagicMock) -> None:
    """container exits with error code."""
    mock_run.side_effect = CalledProcessError(
        returncode=1,
        cmd=["docker", "run"],
        output="",
        stderr="OOM killed",
    )

    with pytest.raises(RuntimeError, match="Training container failed"):
        run_training_container()


@patch("services.backend.src.services.training_service.subprocess.run")
def test_run_timeout(mock_run: MagicMock) -> None:
    """container exceeds timeout."""
    mock_run.side_effect = TimeoutExpired(cmd=["docker", "run"], timeout=60)

    with pytest.raises(RuntimeError, match="timeout"):
        run_training_container(timeout_seconds=60)


@patch("services.backend.src.services.training_service.subprocess.run")
def test_run_docker_not_found(mock_run: MagicMock) -> None:
    """docker CLI not installed in backend container."""
    mock_run.side_effect = FileNotFoundError("docker not found")

    with pytest.raises(RuntimeError, match="Docker CLI not found"):
        run_training_container()


@patch("services.backend.src.services.training_service.subprocess.run")
def test_run_uses_env_defaults(mock_run: MagicMock) -> None:
    """falls back to HOST_DATA_DIR / HOST_ARTIFACTS_DIR env vars."""
    import importlib

    with patch.dict("os.environ", {"HOST_DATA_DIR": "/env/data", "HOST_ARTIFACTS_DIR": "/env/artifacts"}):
        importlib.reload(training_service)

        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

        training_service.run_training_container()

        call_args = mock_run.call_args[0][0]
        assert "/env/data:/app/data" in call_args
        assert "/env/artifacts:/app/artifacts" in call_args
