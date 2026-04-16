"""Tests for rate limiting and retry utilities."""

import time
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.rate_limit import RateLimiter, get_limiter, rate_limited, retry_with_rate_limit, SERVICE_LIMITS


class TestRateLimiter:
    def test_allows_calls_within_limit(self):
        limiter = RateLimiter(calls_per_minute=10)
        start = time.monotonic()
        for _ in range(5):
            limiter.wait()
        elapsed = time.monotonic() - start
        assert elapsed < 1.0

    def test_blocks_when_limit_exceeded(self):
        limiter = RateLimiter(calls_per_minute=2)
        limiter.wait()
        limiter.wait()
        assert len(limiter._timestamps) == 2
        # A third call must trigger a sleep because the per-minute window is full
        with patch("time.sleep") as mock_sleep:
            limiter.wait()
            mock_sleep.assert_called()
            # The sleep duration must be positive (waiting out the window)
            assert mock_sleep.call_args[0][0] > 0

    @pytest.mark.asyncio
    async def test_async_wait(self):
        limiter = RateLimiter(calls_per_minute=10)
        await limiter.async_wait()
        await limiter.async_wait()
        assert len(limiter._timestamps) == 2


class TestGetLimiter:
    def test_creates_limiter_with_service_defaults(self):
        limiter = get_limiter("serpapi")
        assert limiter.calls_per_minute == SERVICE_LIMITS["serpapi"]

    def test_returns_same_instance(self):
        limiter1 = get_limiter("outscraper")
        limiter2 = get_limiter("outscraper")
        assert limiter1 is limiter2

    def test_unknown_service_gets_default(self):
        limiter = get_limiter("unknown_service_xyz")
        assert limiter.calls_per_minute == 30


class TestRateLimitedDecorator:
    def test_sync_function(self):
        call_count = 0

        @rate_limited("website_audit")
        def my_func():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = my_func()
        assert result == "ok"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_async_function(self):
        call_count = 0

        @rate_limited("website_audit")
        async def my_async_func():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = await my_async_func()
        assert result == "ok"
        assert call_count == 1


class TestRetryWithRateLimit:
    def test_succeeds_on_first_try(self):
        @retry_with_rate_limit("serpapi", max_attempts=3)
        def success():
            return "done"

        assert success() == "done"

    def test_retries_on_429(self):
        attempt = 0

        @retry_with_rate_limit("serpapi", max_attempts=3)
        def flaky():
            nonlocal attempt
            attempt += 1
            if attempt < 2:
                response = httpx.Response(429, request=httpx.Request("GET", "https://example.com"))
                raise httpx.HTTPStatusError("rate limited", request=response.request, response=response)
            return "recovered"

        result = flaky()
        assert result == "recovered"
        assert attempt == 2

    def test_retries_on_500(self):
        attempt = 0

        @retry_with_rate_limit("serpapi", max_attempts=3)
        def server_error():
            nonlocal attempt
            attempt += 1
            if attempt < 2:
                response = httpx.Response(500, request=httpx.Request("GET", "https://example.com"))
                raise httpx.HTTPStatusError("server error", request=response.request, response=response)
            return "recovered"

        result = server_error()
        assert result == "recovered"

    def test_no_retry_on_400(self):
        @retry_with_rate_limit("serpapi", max_attempts=3)
        def bad_request():
            response = httpx.Response(400, request=httpx.Request("GET", "https://example.com"))
            raise httpx.HTTPStatusError("bad request", request=response.request, response=response)

        with pytest.raises(httpx.HTTPStatusError):
            bad_request()

    def test_raises_after_max_attempts(self):
        @retry_with_rate_limit("serpapi", max_attempts=2)
        def always_fails():
            response = httpx.Response(500, request=httpx.Request("GET", "https://example.com"))
            raise httpx.HTTPStatusError("server error", request=response.request, response=response)

        with pytest.raises(httpx.HTTPStatusError):
            always_fails()

    def test_retries_on_timeout(self):
        attempt = 0

        @retry_with_rate_limit("serpapi", max_attempts=3)
        def timeout_then_ok():
            nonlocal attempt
            attempt += 1
            if attempt < 2:
                raise httpx.TimeoutException("timed out")
            return "recovered"

        result = timeout_then_ok()
        assert result == "recovered"
        assert attempt == 2

    def test_timeout_exhausts_retries(self):
        @retry_with_rate_limit("serpapi", max_attempts=2)
        def always_timeout():
            raise httpx.TimeoutException("timed out")

        with pytest.raises(httpx.TimeoutException):
            always_timeout()


class TestRateLimiterSleepPaths:
    def test_sync_wait_sleeps_when_full(self):
        limiter = RateLimiter(calls_per_minute=1)
        # Fill the window with a recent timestamp
        limiter._timestamps = [time.monotonic()]
        with patch("time.sleep") as mock_sleep:
            limiter.wait()
            mock_sleep.assert_called_once()
            assert mock_sleep.call_args[0][0] > 0

    @pytest.mark.asyncio
    async def test_async_wait_sleeps_when_full(self):
        limiter = RateLimiter(calls_per_minute=1)
        # Fill the window with a recent timestamp
        limiter._timestamps = [time.monotonic()]

        async def fake_sleep(duration):
            pass

        with patch("asyncio.sleep", side_effect=fake_sleep) as mock_sleep:
            await limiter.async_wait()
            mock_sleep.assert_called_once()
            assert mock_sleep.call_args[0][0] > 0
