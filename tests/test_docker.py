"""Test Docker image build."""

import shutil
import subprocess
from pathlib import Path

import pytest


def is_docker_available():
    """Check if Docker is available on the system."""
    return shutil.which("docker") is not None


@pytest.mark.skipif(not is_docker_available(), reason="Docker not installed")
def test_docker_build():
    """Test that the Docker image builds successfully."""
    try:
        # Using full paths and fixed arguments for security
        docker_path = shutil.which("docker")
        if not docker_path:
            pytest.skip("Docker executable not found")

        # We're using fixed arguments, not user input
        result = subprocess.run(  # noqa: S603
            [docker_path, "build", "-q", str(Path.cwd())],
            check=True,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Docker build failed: {result.stderr}"
    except subprocess.CalledProcessError as e:
        pytest.fail(f"Docker build command failed: {e.stderr}")
