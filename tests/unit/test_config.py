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
    BackupConfig,
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
        assert config.file.enabled is False

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
        assert config.logging.level == "INFO"
        assert config.backup.retention_count == 7

    def test_nested_config(self):
        """Test nested configuration."""
        config = Config(
            backup=BackupConfig(retention_count=14),
            logging=LoggingConfig(level="DEBUG"),
        )
        assert config.backup.retention_count == 14
        assert config.logging.level == "DEBUG"

    def test_from_yaml_string(self):
        """Test loading configuration from YAML string."""
        yaml_str = """
backup:
  retention_count: 10
logging:
  level: DEBUG
  format: text
"""
        config = Config.from_yaml_string(yaml_str)
        assert config.backup.retention_count == 10
        assert config.logging.level == "DEBUG"
        assert config.logging.format == "text"

    def test_from_yaml_file(self, tmp_path: Path):
        """Test loading configuration from YAML file."""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text("""
backup:
  retention_count: 14
  output_dir: custom_backups
logging:
  level: ERROR
  file:
    enabled: true
""")

        config = Config.from_yaml(config_file)
        assert config.backup.retention_count == 14
        assert config.backup.output_dir == "custom_backups"
        assert config.logging.level == "ERROR"
        assert config.logging.file.enabled is True

    def test_partial_config(self):
        """Test that partial configuration uses defaults."""
        yaml_str = """
backup:
  retention_count: 20
"""
        config = Config.from_yaml_string(yaml_str)
        assert config.backup.retention_count == 20
        assert config.backup.output_dir == "backups"  # Default value
        assert config.logging.level == "INFO"  # Default value


class TestNFOConfig:
    """Tests for NFOConfig model."""

    def test_default_values(self):
        """Test NFOConfig default values."""
        from fuzzbin.common.config import NFOConfig
        
        config = NFOConfig()
        assert config.featured_artists is not None
        assert config.featured_artists.enabled is False
        assert config.featured_artists.append_to_field == "artist"

    def test_custom_featured_artists(self):
        """Test NFOConfig with custom featured artist settings."""
        from fuzzbin.common.config import NFOConfig
        from fuzzbin.parsers.models import FeaturedArtistConfig
        
        featured_config = FeaturedArtistConfig(
            enabled=True,
            append_to_field="title"
        )
        config = NFOConfig(featured_artists=featured_config)
        
        assert config.featured_artists.enabled is True
        assert config.featured_artists.append_to_field == "title"

    def test_yaml_loading(self):
        """Test loading NFOConfig from YAML."""
        yaml_str = """
        nfo:
          featured_artists:
            enabled: true
            append_to_field: title
        """
        full_config = Config.from_yaml_string(yaml_str)
        
        assert full_config.nfo.featured_artists.enabled is True
        assert full_config.nfo.featured_artists.append_to_field == "title"


class TestOrganizerConfig:
    """Tests for OrganizerConfig model."""

    def test_default_values(self):
        """Test OrganizerConfig default values."""
        from fuzzbin.common.config import OrganizerConfig
        
        config = OrganizerConfig()
        assert config.path_pattern == "{artist}/{title}"
        assert config.normalize_filenames is False

    def test_custom_values(self):
        """Test OrganizerConfig with custom values."""
        from fuzzbin.common.config import OrganizerConfig
        
        config = OrganizerConfig(
            path_pattern="{genre}/{artist}/{year}/{title}",
            normalize_filenames=True
        )
        assert config.path_pattern == "{genre}/{artist}/{year}/{title}"
        assert config.normalize_filenames is True

    def test_validate_pattern_valid(self):
        """Test validate_pattern with valid pattern."""
        from fuzzbin.common.config import OrganizerConfig
        
        config = OrganizerConfig(path_pattern="{artist}/{album}/{title}")
        # Should not raise
        config.validate_pattern()

    def test_validate_pattern_invalid(self):
        """Test validate_pattern with invalid field."""
        from fuzzbin.common.config import OrganizerConfig
        
        config = OrganizerConfig(path_pattern="{artist}/{invalid_field}")
        
        with pytest.raises(ValueError) as exc_info:
            config.validate_pattern()
        
        error_msg = str(exc_info.value)
        assert "invalid_field" in error_msg
        assert "Valid fields:" in error_msg

    def test_validate_pattern_multiple_invalid(self):
        """Test validate_pattern with multiple invalid fields."""
        from fuzzbin.common.config import OrganizerConfig
        
        config = OrganizerConfig(path_pattern="{invalid1}/{invalid2}/{title}")
        
        with pytest.raises(ValueError) as exc_info:
            config.validate_pattern()
        
        error_msg = str(exc_info.value)
        assert "invalid1" in error_msg or "invalid2" in error_msg

    def test_yaml_loading(self):
        """Test loading OrganizerConfig from YAML."""
        yaml_str = """
        organizer:
          path_pattern: "{genre}/{artist}/{title}"
          normalize_filenames: true
        """
        full_config = Config.from_yaml_string(yaml_str)
        
        assert full_config.organizer.path_pattern == "{genre}/{artist}/{title}"
        assert full_config.organizer.normalize_filenames is True
