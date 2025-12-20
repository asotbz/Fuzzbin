"""Logging configuration using structlog for structured logging."""

import logging
import logging.handlers
from pathlib import Path
from typing import Any, Dict

import structlog

from .config import LoggingConfig


def setup_logging(config: LoggingConfig) -> None:
    """
    Configure logging based on configuration.

    This function sets up both structlog and standard library logging to work
    together, with appropriate handlers, formatters, and log levels.

    Args:
        config: LoggingConfig object with logging settings

    Example:
        >>> from fuzzbin.common.config import LoggingConfig
        >>> config = LoggingConfig(level="DEBUG", format="text")
        >>> setup_logging(config)
    """
    log_level = getattr(logging, config.level.upper())

    # Configure standard library logging (for third-party libraries)
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        handlers=[],
        force=True,
    )

    # Configure third-party library log levels
    default_third_party = {
        "httpx": "WARNING",
        "httpcore": "WARNING",
        "tenacity": "INFO",
    }
    third_party_config = {**default_third_party, **config.third_party}

    for library, level in third_party_config.items():
        logging.getLogger(library).setLevel(getattr(logging, level.upper()))

    # Setup structlog processors
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # Add appropriate renderer based on format
    if config.format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        # Text format with colors for development
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    # Setup handlers
    handlers = []

    if "console" in config.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        handlers.append(console_handler)

    if "file" in config.handlers and config.file:
        # Create log directory if it doesn't exist
        log_path = Path(config.file.path)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            filename=config.file.path,
            maxBytes=config.file.max_bytes,
            backupCount=config.file.backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(log_level)
        handlers.append(file_handler)

    # Configure root logger with handlers
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    for handler in handlers:
        root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> Any:
    """
    Get a structlog logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Structlog logger instance

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("operation_complete", status="success", duration=1.5)
    """
    return structlog.get_logger(name)


def bind_context(**kwargs: Any) -> None:
    """
    Bind context variables that will be included in all subsequent log messages.

    This is useful for adding request IDs, user IDs, or other contextual
    information that should appear in all logs within a scope.

    Args:
        **kwargs: Key-value pairs to bind to the logging context

    Example:
        >>> bind_context(request_id="abc-123", user_id=42)
        >>> logger.info("user_action")  # Will include request_id and user_id
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    """
    Clear all bound context variables.

    Example:
        >>> bind_context(request_id="abc-123")
        >>> # ... do some work ...
        >>> clear_context()  # Remove request_id from context
    """
    structlog.contextvars.clear_contextvars()
