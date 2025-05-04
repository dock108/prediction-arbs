"""Test Docker image build."""

import os
import shutil
import subprocess

import pytest

# Skip this test if Docker is not available
pytestmark = pytest.mark.skipif(
    shutil.which("docker") is None,
    reason="Docker not available in CI runner",
)


def test_image_builds():
    """Test that the Docker image builds successfully."""
    # Skip if explicitly disabled in CI
    if os.environ.get("CI_SKIP_DOCKER_TESTS") == "1":
        pytest.skip("Docker tests disabled in CI")

    # Get full path to Docker executable
    docker_path = shutil.which("docker")
    assert docker_path is not None, "Docker executable not found"

    try:
        result = subprocess.run(  # noqa: S603
            [docker_path, "build", "-q", "."],
            capture_output=True,
            text=True,
            check=True,
        )
        assert result.stdout.strip(), "Image ID should be returned"
    except subprocess.CalledProcessError as e:
        pytest.fail(f"Docker build command failed: {e.stderr}")
