"""Unit tests for configuration loading and validation."""

import pytest
from pathlib import Path
from pydantic import ValidationError

from fuzzbin.common.config import (
    Config,
    HTTPConfig,
    RetryConfig,
    LoggingConfig,
    FileLoggingConfig,
)


class TestRetryConfig:
    """Tests for RetryConfig model."""

    def test_default_values(self):
        """Test default retry configuration values."""
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.backoff_multiplier == 1.0
        assert config.min_wait == 1.0
        assert config.max_wait == 10.0
        assert 500 in config.status_codes
        assert 503 in config.status_codes

    def test_custom_values(self):
        """Test custom retry configuration values."""
        config = RetryConfig(
            max_attempts=5,
            backoff_multiplier=2.0,
            min_wait=2.0,
            max_wait=30.0,
            status_codes=[500, 502],
        )
        assert config.max_attempts == 5
        assert config.backoff_multiplier == 2.0
        assert config.status_codes == [500, 502]

    def test_invalid_status_code(self):
        """Test validation of invalid status codes."""
        with pytest.raises(ValidationError):
            RetryConfig(status_codes=[999])  # Invalid status code

    def test_validation_constraints(self):
        """Test field validation constraints."""
        with pytest.raises(ValidationError):
            RetryConfig(max_attempts=0)  # Must be >= 1

        with pytest.raises(ValidationError):
            RetryConfig(max_attempts=20)  # Must be <= 10


class TestLoggingConfig:
    """Tests for LoggingConfig model."""

    def test_default_values(self):
        """Test default logging configuration values."""
        config = LoggingConfig()
        assert config.level == "INFO"
        assert config.format == "json"
        assert config.handlers == ["console"]
        assert config.file is None

    def test_level_validation(self):
        """Test log level validation."""
        config = LoggingConfig(level="debug")  # Should be normalized to uppercase
        assert config.level == "DEBUG"

        with pytest.raises(ValidationError):
            LoggingConfig(level="INVALID")

    def test_format_validation(self):
        """Test log format validation."""
        config = LoggingConfig(format="TEXT")  # Should be normalized to lowercase
        assert config.format == "text"

        with pytest.raises(ValidationError):
            LoggingConfig(format="xml")  # Invalid format


class TestConfig:
    """Tests for main Config model."""

    def test_default_config(self):
        """Test default configuration."""
        config = Config()
        assert config.http.timeout == 30
        assert config.logging.level == "INFO"

    def test_nested_config(self):
        """Test nested configuration."""
        config = Config(
            http=HTTPConfig(timeout=60),
            logging=LoggingConfig(level="DEBUG"),
        )
        assert config.http.timeout == 60
        assert config.logging.level == "DEBUG"

    def test_from_yaml_string(self):
        """Test loading configuration from YAML string."""
        yaml_str = """
http:
  timeout: 45
  retry:
    max_attempts: 5
logging:
  level: DEBUG
  format: text
"""
        config = Config.from_yaml_string(yaml_str)
        assert config.http.timeout == 45
        assert config.http.retry.max_attempts == 5
        assert config.logging.level == "DEBUG"
        assert config.logging.format == "text"

    def test_from_yaml_file(self, tmp_path: Path):
        """Test loading configuration from YAML file."""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text("""
http:
  timeout: 120
  max_connections: 200
logging:
  level: ERROR
  handlers:
    - console
    - file
  file:
    path: logs/test.log
    max_bytes: 5242880
    backup_count: 3
""")

        config = Config.from_yaml(config_file)
        assert config.http.timeout == 120
        assert config.http.max_connections == 200
        assert config.logging.level == "ERROR"
        assert "file" in config.logging.handlers
        assert config.logging.file is not None
        assert config.logging.file.path == "logs/test.log"
        assert config.logging.file.max_bytes == 5242880

    def test_partial_config(self):
        """Test that partial configuration uses defaults."""
        yaml_str = """
http:
  timeout: 90
"""
        config = Config.from_yaml_string(yaml_str)
        assert config.http.timeout == 90
        assert config.http.max_redirects == 5  # Default value
        assert config.logging.level == "INFO"  # Default value
