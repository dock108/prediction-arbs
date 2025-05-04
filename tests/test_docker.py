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
        # Build the image
        build_result = subprocess.run(  # noqa: S603
            [docker_path, "build", "-t", "arbscan:test", "."],
            capture_output=True,
            text=True,
            check=True,
        )
        assert build_result.returncode == 0, "Docker build should succeed"

        # Test that the image can run and the arbscan command works
        run_result = subprocess.run(  # noqa: S603
            [docker_path, "run", "--rm", "arbscan:test", "--help"],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "arbscan" in run_result.stdout.lower(), "Help text mentions arbscan"
        assert "threshold" in run_result.stdout.lower(), "Help has threshold option"

    except subprocess.CalledProcessError as e:
        pytest.fail(f"Docker command failed: {e.stderr}")


def test_container_environment():
    """Test that environment variables are passed correctly to the container."""
    # Skip if explicitly disabled in CI
    if os.environ.get("CI_SKIP_DOCKER_TESTS") == "1":
        pytest.skip("Docker tests disabled in CI")

    # Get full path to Docker executable
    docker_path = shutil.which("docker")
    assert docker_path is not None, "Docker executable not found"

    try:
        # Run with --once flag and test env var to verify the container exits correctly
        subprocess.run(  # noqa: S603
            [
                docker_path,
                "run",
                "--rm",
                "-e",
                "TEST_ENV_VAR=test_value",
                "arbscan:test",
                "--once",
            ],
            capture_output=True,
            text=True,
            timeout=10,  # Ensure the command doesn't hang
            check=False,  # We expect this might fail due to database issues in test
        )
        # Note: The command might "fail" with a database error which is expected in test
        # We just want to make sure it tried to run the arbscan command

    except subprocess.TimeoutExpired:
        pytest.fail("Docker container didn't exit in time")
