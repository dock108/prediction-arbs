"""Basic import test for dashboard module."""

import os

import pytest


@pytest.fixture(autouse=True)
def setup_test_env():
    """Set up test environment with in-memory database."""
    # Use in-memory database for testing
    os.environ["ARBSCAN_DB_PATH"] = ":memory:"
    yield
    # Clean up after test
    if "ARBSCAN_DB_PATH" in os.environ:
        del os.environ["ARBSCAN_DB_PATH"]


def test_dashboard_module_imports():
    """Test that the dashboard module can be imported."""
    # This will fail if there are any import errors or SQLModel connection issues
    import arbscan.dashboard

    # Verify main entry point function exists
    assert callable(arbscan.dashboard.main)

    # Verify DB functions exist
    assert callable(arbscan.dashboard.create_db_engine)
    assert callable(arbscan.dashboard.get_db_path)
