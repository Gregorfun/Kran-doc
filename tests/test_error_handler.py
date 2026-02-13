"""
Unit Tests for Error Handler Module

Tests for error handling utilities and decorators.
"""

import pytest

from scripts.error_handler import (
    ConfigurationError,
    ParsingError,
    PDFDocError,
    ValidationError,
    handle_errors,
    retry_on_failure,
    safe_execute,
)


@pytest.mark.unit
class TestSafeExecute:
    """Test safe_execute function."""

    def test_safe_execute_successful_call(self):
        """Test safe_execute with successful function call."""
        result = safe_execute(int, "42", default=0)
        assert result == 42

    def test_safe_execute_with_exception_returns_default(self):
        """Test safe_execute returns default on exception."""
        result = safe_execute(int, "not_a_number", default=999)
        assert result == 999

    def test_safe_execute_with_kwargs(self):
        """Test safe_execute with keyword arguments."""

        def add(a, b):
            return a + b

        result = safe_execute(add, a=10, b=20, default=0)
        assert result == 30

    def test_safe_execute_without_log_error(self):
        """Test safe_execute with log_error=False."""
        # Should not raise, just return default
        result = safe_execute(int, "invalid", default=0, log_error=False)
        assert result == 0


@pytest.mark.unit
class TestRetryOnFailure:
    """Test retry_on_failure decorator."""

    def test_retry_on_failure_immediate_success(self):
        """Test retry_on_failure with function that succeeds immediately."""
        call_count = 0

        @retry_on_failure(max_attempts=3)
        def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_func()
        assert result == "success"
        assert call_count == 1

    def test_retry_on_failure_recovers_after_failures(self):
        """Test retry_on_failure recovers after a few failures."""
        call_count = 0

        @retry_on_failure(max_attempts=3, delay=0.01)
        def sometimes_fails():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise IOError("Temporary failure")
            return "success"

        result = sometimes_fails()
        assert result == "success"
        assert call_count == 3

    def test_retry_on_failure_raises_after_max_attempts(self):
        """Test retry_on_failure raises after max attempts."""
        call_count = 0

        @retry_on_failure(max_attempts=2, delay=0.01)
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise IOError("Permanent failure")

        with pytest.raises(IOError):
            always_fails()

        assert call_count == 2

    def test_retry_on_failure_only_retries_specified_exceptions(self):
        """Test retry_on_failure only retries specified exceptions."""
        call_count = 0

        @retry_on_failure(max_attempts=3, delay=0.01, exceptions=(IOError,))
        def fails_with_value_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("Not retryable")

        with pytest.raises(ValueError):
            fails_with_value_error()

        # Should only try once since ValueError is not in exceptions tuple
        assert call_count == 1


@pytest.mark.unit
class TestHandleErrors:
    """Test handle_errors decorator."""

    def test_handle_errors_successful_call(self):
        """Test handle_errors with successful function."""

        @handle_errors("Test error")
        def successful_func():
            return "success"

        result = successful_func()
        assert result == "success"

    def test_handle_errors_logs_and_returns_none(self):
        """Test handle_errors logs error and returns None."""

        @handle_errors("Test error", reraise=False)
        def failing_func():
            raise ValueError("Test error")

        result = failing_func()
        assert result is None

    def test_handle_errors_reraises(self):
        """Test handle_errors can reraise exceptions."""

        @handle_errors("Test error", reraise=True)
        def failing_func():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            failing_func()


@pytest.mark.unit
class TestCustomExceptions:
    """Test custom exception classes."""

    def test_pdfdoc_error_is_exception(self):
        """Test PDFDocError is an Exception."""
        with pytest.raises(PDFDocError):
            raise PDFDocError("Test error")

    def test_parsing_error_inheritance(self):
        """Test ParsingError inherits from PDFDocError."""
        with pytest.raises(PDFDocError):
            raise ParsingError("Parse failed")

    def test_configuration_error_inheritance(self):
        """Test ConfigurationError inherits from PDFDocError."""
        with pytest.raises(PDFDocError):
            raise ConfigurationError("Config invalid")

    def test_validation_error_inheritance(self):
        """Test ValidationError inherits from PDFDocError."""
        with pytest.raises(PDFDocError):
            raise ValidationError("Validation failed")
