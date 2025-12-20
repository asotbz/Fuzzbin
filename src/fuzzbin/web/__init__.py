"""FastAPI web API for Fuzzbin music video library management."""

from .main import create_app
from .settings import APISettings

__all__ = [
    "create_app",
    "APISettings",
]
