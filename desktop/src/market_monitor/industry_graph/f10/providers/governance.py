"""Central request governance for every F10 provider.

All per-stock F10 page requests (normal calls and retries) must pass through
the rate limiter.  A provider that repeatedly fails with 403/429/empty or
structurally-broken responses trips a circuit breaker and is skipped until it
cools down, which keeps one hostile source from taking the whole enrichment
run down.
"""

from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass, field
from typing import Mapping, Sequence

from .base import ProviderBlocked, ProviderError

HARD_MAX_RPS = 10.0
DEFAULT_MAX_RPS = 4.0


class F10RateLimiter:
    """Thread-safe token-clock limiter with a hard 10 req/s ceiling."""

    def __init__(self, max_rps: float = DEFAULT_MAX_RPS) -> None:
        self.max_rps = validate_max_rps(max_rps)
        self._lock = threading.Lock()
        self._last_request_at = 0.0
        self._request_count = 0
        self._total_wait_seconds = 0.0

    @property
    def request_count(self) -> int:
        with self._lock:
            return self._request_count

    def wait(self) -> float:
        """Block until a request is allowed; returns the waited seconds."""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_at
            min_interval = 1.0 / self.max_rps
            wait_seconds = max(0.0, min_interval - elapsed)
            if wait_seconds > 0:
                time.sleep(wait_seconds)
            self._last_request_at = time.monotonic()
            self._request_count += 1
            self._total_wait_seconds += wait_seconds
            return wait_seconds

    def stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "maxRps": self.max_rps,
                "requestCount": self._request_count,
                "totalWaitSeconds": round(self._total_wait_seconds, 3),
            }


def validate_max_rps(max_rps: float) -> float:
    try:
        value = float(max_rps)
    except (TypeError, ValueError) as error:
        raise ValueError(f"max_rps must be a number, got {max_rps!r}") from error
    if value <= 0:
        raise ValueError("max_rps must be positive")
    if value > HARD_MAX_RPS:
        raise ValueError(f"max_rps cannot exceed {HARD_MAX_RPS:g} req/s")
    return value


@dataclass
class CircuitBreaker:
    """Per-provider failure breaker with a cooldown window."""

    name: str
    failure_threshold: int = 5
    reset_after_seconds: float = 300.0
    consecutive_failures: int = 0
    opened_at: float | None = None
    failure_reasons: list[str] = field(default_factory=list)
    successes: int = 0
    failures: int = 0
    blocked: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @property
    def is_open(self) -> bool:
        if self.opened_at is None:
            return False
        return (time.monotonic() - self.opened_at) < self.reset_after_seconds

    def allow(self) -> bool:
        return not self.is_open

    def record_success(self) -> None:
        with self._lock:
            self.consecutive_failures = 0
            self.opened_at = None
            self.failure_reasons.clear()
            self.successes += 1

    def record_failure(self, reason: str) -> bool:
        """Record a failure; returns True when the breaker just opened."""
        with self._lock:
            self.failures += 1
            self.consecutive_failures += 1
            if len(self.failure_reasons) < 20:
                self.failure_reasons.append(reason[:240])
            if self.consecutive_failures >= self.failure_threshold:
                if self.opened_at is None:
                    self.opened_at = time.monotonic()
                    return True
            return False

    def record_blocked(self, reason: str) -> bool:
        """Record a provider-blocked event (403/429/breaker open)."""
        with self._lock:
            self.blocked += 1
        return self.record_failure(reason)

    def stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "name": self.name,
                "open": self.is_open,
                "consecutiveFailures": self.consecutive_failures,
                "failureThreshold": self.failure_threshold,
                "successes": self.successes,
                "failures": self.failures,
                "blocked": self.blocked,
                "failureReasons": list(self.failure_reasons[-5:]),
            }


