"""Shared data-source adapters and fallback orchestration."""

from .core import (
    FetchResult,
    ProviderFetchError,
    SourceAdapter,
    SourceHealth,
    SourceRegistry,
    get_registry,
)

__all__ = [
    "FetchResult",
    "ProviderFetchError",
    "SourceAdapter",
    "SourceHealth",
    "SourceRegistry",
    "get_registry",
]
