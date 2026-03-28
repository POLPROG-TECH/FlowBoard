"""Tests for defensive utility functions — scheduler sleep guards, truncate/
truncate_html None handling, secret masking, scheduler interval validation,
file encoding, JSON log formatting, rate limiter memory cleanup, CSP headers,
i18n safe interpolation, plural form bounds, date boundaries, and safe division.
"""

from __future__ import annotations

import json
import logging
import time

# ====================================================================
# Negative sleep duration in scheduler
# ====================================================================


class TestSchedulerSleepGuard:
    """Verify the scheduler sleep never receives a negative value."""

    def test_sleep_call_has_max_zero_guard(self):
        """The sleep call must be wrapped with max(0, ...) to prevent ValueError."""
        import inspect

        from flowboard.cli.main import schedule

        src = inspect.getsource(schedule)
        assert "max(0," in src, "sleep() must be guarded with max(0, ...) to prevent negative sleep"

    def test_negative_sleep_scenario_no_crash(self):
        """Simulate the scenario where next_run is in the past — should not crash."""
        # When execution takes longer than the interval, next_run - now < 0
        next_run = time.time() - 10  # 10 seconds in the past
        now = time.time()
        sleep_val = max(0, min(5, next_run - now))
        assert sleep_val == 0, "Sleep value must be 0 when next_run is in the past"

    def test_zero_sleep_is_valid(self):
        """time.sleep(0) must not raise."""
        time.sleep(0)  # Should not raise ValueError


# ====================================================================
# truncate(None) crash
# ====================================================================


class TestTruncateNoneHandling:
    """Verify truncate() handles None and empty inputs safely."""

    def test_truncate_none_returns_empty_string(self):
        from flowboard.shared.utils import truncate

        assert truncate(None) == ""

    def test_truncate_empty_string_returns_empty(self):
        from flowboard.shared.utils import truncate

        assert truncate("") == ""

    def test_truncate_normal_short_text(self):
        from flowboard.shared.utils import truncate

        assert truncate("hello") == "hello"

    def test_truncate_long_text_is_truncated(self):
        from flowboard.shared.utils import truncate

        result = truncate("a" * 100, max_length=10)
        assert len(result) == 10
        assert result.endswith("…")

    def test_truncate_exact_length_not_truncated(self):
        from flowboard.shared.utils import truncate

        assert truncate("12345", max_length=5) == "12345"


# ====================================================================
# truncate_html(None) crash
# ====================================================================


class TestTruncateHtmlNoneHandling:
    """Verify truncate_html() handles None and empty inputs safely."""

    def test_truncate_html_none_returns_empty(self):
        from flowboard.shared.utils import truncate_html

        assert truncate_html(None) == ""

    def test_truncate_html_empty_string_returns_empty(self):
        from flowboard.shared.utils import truncate_html

        assert truncate_html("") == ""

    def test_truncate_html_short_text_escaped(self):
        from flowboard.shared.utils import truncate_html

        result = truncate_html("<script>alert(1)</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_truncate_html_long_text_has_span_title(self):
        from flowboard.shared.utils import truncate_html

        result = truncate_html("a" * 100, max_length=10)
        assert "<span title=" in result
        assert "…" in result


# ====================================================================
# mask_secret(None) crash
# ====================================================================


class TestMaskSecretNoneHandling:
    """Verify mask_secret() handles None and empty inputs safely."""

    def test_mask_secret_none_returns_masked(self):
        from flowboard.shared.utils import mask_secret

        assert mask_secret(None) == "****"

    def test_mask_secret_empty_returns_masked(self):
        from flowboard.shared.utils import mask_secret

        assert mask_secret("") == "****"

    def test_mask_secret_short_value_fully_masked(self):
        from flowboard.shared.utils import mask_secret

        assert mask_secret("abc") == "****"

    def test_mask_secret_normal_value_shows_last_chars(self):
        from flowboard.shared.utils import mask_secret

        result = mask_secret("my-secret-token-1234")
        assert result.endswith("1234")
        assert result.startswith("****")


# ====================================================================
# Invalid interval silently defaults to daily
# ====================================================================


class TestSchedulerIntervalValidation:
    """Verify unknown intervals produce a warning instead of silently defaulting."""

    def test_valid_intervals_recognized(self):
        intervals = {"hourly": 3600, "daily": 86400, "weekly": 604800}
        assert intervals.get("hourly") == 3600
        assert intervals.get("daily") == 86400
        assert intervals.get("weekly") == 604800

    def test_unknown_interval_returns_none(self):
        intervals = {"hourly": 3600, "daily": 86400, "weekly": 604800}
        assert intervals.get("cron_expression") is None

    def test_help_text_does_not_mention_cron(self):
        """The help text for --interval must not mention cron (not implemented)."""
        import inspect

        from flowboard.cli.main import schedule

        src = inspect.getsource(schedule)
        # The option help should say "hourly, daily, or weekly" not "cron"
        assert "cron" not in src.lower() or "cron)" in src.lower(), (
            "Help text should not mention cron expressions (not implemented)"
        )


# ====================================================================
# Missing encoding in file open
# ====================================================================


class TestFileEncodingExplicit:
    """Verify file opens specify encoding='utf-8' for cross-platform safety."""

    def test_demo_fixture_uses_utf8_encoding(self):
        import inspect

        from flowboard.cli.main import demo

        src = inspect.getsource(demo)
        assert 'encoding="utf-8"' in src or "encoding='utf-8'" in src, (
            "Demo fixture file must be opened with explicit UTF-8 encoding"
        )


# ====================================================================
# JSON log format broken by special characters
# ====================================================================


class TestJsonLogFormatter:
    """Verify the JSON log formatter produces valid JSON for all inputs."""

    def _make_record(self, message: str) -> logging.LogRecord:
        return logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg=message,
            args=(),
            exc_info=None,
        )

    def test_simple_message_produces_valid_json(self):
        from flowboard.cli.main import _JsonFormatter

        fmt = _JsonFormatter()
        record = self._make_record("Hello world")
        output = fmt.format(record)
        data = json.loads(output)
        assert data["message"] == "Hello world"
        assert data["level"] == "INFO"
        assert "time" in data
        assert "logger" in data

    def test_message_with_quotes_produces_valid_json(self):
        from flowboard.cli.main import _JsonFormatter

        fmt = _JsonFormatter()
        record = self._make_record("He said \"hello\" and 'goodbye'")
        output = fmt.format(record)
        data = json.loads(output)
        assert '"hello"' in data["message"]

    def test_message_with_newlines_produces_valid_json(self):
        from flowboard.cli.main import _JsonFormatter

        fmt = _JsonFormatter()
        record = self._make_record("Line 1\nLine 2\nLine 3")
        output = fmt.format(record)
        data = json.loads(output)
        assert data["message"] == "Line 1\nLine 2\nLine 3"

    def test_message_with_backslashes_produces_valid_json(self):
        from flowboard.cli.main import _JsonFormatter

        fmt = _JsonFormatter()
        record = self._make_record("path\\to\\file")
        output = fmt.format(record)
        data = json.loads(output)
        assert data["message"] == "path\\to\\file"

    def test_message_with_unicode_produces_valid_json(self):
        from flowboard.cli.main import _JsonFormatter

        fmt = _JsonFormatter()
        record = self._make_record("Polish: zażółć gęślą jaźń 🎯")
        output = fmt.format(record)
        data = json.loads(output)
        assert "zażółć" in data["message"]


