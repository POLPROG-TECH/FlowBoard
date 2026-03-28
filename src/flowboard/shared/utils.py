"""Shared utility functions used across FlowBoard."""

from __future__ import annotations

import logging
from datetime import date, datetime

logger = logging.getLogger(__name__)


def parse_date(value: str | None) -> date | None:
    """Parse an ISO-style date string into a date object."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except (ValueError, AttributeError):
        logger.warning("Failed to parse date value: %r — treating as missing.", value)
        return None


def parse_datetime(value: str | None) -> datetime | None:
    """Parse an ISO-style datetime string."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        logger.warning("Failed to parse datetime value: %r — treating as missing.", value)
        return None


def days_between(start: date | None, end: date | None) -> int | None:
    """Return the number of days between two dates, or None if either is missing."""
    if start is None or end is None:
        return None
    return (end - start).days


def business_days_between(start: date, end: date) -> int:
    """Count business days (Mon-Fri) between two dates, inclusive of start.

    Uses an O(1) arithmetic formula instead of day-by-day iteration
    for better performance with large date ranges.
    """
    if start > end:
        return 0
    total_days = (end - start).days + 1  # inclusive
    full_weeks, remainder = divmod(total_days, 7)
    count = full_weeks * 5
    # Count weekdays in the remaining partial week
    current_weekday = start.weekday()  # 0=Mon, 6=Sun
    for _ in range(remainder):
        if current_weekday < 5:
            count += 1
        current_weekday = (current_weekday + 1) % 7
    return count


def safe_division(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Divide safely, returning *default* when denominator is zero."""
    if denominator == 0:
        return default
    return numerator / denominator


def clamp(value: float, lo: float, hi: float) -> float:
    """Clamp *value* within [lo, hi]."""
    return max(lo, min(hi, value))


def truncate(text: str, max_length: int = 80) -> str:
    """Truncate text with an ellipsis if it exceeds *max_length*."""
    if not text:
        return text or ""
    if len(text) <= max_length:
        return text
    return text[: max_length - 1] + "…"


def truncate_html(text: str, max_length: int = 80) -> str:
    """Truncate text with ellipsis and wrap in a span with title for hover reveal."""
    from markupsafe import escape

    if not text:
        return ""
    if len(text) <= max_length:
        return str(escape(text))
    truncated = text[: max_length - 1] + "…"
    return f'<span title="{escape(text)}">{escape(truncated)}</span>'


def mask_secret(value: str, visible: int = 4) -> str:
    """Return a masked version of a secret string, showing only last *visible* chars."""
    if not value:
        return "****"
    if len(value) <= visible:
        return "****"
    return "*" * (len(value) - visible) + value[-visible:]
