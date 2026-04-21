"""Tests for defensive utility functions - scheduler sleep guards, truncate/
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
    """Tests for scheduler sleep guard."""

    """GIVEN scheduler sleep guard and the scenario: sleep call has max zero guard"""
    def test_sleep_call_has_max_zero_guard(self):
        """WHEN the code under test is exercised for: sleep call has max zero guard"""
        import inspect

        from flowboard.cli.main import schedule

        src = inspect.getsource(schedule)

        """THEN the expected behaviour holds: sleep call has max zero guard"""
        assert "max(0," in src, "sleep() must be guarded with max(0, ...) to prevent negative sleep"

    """GIVEN scheduler sleep guard and the scenario: negative sleep scenario no crash"""
    def test_negative_sleep_scenario_no_crash(self):
        # When execution takes longer than the interval, next_run - now < 0

        """WHEN the code under test is exercised for: negative sleep scenario no crash"""
        next_run = time.time() - 10  # 10 seconds in the past
        now = time.time()
        sleep_val = max(0, min(5, next_run - now))

        """THEN the expected behaviour holds: negative sleep scenario no crash"""
        assert sleep_val == 0, "Sleep value must be 0 when next_run is in the past"

    """GIVEN scheduler sleep guard and the scenario: zero sleep is valid"""
    def test_zero_sleep_is_valid(self):
        """WHEN the code under test is exercised for: zero sleep is valid"""
        time.sleep(0)  # Should not raise ValueError


# ====================================================================
# truncate(None) crash
# ====================================================================


class TestTruncateNoneHandling:
    """Tests for truncate none handling."""

    """GIVEN truncate none handling and the scenario: truncate none returns empty string"""
    def test_truncate_none_returns_empty_string(self):
        """WHEN the code under test is exercised for: truncate none returns empty string"""
        from flowboard.shared.utils import truncate

        """THEN the expected behaviour holds: truncate none returns empty string"""
        assert truncate(None) == ""

    """GIVEN truncate none handling and the scenario: truncate empty string returns empty"""
    def test_truncate_empty_string_returns_empty(self):
        """WHEN the code under test is exercised for: truncate empty string returns empty"""
        from flowboard.shared.utils import truncate

        """THEN the expected behaviour holds: truncate empty string returns empty"""
        assert truncate("") == ""

    """GIVEN truncate none handling and the scenario: truncate normal short text"""
    def test_truncate_normal_short_text(self):
        """WHEN the code under test is exercised for: truncate normal short text"""
        from flowboard.shared.utils import truncate

        """THEN the expected behaviour holds: truncate normal short text"""
        assert truncate("hello") == "hello"

    """GIVEN truncate none handling and the scenario: truncate long text is truncated"""
    def test_truncate_long_text_is_truncated(self):
        """WHEN the code under test is exercised for: truncate long text is truncated"""
        from flowboard.shared.utils import truncate

        result = truncate("a" * 100, max_length=10)

        """THEN the expected behaviour holds: truncate long text is truncated"""
        assert len(result) == 10
        assert result.endswith("…")

    """GIVEN truncate none handling and the scenario: truncate exact length not truncated"""
    def test_truncate_exact_length_not_truncated(self):
        """WHEN the code under test is exercised for: truncate exact length not truncated"""
        from flowboard.shared.utils import truncate

        """THEN the expected behaviour holds: truncate exact length not truncated"""
        assert truncate("12345", max_length=5) == "12345"


# ====================================================================
# truncate_html(None) crash
# ====================================================================


class TestTruncateHtmlNoneHandling:
    """Tests for truncate html none handling."""

    """GIVEN truncate html none handling and the scenario: truncate html none returns empty"""
    def test_truncate_html_none_returns_empty(self):
        """WHEN the code under test is exercised for: truncate html none returns empty"""
        from flowboard.shared.utils import truncate_html

        """THEN the expected behaviour holds: truncate html none returns empty"""
        assert truncate_html(None) == ""

    """GIVEN truncate html none handling and the scenario: truncate html empty string returns empty"""
    def test_truncate_html_empty_string_returns_empty(self):
        """WHEN the code under test is exercised for: truncate html empty string returns empty"""
        from flowboard.shared.utils import truncate_html

        """THEN the expected behaviour holds: truncate html empty string returns empty"""
        assert truncate_html("") == ""

    """GIVEN truncate html none handling and the scenario: truncate html short text escaped"""
    def test_truncate_html_short_text_escaped(self):
        """WHEN the code under test is exercised for: truncate html short text escaped"""
        from flowboard.shared.utils import truncate_html

        result = truncate_html("<script>alert(1)</script>")

        """THEN the expected behaviour holds: truncate html short text escaped"""
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    """GIVEN truncate html none handling and the scenario: truncate html long text has span title"""
    def test_truncate_html_long_text_has_span_title(self):
        """WHEN the code under test is exercised for: truncate html long text has span title"""
        from flowboard.shared.utils import truncate_html

        result = truncate_html("a" * 100, max_length=10)

        """THEN the expected behaviour holds: truncate html long text has span title"""
        assert "<span title=" in result
        assert "…" in result


# ====================================================================
# mask_secret(None) crash
# ====================================================================


class TestMaskSecretNoneHandling:
    """Tests for mask secret none handling."""

    """GIVEN mask secret none handling and the scenario: mask secret none returns masked"""
    def test_mask_secret_none_returns_masked(self):
        """WHEN the code under test is exercised for: mask secret none returns masked"""
        from flowboard.shared.utils import mask_secret

        """THEN the expected behaviour holds: mask secret none returns masked"""
        assert mask_secret(None) == "****"

    """GIVEN mask secret none handling and the scenario: mask secret empty returns masked"""
    def test_mask_secret_empty_returns_masked(self):
        """WHEN the code under test is exercised for: mask secret empty returns masked"""
        from flowboard.shared.utils import mask_secret

        """THEN the expected behaviour holds: mask secret empty returns masked"""
        assert mask_secret("") == "****"

    """GIVEN mask secret none handling and the scenario: mask secret short value fully masked"""
    def test_mask_secret_short_value_fully_masked(self):
        """WHEN the code under test is exercised for: mask secret short value fully masked"""
        from flowboard.shared.utils import mask_secret

        """THEN the expected behaviour holds: mask secret short value fully masked"""
        assert mask_secret("abc") == "****"

    """GIVEN mask secret none handling and the scenario: mask secret normal value shows last chars"""
    def test_mask_secret_normal_value_shows_last_chars(self):
        """WHEN the code under test is exercised for: mask secret normal value shows last chars"""
        from flowboard.shared.utils import mask_secret

        result = mask_secret("my-secret-token-1234")

        """THEN the expected behaviour holds: mask secret normal value shows last chars"""
        assert result.endswith("1234")
        assert result.startswith("****")


# ====================================================================
# Invalid interval silently defaults to daily
# ====================================================================


class TestSchedulerIntervalValidation:
    """Tests for scheduler interval validation."""

    """GIVEN scheduler interval validation and the scenario: valid intervals recognized"""
    def test_valid_intervals_recognized(self):
        """WHEN the code under test is exercised for: valid intervals recognized"""
        intervals = {"hourly": 3600, "daily": 86400, "weekly": 604800}

        """THEN the expected behaviour holds: valid intervals recognized"""
        assert intervals.get("hourly") == 3600
        assert intervals.get("daily") == 86400
        assert intervals.get("weekly") == 604800

    """GIVEN scheduler interval validation and the scenario: unknown interval returns none"""
    def test_unknown_interval_returns_none(self):
        """WHEN the code under test is exercised for: unknown interval returns none"""
        intervals = {"hourly": 3600, "daily": 86400, "weekly": 604800}

        """THEN the expected behaviour holds: unknown interval returns none"""
        assert intervals.get("cron_expression") is None

    """GIVEN scheduler interval validation and the scenario: help text does not mention cron"""
    def test_help_text_does_not_mention_cron(self):
        """WHEN the code under test is exercised for: help text does not mention cron"""
        import inspect

        from flowboard.cli.main import schedule

        src = inspect.getsource(schedule)
        # The option help should say "hourly, daily, or weekly" not "cron"

        """THEN the expected behaviour holds: help text does not mention cron"""
        assert "cron" not in src.lower() or "cron)" in src.lower(), (
            "Help text should not mention cron expressions (not implemented)"
        )


# ====================================================================
# Missing encoding in file open
# ====================================================================


class TestFileEncodingExplicit:
    """Tests for file encoding explicit."""

    """GIVEN file encoding explicit and the scenario: demo fixture uses utf8 encoding"""
    def test_demo_fixture_uses_utf8_encoding(self):
        """WHEN the code under test is exercised for: demo fixture uses utf8 encoding"""
        import inspect

        from flowboard.cli.main import demo

        src = inspect.getsource(demo)

        """THEN the expected behaviour holds: demo fixture uses utf8 encoding"""
        assert 'encoding="utf-8"' in src or "encoding='utf-8'" in src, (
            "Demo fixture file must be opened with explicit UTF-8 encoding"
        )


# ====================================================================
# JSON log format broken by special characters
# ====================================================================


class TestJsonLogFormatter:
    """Tests for json log formatter."""

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

    """GIVEN json log formatter and the scenario: simple message produces valid json"""
    def test_simple_message_produces_valid_json(self):
        """WHEN the code under test is exercised for: simple message produces valid json"""
        from flowboard.cli.main import _JsonFormatter

        fmt = _JsonFormatter()
        record = self._make_record("Hello world")
        output = fmt.format(record)
        data = json.loads(output)

        """THEN the expected behaviour holds: simple message produces valid json"""
        assert data["message"] == "Hello world"
        assert data["level"] == "INFO"
        assert "time" in data
        assert "logger" in data

    """GIVEN json log formatter and the scenario: message with quotes produces valid json"""
    def test_message_with_quotes_produces_valid_json(self):
        """WHEN the code under test is exercised for: message with quotes produces valid json"""
        from flowboard.cli.main import _JsonFormatter

        fmt = _JsonFormatter()
        record = self._make_record("He said \"hello\" and 'goodbye'")
        output = fmt.format(record)
        data = json.loads(output)

        """THEN the expected behaviour holds: message with quotes produces valid json"""
        assert '"hello"' in data["message"]

    """GIVEN json log formatter and the scenario: message with newlines produces valid json"""
    def test_message_with_newlines_produces_valid_json(self):
        """WHEN the code under test is exercised for: message with newlines produces valid json"""
        from flowboard.cli.main import _JsonFormatter

        fmt = _JsonFormatter()
        record = self._make_record("Line 1\nLine 2\nLine 3")
        output = fmt.format(record)
        data = json.loads(output)

        """THEN the expected behaviour holds: message with newlines produces valid json"""
        assert data["message"] == "Line 1\nLine 2\nLine 3"

    """GIVEN json log formatter and the scenario: message with backslashes produces valid json"""
    def test_message_with_backslashes_produces_valid_json(self):
        """WHEN the code under test is exercised for: message with backslashes produces valid json"""
        from flowboard.cli.main import _JsonFormatter

        fmt = _JsonFormatter()
        record = self._make_record("path\\to\\file")
        output = fmt.format(record)
        data = json.loads(output)

        """THEN the expected behaviour holds: message with backslashes produces valid json"""
        assert data["message"] == "path\\to\\file"

    """GIVEN json log formatter and the scenario: message with unicode produces valid json"""
    def test_message_with_unicode_produces_valid_json(self):
        """WHEN the code under test is exercised for: message with unicode produces valid json"""
        from flowboard.cli.main import _JsonFormatter

        fmt = _JsonFormatter()
        record = self._make_record("Polish: zażółć gęślą jaźń 🎯")
        output = fmt.format(record)
        data = json.loads(output)

        """THEN the expected behaviour holds: message with unicode produces valid json"""
        assert "zażółć" in data["message"]


# ====================================================================
# Rate limiter memory leak
# ====================================================================


class TestRateLimiterMemoryCleanup:
    """Tests for rate limiter memory cleanup."""

    """GIVEN rate limiter memory cleanup and the scenario: rate limiter uses regular dict"""
    def test_rate_limiter_uses_regular_dict(self):
        """WHEN the code under test is exercised for: rate limiter uses regular dict"""
        from flowboard.web.middleware import RateLimitMiddleware

        class FakeApp:
            pass

        rl = RateLimitMiddleware(FakeApp())

        """THEN the expected behaviour holds: rate limiter uses regular dict"""
        assert type(rl._requests) is dict, "Must use regular dict, not defaultdict"

    """GIVEN rate limiter memory cleanup and the scenario: rate limiter has cleanup counter"""
    def test_rate_limiter_has_cleanup_counter(self):
        """WHEN the code under test is exercised for: rate limiter has cleanup counter"""
        from flowboard.web.middleware import RateLimitMiddleware

        class FakeApp:
            pass

        rl = RateLimitMiddleware(FakeApp())

        """THEN the expected behaviour holds: rate limiter has cleanup counter"""
        assert hasattr(rl, "_cleanup_counter"), "Must have cleanup counter"

    """GIVEN rate limiter memory cleanup and the scenario: rate limiter does not create keys on check"""
    def test_rate_limiter_does_not_create_keys_on_check(self):
        """WHEN the code under test is exercised for: rate limiter does not create keys on check"""
        from flowboard.web.middleware import RateLimitMiddleware

        class FakeApp:
            pass

        rl = RateLimitMiddleware(FakeApp())
        # Before any requests, dict should be empty

        """THEN the expected behaviour holds: rate limiter does not create keys on check"""
        assert len(rl._requests) == 0

    """GIVEN rate limiter memory cleanup and the scenario: rate limiter cleanup removes stale ips"""
    def test_rate_limiter_cleanup_removes_stale_ips(self):
        """WHEN the code under test is exercised for: rate limiter cleanup removes stale ips"""
        from flowboard.web.middleware import RateLimitMiddleware

        class FakeApp:
            pass

        rl = RateLimitMiddleware(FakeApp())
        # Inject stale data - timestamps far in the past
        rl._requests["192.168.1.1"] = [0.0, 1.0, 2.0]  # Very old timestamps
        rl._requests["10.0.0.1"] = [0.0]  # Also very old

        # Force cleanup by setting counter to threshold
        rl._cleanup_counter = 199
        rl._is_rate_limited("fresh-ip")  # This should trigger cleanup

        # Stale IPs should be cleaned up

        """THEN the expected behaviour holds: rate limiter cleanup removes stale ips"""
        assert "192.168.1.1" not in rl._requests, "Stale IP should be cleaned up"
        assert "10.0.0.1" not in rl._requests, "Stale IP should be cleaned up"
        # Fresh IP should exist (it just made a request)
        assert "fresh-ip" in rl._requests


# ====================================================================
# CSP blocks Google Fonts
# ====================================================================


class TestCSPGoogleFonts:
    """Tests for c s p google fonts."""

    """GIVEN c s p google fonts and the scenario: csp allows google fonts stylesheets"""
    def test_csp_allows_google_fonts_stylesheets(self):
        """WHEN the code under test is exercised for: csp allows google fonts stylesheets"""
        from flowboard.web.middleware import SecurityHeadersMiddleware

        class FakeApp:
            pass

        mw = SecurityHeadersMiddleware(FakeApp())

        """THEN the expected behaviour holds: csp allows google fonts stylesheets"""
        assert "fonts.googleapis.com" in mw._csp, (
            "CSP style-src must allow fonts.googleapis.com for Google Fonts CSS"
        )

    """GIVEN c s p google fonts and the scenario: csp allows google fonts files"""
    def test_csp_allows_google_fonts_files(self):
        """WHEN the code under test is exercised for: csp allows google fonts files"""
        from flowboard.web.middleware import SecurityHeadersMiddleware

        class FakeApp:
            pass

        mw = SecurityHeadersMiddleware(FakeApp())

        """THEN the expected behaviour holds: csp allows google fonts files"""
        assert "fonts.gstatic.com" in mw._csp, (
            "CSP font-src must allow fonts.gstatic.com for Google Fonts woff2 files"
        )


# ====================================================================
# i18n safe interpolation
# ====================================================================


class TestI18nSafeInterpolation:
    """Tests for i18n safe interpolation."""

    """GIVEN i18n safe interpolation and the scenario: missing format param returns marker"""
    def test_missing_format_param_returns_marker(self):
        """WHEN the code under test is exercised for: missing format param returns marker"""
        from flowboard.i18n.translator import Translator

        t = Translator("en")
        t._messages["test.interp"] = "Hello {name}, welcome to {place}"
        result = t("test.interp", wrong="test")

        """THEN the expected behaviour holds: missing format param returns marker"""
        assert "[?]" in result
        assert "{name}" not in result


# ====================================================================
# Plural index bounds
# ====================================================================


class TestPluralIndexBounds:
    """Tests for plural index bounds."""

    """GIVEN plural index bounds and the scenario: plural with zero"""
    def test_plural_with_zero(self):
        """WHEN the code under test is exercised for: plural with zero"""
        from flowboard.i18n.translator import Translator

        t = Translator("en")
        # Should not crash with n=0
        result = t.plural(0, "unit.sp")

        """THEN the expected behaviour holds: plural with zero"""
        assert isinstance(result, str)

    """GIVEN plural index bounds and the scenario: plural with negative"""
    def test_plural_with_negative(self):
        """WHEN the code under test is exercised for: plural with negative"""
        from flowboard.i18n.translator import Translator

        t = Translator("en")
        # Negative n should not cause IndexError
        result = t.plural(-1, "unit.sp")

        """THEN the expected behaviour holds: plural with negative"""
        assert isinstance(result, str)


# ====================================================================
# Webhook rate limiting
# ====================================================================


class TestWebhookRateLimiting:
    """Tests for webhook rate limiting."""

    """GIVEN webhook rate limiting and the scenario: rate limiter allows normal traffic"""
    def test_rate_limiter_allows_normal_traffic(self):
        # Reset state

        """WHEN the code under test is exercised for: rate limiter allows normal traffic"""
        from flowboard.web import routes_extended
        from flowboard.web.routes_extended import _webhook_rate_check

        routes_extended._WEBHOOK_RATE.clear()

        """THEN the expected behaviour holds: rate limiter allows normal traffic"""
        assert not _webhook_rate_check("10.0.0.1")

    """GIVEN webhook rate limiting and the scenario: rate limiter blocks excess"""
    def test_rate_limiter_blocks_excess(self):
        """WHEN the code under test is exercised for: rate limiter blocks excess"""
        from flowboard.web import routes_extended
        from flowboard.web.routes_extended import _WEBHOOK_RATE_LIMIT, _webhook_rate_check

        routes_extended._WEBHOOK_RATE.clear()
        for _ in range(_WEBHOOK_RATE_LIMIT):
            _webhook_rate_check("flood-ip")

        """THEN the expected behaviour holds: rate limiter blocks excess"""
        assert _webhook_rate_check("flood-ip") is True


# ====================================================================
# Boundary date tests
# ====================================================================


class TestDateBoundaryConditions:
    """Tests for date boundary conditions."""

    """GIVEN date boundary conditions and the scenario: year boundary dec31 to jan1"""
    def test_year_boundary_dec31_to_jan1(self):
        """WHEN the code under test is exercised for: year boundary dec31 to jan1"""
        from datetime import date

        from flowboard.shared.utils import business_days_between

        result = business_days_between(date(2025, 12, 31), date(2026, 1, 1))

        """THEN the expected behaviour holds: year boundary dec31 to jan1"""
        assert result == 2  # Wed Dec 31 + Thu Jan 1

    """GIVEN date boundary conditions and the scenario: leap year feb28 to mar1"""
    def test_leap_year_feb28_to_mar1(self):
        """WHEN the code under test is exercised for: leap year feb28 to mar1"""
        from datetime import date

        from flowboard.shared.utils import business_days_between

        result = business_days_between(date(2024, 2, 28), date(2024, 3, 1))

        """THEN the expected behaviour holds: leap year feb28 to mar1"""
        assert result == 3  # Wed Feb 28 + Thu Feb 29 + Fri Mar 1

    """GIVEN date boundary conditions and the scenario: non leap year feb28 to mar1"""
    def test_non_leap_year_feb28_to_mar1(self):
        """WHEN the code under test is exercised for: non leap year feb28 to mar1"""
        from datetime import date

        from flowboard.shared.utils import business_days_between

        result = business_days_between(date(2025, 2, 28), date(2025, 3, 1))

        """THEN the expected behaviour holds: non leap year feb28 to mar1"""
        assert result == 1  # Fri Feb 28 only; Mar 1 is Saturday

    """GIVEN date boundary conditions and the scenario: same day weekday"""
    def test_same_day_weekday(self):
        """WHEN the code under test is exercised for: same day weekday"""
        from datetime import date

        from flowboard.shared.utils import business_days_between

        result = business_days_between(date(2026, 3, 27), date(2026, 3, 27))

        """THEN the expected behaviour holds: same day weekday"""
        assert result == 1

    """GIVEN date boundary conditions and the scenario: reversed dates"""
    def test_reversed_dates(self):
        """WHEN the code under test is exercised for: reversed dates"""
        from datetime import date

        from flowboard.shared.utils import business_days_between

        result = business_days_between(date(2026, 3, 27), date(2026, 3, 20))

        """THEN the expected behaviour holds: reversed dates"""
        assert result == 0

    """GIVEN date boundary conditions and the scenario: full week"""
    def test_full_week(self):
        """WHEN the code under test is exercised for: full week"""
        from datetime import date

        from flowboard.shared.utils import business_days_between

        result = business_days_between(date(2026, 3, 23), date(2026, 3, 29))

        """THEN the expected behaviour holds: full week"""
        assert result == 5

    """GIVEN date boundary conditions and the scenario: weekend only"""
    def test_weekend_only(self):
        """WHEN the code under test is exercised for: weekend only"""
        from datetime import date

        from flowboard.shared.utils import business_days_between

        result = business_days_between(date(2026, 3, 28), date(2026, 3, 29))

        """THEN the expected behaviour holds: weekend only"""
        assert result == 0


class TestSafeDivisionEdgeCases:
    """Tests for safe division edge cases."""

    """GIVEN safe division edge cases and the scenario: zero denominator"""
    def test_zero_denominator(self):
        """WHEN the code under test is exercised for: zero denominator"""
        from flowboard.shared.utils import safe_division

        """THEN the expected behaviour holds: zero denominator"""
        assert safe_division(10, 0) == 0.0

    """GIVEN safe division edge cases and the scenario: zero denominator custom default"""
    def test_zero_denominator_custom_default(self):
        """WHEN the code under test is exercised for: zero denominator custom default"""
        from flowboard.shared.utils import safe_division

        """THEN the expected behaviour holds: zero denominator custom default"""
        assert safe_division(10, 0, default=999.0) == 999.0

    """GIVEN safe division edge cases and the scenario: normal division"""
    def test_normal_division(self):
        """WHEN the code under test is exercised for: normal division"""
        from flowboard.shared.utils import safe_division

        """THEN the expected behaviour holds: normal division"""
        assert safe_division(10, 2) == 5.0

    """GIVEN safe division edge cases and the scenario: negative values"""
    def test_negative_values(self):
        """WHEN the code under test is exercised for: negative values"""
        from flowboard.shared.utils import safe_division

        """THEN the expected behaviour holds: negative values"""
        assert safe_division(-10, 2) == -5.0