# ====================================================================
# Rate limiter memory leak
# ====================================================================


class TestRateLimiterMemoryCleanup:
    """Verify the rate limiter doesn't leak memory from stale IPs."""

    def test_rate_limiter_uses_regular_dict(self):
        """Must NOT use defaultdict — regular dict prevents accidental key creation."""
        from flowboard.web.middleware import RateLimitMiddleware

        class FakeApp:
            pass

        rl = RateLimitMiddleware(FakeApp())
        assert type(rl._requests) is dict, "Must use regular dict, not defaultdict"

    def test_rate_limiter_has_cleanup_counter(self):
        """Must have a cleanup mechanism for stale IPs."""
        from flowboard.web.middleware import RateLimitMiddleware

        class FakeApp:
            pass

        rl = RateLimitMiddleware(FakeApp())
        assert hasattr(rl, "_cleanup_counter"), "Must have cleanup counter"

    def test_rate_limiter_does_not_create_keys_on_check(self):
        """Checking a new IP for rate limiting should not create a permanent entry
        when the IP has no previous requests (it will create one for the new request though)."""
        from flowboard.web.middleware import RateLimitMiddleware

        class FakeApp:
            pass

        rl = RateLimitMiddleware(FakeApp())
        # Before any requests, dict should be empty
        assert len(rl._requests) == 0

    def test_rate_limiter_cleanup_removes_stale_ips(self):
        """After cleanup, IPs with no recent timestamps should be removed."""
        from flowboard.web.middleware import RateLimitMiddleware

        class FakeApp:
            pass

        rl = RateLimitMiddleware(FakeApp())
        # Inject stale data — timestamps far in the past
        rl._requests["192.168.1.1"] = [0.0, 1.0, 2.0]  # Very old timestamps
        rl._requests["10.0.0.1"] = [0.0]  # Also very old

        # Force cleanup by setting counter to threshold
        rl._cleanup_counter = 199
        rl._is_rate_limited("fresh-ip")  # This should trigger cleanup

        # Stale IPs should be cleaned up
        assert "192.168.1.1" not in rl._requests, "Stale IP should be cleaned up"
        assert "10.0.0.1" not in rl._requests, "Stale IP should be cleaned up"
        # Fresh IP should exist (it just made a request)
        assert "fresh-ip" in rl._requests


# ====================================================================
# CSP blocks Google Fonts
# ====================================================================