class F10Governance:
    """Holds one limiter plus per-provider circuit breakers."""

    def __init__(
        self,
        *,
        max_rps: float = DEFAULT_MAX_RPS,
        failure_threshold: int = 5,
        reset_after_seconds: float = 300.0,
    ) -> None:
        self.limiter = F10RateLimiter(max_rps)
        self.failure_threshold = failure_threshold
        self.reset_after_seconds = reset_after_seconds
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()

    def breaker(self, provider: str) -> CircuitBreaker:
        with self._lock:
            if provider not in self._breakers:
                self._breakers[provider] = CircuitBreaker(
                    name=provider,
                    failure_threshold=self.failure_threshold,
                    reset_after_seconds=self.reset_after_seconds,
                )
            return self._breakers[provider]

    def wait(self) -> float:
        return self.limiter.wait()

    def stats(self) -> dict[str, object]:
        return {
            "limiter": self.limiter.stats(),
            "breakers": {name: breaker.stats() for name, breaker in self._breakers.items()},
        }


_GOVERNANCE: F10Governance | None = None
_GOVERNANCE_LOCK = threading.Lock()


def get_governance(max_rps: float | None = None) -> F10Governance:
    """Return the process-wide governance singleton (optionally re-created)."""
    global _GOVERNANCE
    if max_rps is not None:
        with _GOVERNANCE_LOCK:
            _GOVERNANCE = F10Governance(max_rps=max_rps)
            return _GOVERNANCE
    with _GOVERNANCE_LOCK:
        if _GOVERNANCE is None:
            _GOVERNANCE = F10Governance()
        return _GOVERNANCE


def reset_governance() -> None:
    """Testing hook: clear the singleton so a fresh one is created."""
    global _GOVERNANCE
    with _GOVERNANCE_LOCK:
        _GOVERNANCE = None


def governed_get(
    url: str,
    *,
    provider: str,
    governance: F10Governance | None = None,
    attempts: int = 3,
    timeout: float = 18.0,
    encoding: str = "utf-8",
    backoff_base_seconds: float = 1.5,
    headers: Mapping[str, str] | Sequence[tuple[str, str]] | None = None,
) -> str:
    """Fetch a per-stock F10 page through the central limiter + breaker.

    Every attempt (including retries) acquires the limiter, so a burst of
    retries can never exceed the configured request rate.  The breaker is
    tripped on empty responses, 403/429 pages and structural failures; when
    open the function raises :class:`ProviderBlocked` immediately.
    """

    gov = governance or get_governance()
    breaker = gov.breaker(provider)
    if not breaker.allow():
        breaker.record_blocked(f"{provider} circuit breaker is open")
        raise ProviderBlocked(f"{provider} circuit breaker is open")
    # Lazy import avoids a module-load cycle with market_monitor.f10.
    from market_monitor.f10 import _get

    last_error: Exception | None = None
    for attempt in range(attempts):
        gov.wait()
        try:
            body = _get(url, timeout=timeout, encoding=encoding, headers=headers)
            if not body or not body.strip():
                raise ProviderError(f"empty response from {provider}")
            lowered = body[:400].lower()
            if "403 forbidden" in lowered or "forbidden" in lowered[:200]:
                raise ProviderBlocked(f"{provider} returned 403/forbidden")
            if "429" in lowered and ("too many requests" in lowered or "rate" in lowered):
                raise ProviderBlocked(f"{provider} returned 429 rate limited")
            breaker.record_success()
            return body
        except ProviderBlocked as error:
            breaker.record_blocked(str(error))
            raise
        except Exception as error:  # noqa: BLE001 - provider network failures
            last_error = error
            breaker.record_failure(str(error))
            if attempt + 1 < attempts:
                jitter = random.uniform(0.0, 0.3 * backoff_base_seconds)
                time.sleep(backoff_base_seconds * (2 ** attempt) + jitter)
    raise ProviderError(
        f"{provider} fetch failed after {attempts} attempts: {last_error}"
    ) from last_error


__all__ = (
    "CircuitBreaker",
    "DEFAULT_MAX_RPS",
    "F10Governance",
    "F10RateLimiter",
    "HARD_MAX_RPS",
    "get_governance",
    "governed_get",
    "reset_governance",
    "validate_max_rps",
)
