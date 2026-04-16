"""Rate limiting and retry utilities.

Shared across all modules that make external API calls.
Prevents hitting rate limits and handles transient failures.
"""

from __future__ import annotations

import inspect
import time
import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from functools import wraps
from typing import Callable, Any

import httpx
from rich.console import Console

console = Console()


@dataclass
class RateLimiter:
    """Token bucket rate limiter.

    Usage:
        limiter = RateLimiter(calls_per_minute=30)
        limiter.wait()  # blocks until a slot is available
        make_api_call()
    """

    calls_per_minute: int = 30
    _timestamps: list[float] = field(default_factory=list)

    def _compute_sleep_time(self) -> float:
        """Purge stale timestamps and return required sleep duration."""
        now = time.monotonic()
        window = 60.0
        self._timestamps = [
            t for t in self._timestamps if now - t < window
        ]
        if len(self._timestamps) >= self.calls_per_minute:
            sleep_time = window - (now - self._timestamps[0]) + 0.1
            return max(sleep_time, 0.0)
        return 0.0

    def wait(self):
        """Block until we're under the rate limit."""
        sleep_time = self._compute_sleep_time()
        if sleep_time > 0:
            console.print(f"    [dim]Rate limit: sleeping {sleep_time:.1f}s[/]")
            time.sleep(sleep_time)
        self._timestamps.append(time.monotonic())

    async def async_wait(self):
        """Async version of wait."""
        sleep_time = self._compute_sleep_time()
        if sleep_time > 0:
            console.print(f"    [dim]Rate limit: sleeping {sleep_time:.1f}s[/]")
            await asyncio.sleep(sleep_time)
        self._timestamps.append(time.monotonic())


# Pre-configured limiters per service
RATE_LIMITS: dict[str, RateLimiter] = defaultdict(lambda: RateLimiter(calls_per_minute=30))

# Sensible defaults per service
SERVICE_LIMITS = {
    "serpapi": 60,
    "apify": 30,
    "outscraper": 20,
    "apollo": 50,
    "hunter": 30,
    "builtwith": 20,
    "anthropic": 40,
    "instantly": 30,
    "website_audit": 120,  # Our own crawling — be respectful
}


def get_limiter(service: str) -> RateLimiter:
    """Get or create a rate limiter for a service."""
    if service not in RATE_LIMITS:
        cpm = SERVICE_LIMITS.get(service, 30)
        RATE_LIMITS[service] = RateLimiter(calls_per_minute=cpm)
    return RATE_LIMITS[service]


def rate_limited(service: str):
    """Decorator that applies rate limiting to a function."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            limiter = get_limiter(service)
            limiter.wait()
            return func(*args, **kwargs)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            limiter = get_limiter(service)
            await limiter.async_wait()
            return await func(*args, **kwargs)

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return wrapper

    return decorator


def retry_with_rate_limit(service: str, max_attempts: int = 3):
    """Combined decorator: rate limit + retry."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            limiter = get_limiter(service)
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                limiter.wait()
                try:
                    return func(*args, **kwargs)
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429:
                        # Rate limited by the server — back off harder
                        backoff = min(60, 2 ** attempt * 5)
                        console.print(
                            f"    [yellow]429 rate limited, backing off {backoff}s[/]"
                        )
                        time.sleep(backoff)
                        last_exception = e
                    elif e.response.status_code >= 500:
                        # Server error — standard retry
                        time.sleep(2 ** attempt)
                        last_exception = e
                    else:
                        raise  # Client error, don't retry
                except httpx.TimeoutException as e:
                    time.sleep(2 ** attempt)
                    last_exception = e

            if last_exception:
                raise last_exception

        return wrapper

    return decorator
