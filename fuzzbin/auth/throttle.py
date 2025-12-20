"""Simple in-memory brute-force login throttling."""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from threading import Lock
from typing import Dict, List

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class AttemptRecord:
    """Record of failed login attempts for an IP address."""

    timestamps: List[float] = field(default_factory=list)


class LoginThrottle:
    """
    Simple in-memory rate limiter for login attempts.

    Tracks failed login attempts per IP address and blocks requests
    that exceed the threshold within the time window.

    Attributes:
        max_attempts: Maximum failed attempts allowed per window (default: 5)
        window_seconds: Time window in seconds (default: 60)

    Example:
        >>> throttle = LoginThrottle(max_attempts=5, window_seconds=60)
        >>> if throttle.is_blocked("192.168.1.1"):
        ...     raise HTTPException(429, "Too many login attempts")
        >>> # On failed login:
        >>> throttle.record_failure("192.168.1.1")
    """

    def __init__(
        self,
        max_attempts: int = 5,
        window_seconds: int = 60,
    ):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts: Dict[str, AttemptRecord] = defaultdict(AttemptRecord)
        self._lock = Lock()

    def _cleanup_old_attempts(self, record: AttemptRecord) -> None:
        """Remove attempts older than the time window."""
        cutoff = time.time() - self.window_seconds
        record.timestamps = [ts for ts in record.timestamps if ts > cutoff]

    def is_blocked(self, ip_address: str) -> bool:
        """
        Check if an IP address is blocked due to too many failed attempts.

        Args:
            ip_address: The IP address to check

        Returns:
            True if blocked, False if allowed
        """
        with self._lock:
            record = self._attempts[ip_address]
            self._cleanup_old_attempts(record)
            is_blocked = len(record.timestamps) >= self.max_attempts

            if is_blocked:
                logger.warning(
                    "login_throttled",
                    ip_address=ip_address,
                    attempt_count=len(record.timestamps),
                    window_seconds=self.window_seconds,
                )

            return is_blocked

    def record_failure(self, ip_address: str) -> int:
        """
        Record a failed login attempt for an IP address.

        Args:
            ip_address: The IP address that had a failed attempt

        Returns:
            Current number of failed attempts in the window
        """
        with self._lock:
            record = self._attempts[ip_address]
            self._cleanup_old_attempts(record)
            record.timestamps.append(time.time())

            attempt_count = len(record.timestamps)
            logger.info(
                "login_attempt_failed",
                ip_address=ip_address,
                attempt_count=attempt_count,
                max_attempts=self.max_attempts,
            )

            return attempt_count

    def clear(self, ip_address: str) -> None:
        """
        Clear failed attempts for an IP address (e.g., after successful login).

        Args:
            ip_address: The IP address to clear
        """
        with self._lock:
            if ip_address in self._attempts:
                del self._attempts[ip_address]
                logger.debug("login_attempts_cleared", ip_address=ip_address)

    def get_remaining_attempts(self, ip_address: str) -> int:
        """
        Get the number of remaining login attempts for an IP.

        Args:
            ip_address: The IP address to check

        Returns:
            Number of remaining attempts before blocking
        """
        with self._lock:
            record = self._attempts[ip_address]
            self._cleanup_old_attempts(record)
            return max(0, self.max_attempts - len(record.timestamps))

    def get_retry_after(self, ip_address: str) -> int:
        """
        Get seconds until the oldest attempt expires (for Retry-After header).

        Args:
            ip_address: The IP address to check

        Returns:
            Seconds until an attempt slot opens, or 0 if not blocked
        """
        with self._lock:
            record = self._attempts[ip_address]
            self._cleanup_old_attempts(record)

            if len(record.timestamps) < self.max_attempts:
                return 0

            oldest = min(record.timestamps)
            retry_after = int(oldest + self.window_seconds - time.time())
            return max(0, retry_after)


# Global throttle instance
_throttle: LoginThrottle | None = None


@lru_cache
def get_login_throttle() -> LoginThrottle:
    """
    Get the global login throttle instance (cached).

    Returns:
        LoginThrottle instance with default settings
    """
    return LoginThrottle(max_attempts=5, window_seconds=60)
