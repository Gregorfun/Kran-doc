"""
Smoke Tests

Basic tests to ensure the application modules can be imported correctly.
"""

import os
import sys

import pytest

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.mark.unit
def test_imports():
    """Test that core modules can be imported"""
    try:
        from config import settings
        from core import search
        from scripts import error_handler, logger

        assert True
    except ImportError as e:
        pytest.fail(f"Could not import core modules: {e}")


@pytest.mark.unit
def test_logger_can_be_initialized():
    """Test that logger can be initialized"""
    from scripts.logger import get_logger, setup_logging

    logger = get_logger("test")
    assert logger is not None
    assert logger.name == "test"


@pytest.mark.unit
def test_error_handler_imports():
    """Test error handler utilities"""
    from scripts.error_handler import handle_errors, retry_on_failure, safe_execute

    # Test safe_execute
    result = safe_execute(int, "123", default=0)
    assert result == 123

    result = safe_execute(int, "invalid", default=999)
    assert result == 999