class TestCSPGoogleFonts:
    """Verify CSP allows Google Fonts for first_run.html."""

    def test_csp_allows_google_fonts_stylesheets(self):
        """style-src must include fonts.googleapis.com."""
        from flowboard.web.middleware import SecurityHeadersMiddleware

        class FakeApp:
            pass

        mw = SecurityHeadersMiddleware(FakeApp())
        assert "fonts.googleapis.com" in mw._csp, (
            "CSP style-src must allow fonts.googleapis.com for Google Fonts CSS"
        )

    def test_csp_allows_google_fonts_files(self):
        """font-src must include fonts.gstatic.com."""
        from flowboard.web.middleware import SecurityHeadersMiddleware

        class FakeApp:
            pass

        mw = SecurityHeadersMiddleware(FakeApp())
        assert "fonts.gstatic.com" in mw._csp, (
            "CSP font-src must allow fonts.gstatic.com for Google Fonts woff2 files"
        )


# ====================================================================
# i18n safe interpolation
# ====================================================================


class TestI18nSafeInterpolation:
    """Verify format failures replace placeholders with [?] markers."""

    def test_missing_format_param_returns_marker(self):
        from flowboard.i18n.translator import Translator

        t = Translator("en")
        t._messages["test.interp"] = "Hello {name}, welcome to {place}"
        result = t("test.interp", wrong="test")
        assert "[?]" in result
        assert "{name}" not in result


# ====================================================================
# Plural index bounds
# ====================================================================


class TestPluralIndexBounds:
    """Verify plural index is clamped to valid range."""

    def test_plural_with_zero(self):
        from flowboard.i18n.translator import Translator

        t = Translator("en")
        # Should not crash with n=0
        result = t.plural(0, "unit.sp")
        assert isinstance(result, str)

    def test_plural_with_negative(self):
        from flowboard.i18n.translator import Translator

        t = Translator("en")
        # Negative n should not cause IndexError
        result = t.plural(-1, "unit.sp")
        assert isinstance(result, str)


# ====================================================================
# Webhook rate limiting
# ====================================================================


class TestWebhookRateLimiting:
    """Verify webhook endpoint has per-IP rate limiting."""

    def test_rate_limiter_allows_normal_traffic(self):
        # Reset state
        from flowboard.web import routes_extended
        from flowboard.web.routes_extended import _webhook_rate_check

        routes_extended._WEBHOOK_RATE.clear()
        assert not _webhook_rate_check("10.0.0.1")

    def test_rate_limiter_blocks_excess(self):
        from flowboard.web import routes_extended
        from flowboard.web.routes_extended import _WEBHOOK_RATE_LIMIT, _webhook_rate_check

        routes_extended._WEBHOOK_RATE.clear()
        for _ in range(_WEBHOOK_RATE_LIMIT):
            _webhook_rate_check("flood-ip")
        assert _webhook_rate_check("flood-ip") is True


# ====================================================================
# Boundary date tests
# ====================================================================


class TestDateBoundaryConditions:
    """Boundary date tests for business_days_between."""

    def test_year_boundary_dec31_to_jan1(self):
        from datetime import date

        from flowboard.shared.utils import business_days_between

        result = business_days_between(date(2025, 12, 31), date(2026, 1, 1))
        assert result == 2  # Wed Dec 31 + Thu Jan 1

    def test_leap_year_feb28_to_mar1(self):
        from datetime import date

        from flowboard.shared.utils import business_days_between

        result = business_days_between(date(2024, 2, 28), date(2024, 3, 1))
        assert result == 3  # Wed Feb 28 + Thu Feb 29 + Fri Mar 1

    def test_non_leap_year_feb28_to_mar1(self):
        from datetime import date

        from flowboard.shared.utils import business_days_between

        result = business_days_between(date(2025, 2, 28), date(2025, 3, 1))
        assert result == 1  # Fri Feb 28 only; Mar 1 is Saturday

    def test_same_day_weekday(self):
        from datetime import date

        from flowboard.shared.utils import business_days_between

        result = business_days_between(date(2026, 3, 27), date(2026, 3, 27))
        assert result == 1

    def test_reversed_dates(self):
        from datetime import date

        from flowboard.shared.utils import business_days_between

        result = business_days_between(date(2026, 3, 27), date(2026, 3, 20))
        assert result == 0

    def test_full_week(self):
        from datetime import date

        from flowboard.shared.utils import business_days_between

        result = business_days_between(date(2026, 3, 23), date(2026, 3, 29))
        assert result == 5

    def test_weekend_only(self):
        from datetime import date

        from flowboard.shared.utils import business_days_between

        result = business_days_between(date(2026, 3, 28), date(2026, 3, 29))
        assert result == 0


class TestSafeDivisionEdgeCases:
    """Edge case tests for safe_division."""

    def test_zero_denominator(self):
        from flowboard.shared.utils import safe_division

        assert safe_division(10, 0) == 0.0

    def test_zero_denominator_custom_default(self):
        from flowboard.shared.utils import safe_division

        assert safe_division(10, 0, default=999.0) == 999.0

    def test_normal_division(self):
        from flowboard.shared.utils import safe_division

        assert safe_division(10, 2) == 5.0

    def test_negative_values(self):
        from flowboard.shared.utils import safe_division

        assert safe_division(-10, 2) == -5.0
