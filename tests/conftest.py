"""
Pytest Configuration & Fixtures

This file provides shared test configuration and fixtures for the entire test suite.
"""

import os
import sys
from pathlib import Path

import pytest

# Add project root to path so imports work
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def project_root() -> Path:
    """Returns the project root directory."""
    return PROJECT_ROOT


@pytest.fixture
def test_data_dir() -> Path:
    """Returns the test data directory."""
    test_dir = PROJECT_ROOT / "tests" / "data"
    test_dir.mkdir(parents=True, exist_ok=True)
    return test_dir


@pytest.fixture
def temp_output_dir(tmp_path) -> Path:
    """Returns a temporary directory for test outputs."""
    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


@pytest.fixture
def mock_settings():
    """Returns mock settings for testing without real config."""

    class MockSettings:
        app_name = "Kran-Doc"
        debug = True
        base_dir = PROJECT_ROOT
        input_dir = PROJECT_ROOT / "tests" / "data"
        output_dir = PROJECT_ROOT / "tests" / "output"
        ocr_enabled = False  # Disable for tests
        semantic_threshold = 0.6

    return MockSettings()


@pytest.fixture(autouse=True)
def reset_env():
    """Reset environment variables to safe defaults for tests."""
    original_env = os.environ.copy()

    # Set test-safe environment
    os.environ["LOG_LEVEL"] = "DEBUG"
    os.environ["FLASK_ENV"] = "testing"

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


# Mark tests that should only run locally
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "skip_ci: mark test to skip in CI environment")


@pytest.fixture(scope="session")
def ci_environment():
    """Check if running in CI environment."""
    return bool(os.getenv("CI") or os.getenv("GITHUB_ACTIONS"))
