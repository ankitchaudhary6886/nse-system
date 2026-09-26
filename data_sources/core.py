"""Typed adapter contract, source health, and explicit fallback routing."""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from importlib import import_module
from pkgutil import iter_modules
from threading import Lock
from time import monotonic
from typing import Any, Callable, Deque, Dict, Iterable, List, Optional, Protocol


@dataclass(frozen=True)
class SourceHealth:
    provider: str
    datasets: List[str]
    state: str
    rate_limit_ok: bool
    calls: int
    failures: int
    last_success: Optional[str]
    last_error: Optional[str]


@dataclass(frozen=True)
class FetchResult:
    data: Any
    provider: str
    fetched_at: str


class SourceAdapter(Protocol):
    name: str
    datasets: Iterable[str]

    def fetch(self, *args: Any, **kwargs: Any) -> Any:
        ...

    def health(self) -> SourceHealth:
        ...

    def rate_limit_ok(self) -> bool:
        ...


class ProviderFetchError(RuntimeError):
    """Raised when no configured provider can return an acceptable result."""

    def __init__(self, dataset: str, errors: Dict[str, str]):
        self.dataset = dataset
        self.errors = errors
        details = "; ".join(f"{name}: {error}" for name, error in errors.items())
        super().__init__(f"No provider returned {dataset}: {details}")


class RateWindow:
    def __init__(self, max_calls: int, window_seconds: int):
        if max_calls < 1 or window_seconds < 1:
            raise ValueError("Rate window values must be positive")
        self.max_calls = max_calls
        self.window = timedelta(seconds=window_seconds)
        self._calls: Deque[float] = deque()
        self._lock = Lock()

    def allow(self) -> bool:
        now = monotonic()
        with self._lock:
            cutoff = now - self.window.total_seconds()
            while self._calls and self._calls[0] <= cutoff:
                self._calls.popleft()
            return len(self._calls) < self.max_calls

    def consume(self) -> bool:
        now = monotonic()
        with self._lock:
            cutoff = now - self.window.total_seconds()
            while self._calls and self._calls[0] <= cutoff:
                self._calls.popleft()
            if len(self._calls) >= self.max_calls:
                return False
            self._calls.append(now)
            return True


class BaseSourceAdapter:
    """Tracks per-process source health and enforces a local call budget."""

    name = "unnamed"
    datasets: Iterable[str] = ()

    def __init__(self, max_calls: int = 60, window_seconds: int = 60):
        self._rate_window = RateWindow(max_calls, window_seconds)
        self._calls = 0
        self._failures = 0
        self._last_success: Optional[str] = None
        self._last_error: Optional[str] = None
        self._lock = Lock()

    def rate_limit_ok(self) -> bool:
        return self._rate_window.allow()

    def health(self) -> SourceHealth:
        with self._lock:
            state = ("unavailable" if self._last_error else
                     "healthy" if self._last_success else "not_checked")
            return SourceHealth(
                provider=self.name,
                datasets=sorted(self.datasets),
                state=state,
                rate_limit_ok=self.rate_limit_ok(),
                calls=self._calls,
                failures=self._failures,
                last_success=self._last_success,
                last_error=self._last_error,
            )

    def _execute(self, operation: Callable[[], Any]) -> Any:
        if not self._rate_window.consume():
            raise RuntimeError("local provider rate limit exceeded")
        with self._lock:
            self._calls += 1
        try:
            result = operation()
        except Exception as exc:
            with self._lock:
                self._failures += 1
                self._last_error = f"{type(exc).__name__}: {exc}"
            raise
        with self._lock:
            self._last_success = datetime.now().isoformat(timespec="seconds")
            self._last_error = None
        return result

    def record_error(self, message: str) -> None:
        with self._lock:
            self._failures += 1
            self._last_error = message


class SourceRegistry:
    def __init__(self):
        self._adapters: Dict[str, SourceAdapter] = {}
        self._discovered = False
        self._lock = Lock()
        self._discovery_lock = Lock()

    def register(self, adapter: SourceAdapter) -> None:
        with self._lock:
            if adapter.name in self._adapters:
                raise ValueError(f"Duplicate data source: {adapter.name}")
            self._adapters[adapter.name] = adapter

    def discover(self) -> None:
        with self._discovery_lock:
            if self._discovered:
                return
            package = import_module("data_sources.adapters")
            for module in iter_modules(
                    package.__path__, package.__name__ + "."):
                loaded = import_module(module.name)
                register_adapters = getattr(
                    loaded, "register_adapters", None)
                if register_adapters is not None:
                    register_adapters(self)
            self._discovered = True

    def fetch(
        self,
        dataset: str,
        providers: Iterable[str],
        *args: Any,
        accept: Optional[Callable[[Any], bool]] = None,
        **kwargs: Any,
    ) -> FetchResult:
        self.discover()
        accept_result = accept or (lambda value: True)
        errors: Dict[str, str] = {}
        for provider_name in providers:
            adapter = self._adapters.get(provider_name)
            if adapter is None:
                errors[provider_name] = "provider is not registered"
                continue
            if dataset not in adapter.datasets:
                errors[provider_name] = f"provider does not support {dataset}"
                continue
            if not adapter.rate_limit_ok():
                errors[provider_name] = "provider rate limit exceeded"
                continue
            try:
                result = adapter.fetch(*args, **kwargs)
                if not accept_result(result):
                    errors[provider_name] = "provider result rejected"
                    record_error = getattr(adapter, "record_error", None)
                    if record_error is not None:
                        record_error("provider result rejected")
                    continue
                return FetchResult(
                    data=result,
                    provider=provider_name,
                    fetched_at=datetime.now().isoformat(timespec="seconds"),
                )
            except Exception as exc:
                errors[provider_name] = f"{type(exc).__name__}: {exc}"
        raise ProviderFetchError(dataset, errors)

    def health(self) -> List[Dict[str, Any]]:
        self.discover()
        return [asdict(adapter.health())
                for adapter in sorted(self._adapters.values(),
                                      key=lambda item: item.name)]


_registry = SourceRegistry()


def get_registry() -> SourceRegistry:
    return _registry
