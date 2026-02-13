"""
Unit Tests for Logger Module

Tests for logging functionality and formatters.
"""

import json
import logging
from pathlib import Path

import pytest

from scripts.logger import ColoredFormatter, JSONFormatter, get_logger, setup_logging


@pytest.mark.unit
class TestLoggerBasic:
    """Test basic logger functionality."""

    def test_get_logger_returns_logger(self):
        """Test that get_logger returns a Logger instance."""
        logger = get_logger("test_module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_module"

    def test_get_logger_same_instance(self):
        """Test that get_logger returns same instance for same name."""
        logger1 = get_logger("test")
        logger2 = get_logger("test")
        assert logger1 is logger2

    def test_logger_can_log(self):
        """Test that logger can actually log messages."""
        logger = get_logger("test_logger")

        # Should not raise exception
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")


@pytest.mark.unit
class TestFormatters:
    """Test logging formatters."""

    def test_colored_formatter_formats_record(self):
        """Test that ColoredFormatter can format a log record."""
        formatter = ColoredFormatter(fmt="%(levelname)s - %(message)s")
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py", lineno=10, msg="Test message", args=(), exc_info=None
        )

        formatted = formatter.format(record)
        assert "Test message" in formatted

    def test_json_formatter_creates_valid_json(self):
        """Test that JSONFormatter creates valid JSON output."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py", lineno=10, msg="Test message", args=(), exc_info=None
        )

        formatted = formatter.format(record)

        # Should be valid JSON
        data = json.loads(formatted)
        assert data["level"] == "INFO"
        assert data["message"] == "Test message"
        assert data["logger"] == "test"
        assert "timestamp" in data


@pytest.mark.unit
def test_setup_logging_colored_format(tmp_path):
    """Test setup_logging with colored format."""
    log_file = tmp_path / "test.log"
    setup_logging(level=logging.INFO, log_file=log_file, enable_colors=True, format_type="colored")

    logger = get_logger("test")
    logger.info("Test message")

    assert log_file.exists()


@pytest.mark.unit
def test_setup_logging_json_format(tmp_path):
    """Test setup_logging with JSON format."""
    log_file = tmp_path / "test.log"
    setup_logging(level=logging.INFO, log_file=log_file, enable_colors=False, format_type="json")

    logger = get_logger("test")
    logger.info("Test message")

    assert log_file.exists()

    # File should contain valid JSON
    with open(log_file) as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                assert "timestamp" in data
                assert "level" in data
