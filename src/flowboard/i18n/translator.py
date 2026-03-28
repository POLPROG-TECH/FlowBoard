"""Core translator engine for FlowBoard i18n.

Loads JSON translation files, provides key-based lookup with fallback,
interpolation support, pluralization, and locale-aware formatting helpers.
"""

from __future__ import annotations

import json
import locale as _locale_mod
import logging
import math
import os
import threading
from datetime import date, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_LOCALE_DIR = Path(__file__).parent
_DEFAULT_LOCALE = "en"
_SUPPORTED_LOCALES = ("en", "pl")

# Thread-local storage for current locale
_state = threading.local()

# Loaded translation caches: locale -> {key: value}
_cache: dict[str, dict[str, Any]] = {}
_cache_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Month name tables (avoid system-locale dependency from strftime)
# ---------------------------------------------------------------------------
_MONTH_NAMES: dict[str, list[str]] = {
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "pl": ["sty", "lut", "mar", "kwi", "maj", "cze", "lip", "sie", "wrz", "paź", "lis", "gru"],
}

_MONTH_NAMES_FULL: dict[str, list[str]] = {
    "en": [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ],
    "pl": [
        "styczeń",
        "luty",
        "marzec",
        "kwiecień",
        "maj",
        "czerwiec",
        "lipiec",
        "sierpień",
        "wrzesień",
        "październik",
        "listopad",
        "grudzień",
    ],
}

# ---------------------------------------------------------------------------
# Number formatting per locale
# ---------------------------------------------------------------------------
_NUM_FMT: dict[str, tuple[str, str]] = {
    # (decimal_sep, thousands_sep)
    "en": (".", ","),
    "pl": (",", "\u00a0"),  # non-breaking space
}

# ---------------------------------------------------------------------------
# Datetime formatting per locale
# ---------------------------------------------------------------------------
_DATETIME_FORMATS: dict[str, str] = {
    "en": "%Y-%m-%d %H:%M",
    "pl": "%d.%m.%Y %H:%M",
}

# ---------------------------------------------------------------------------
# Polish pluralization rules
# ---------------------------------------------------------------------------


def _plural_index_pl(n: int) -> int:
    """Return Polish plural form index: 0=one, 1=few, 2=many."""
    n = abs(n)
    if n == 1:
        return 0
    mod10 = n % 10
    mod100 = n % 100
    if mod10 in (2, 3, 4) and mod100 not in (12, 13, 14):
        return 1
    return 2


_PLURAL_INDEX: dict[str, Any] = {
    "en": lambda n: 0 if abs(n) == 1 else 1,
    "pl": _plural_index_pl,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def supported_locales() -> tuple[str, ...]:
    """Return tuple of supported locale codes."""
    return _SUPPORTED_LOCALES


def get_locale() -> str:
    """Return the currently active locale code."""
    return getattr(_state, "locale", _DEFAULT_LOCALE)


def set_locale(locale_code: str) -> None:
    """Set the active locale. Falls back to 'en' if not supported."""
    code = _normalize_locale(locale_code)
    if code not in _SUPPORTED_LOCALES:
        logger.warning(
            "Unsupported locale '%s', falling back to '%s'", locale_code, _DEFAULT_LOCALE
        )
        code = _DEFAULT_LOCALE
    _state.locale = code


def reset_locale() -> None:
    """Reset thread-local locale to the default, cleaning up state."""
    _state.locale = _DEFAULT_LOCALE


class LocaleContext:
    """Context manager for thread-safe locale switching (Blocker #11).

    Usage::

        with locale_context("pl"):
            t = Translator()  # uses "pl"
        # locale is restored here
    """

    def __init__(self, locale_code: str) -> None:
        self._new_code = locale_code
        self._old_code: str | None = None

    def __enter__(self) -> str:
        self._old_code = get_locale()
        set_locale(self._new_code)
        return get_locale()

    def __exit__(self, *exc: Any) -> None:
        if self._old_code is not None:
            set_locale(self._old_code)
        else:
            reset_locale()


# Backward-compatible alias
locale_context = LocaleContext


def detect_locale() -> str:
    """Detect locale from environment: FLOWBOARD_LOCALE > LANG > default."""
    env_locale = os.environ.get("FLOWBOARD_LOCALE", "")
    if env_locale:
        code = _normalize_locale(env_locale)
        if code in _SUPPORTED_LOCALES:
            return code

    lang = os.environ.get("LANG", "")
    if lang:
        code = _normalize_locale(lang)
        if code in _SUPPORTED_LOCALES:
            return code

    try:
        sys_locale = _locale_mod.getlocale()[0] or ""
        code = _normalize_locale(sys_locale)
        if code in _SUPPORTED_LOCALES:
            return code
    except (ValueError, AttributeError):
        pass

    return _DEFAULT_LOCALE


def _normalize_locale(code: str) -> str:
    """Normalize locale codes like 'pl_PL.UTF-8' -> 'pl'."""
    code = code.strip().lower()
    code = code.split(".")[0]  # strip encoding
    code = code.split("@")[0]  # strip modifier
    code = code.split("_")[0]  # use just language part
    return code


def _load_translations(locale_code: str) -> dict[str, Any]:
    """Load and cache translation data for a given locale."""
    with _cache_lock:
        if locale_code in _cache:
            return _cache[locale_code]

        path = _LOCALE_DIR / f"{locale_code}.json"
        if not path.exists():
            logger.warning("Translation file not found: %s", path)
            _cache[locale_code] = {}
            return {}

        with path.open(encoding="utf-8") as fh:
            data: dict[str, Any] = json.load(fh)

        # Remove meta key
        data.pop("_meta", None)
        _cache[locale_code] = data
        return data


class Translator:
    """Translation lookup engine with fallback support.

    Usage::

        t = Translator("pl")
        t("tab.overview")                      # -> "📋 Przegląd"
        t("cli.error", error="x")              # -> "Błąd: x"
        t.plural(5, "day.one", "day.few", "day.many")  # -> "5 dni"
        t.format_date(some_date)               # -> "18 mar"
        t.format_number(1234.5)                # -> "1 234,5"
    """

    def __init__(self, locale_code: str | None = None) -> None:
        self._locale = locale_code or get_locale()
        if self._locale not in _SUPPORTED_LOCALES:
            self._locale = _DEFAULT_LOCALE
        self._messages = _load_translations(self._locale)
        self._fallback = (
            _load_translations(_DEFAULT_LOCALE) if self._locale != _DEFAULT_LOCALE else {}
        )

    @property
    def locale(self) -> str:
        return self._locale

    def __call__(self, key: str, /, *, fallback: str | None = None, **kwargs: Any) -> str:
        """Look up a translation key and interpolate variables."""
        raw = self._messages.get(key)
        if raw is None:
            raw = self._fallback.get(key)
            if raw is None:
                if fallback is not None:
                    return fallback
                logger.warning("Missing translation key: '%s' (locale=%s)", key, self._locale)
                return key
            if self._locale != _DEFAULT_LOCALE:
                logger.debug("Falling back to 'en' for key: '%s'", key)

        if not isinstance(raw, str):
            return str(raw)

        if kwargs:
            try:
                return raw.format(**kwargs)
            except (KeyError, IndexError, ValueError) as exc:
                logger.warning("Interpolation error for key '%s': %s", key, exc)
                import re as _re

                return _re.sub(r"\{[^}]+\}", "[?]", raw)

        return raw

    def has(self, key: str) -> bool:
        """Check if a key exists in the current locale or fallback."""
        return key in self._messages or key in self._fallback

    # ------------------------------------------------------------------
    # Pluralization
    # ------------------------------------------------------------------

    def plural(self, n: int, *form_keys: str, **kwargs: Any) -> str:
        """Select the correct plural form and interpolate.

        For English: plural(n, "key.one", "key.other")
        For Polish:  plural(n, "key.one", "key.few", "key.many")

        The variable ``{n}`` is automatically available for interpolation.
        """
        if not form_keys:
            return str(n)
        fn = _PLURAL_INDEX.get(self._locale, _PLURAL_INDEX["en"])
        idx = fn(n)
        idx = max(0, min(idx, len(form_keys) - 1))
        kwargs["n"] = n
        return self(form_keys[idx], **kwargs)

    # ------------------------------------------------------------------
    # Date formatting (locale-safe, no strftime month dependency)
    # ------------------------------------------------------------------

    def format_date_short(self, d: date) -> str:
        """Format a date as short locale string (e.g. 'Mar 18' / '18 mar')."""
        months = _MONTH_NAMES.get(self._locale, _MONTH_NAMES["en"])
        month = months[d.month - 1]
        if self._locale == "pl":
            return f"{d.day} {month}"
        return f"{month} {d.day:02d}"

    def format_date_full(self, d: date) -> str:
        """Format a date with year (e.g. 'Mar 18, 2026' / '18 mar 2026')."""
        months = _MONTH_NAMES.get(self._locale, _MONTH_NAMES["en"])
        month = months[d.month - 1]
        if self._locale == "pl":
            return f"{d.day} {month} {d.year}"
        return f"{month} {d.day:02d}, {d.year}"

    def format_month_year(self, d: date) -> str:
        """Format month+year for timeline axis (e.g. 'Mar 2026' / 'mar 2026')."""
        months = _MONTH_NAMES.get(self._locale, _MONTH_NAMES["en"])
        return f"{months[d.month - 1]} {d.year}"

    def format_month_short(self, d: date) -> str:
        """Format short month name (e.g. 'Mar' / 'mar')."""
        months = _MONTH_NAMES.get(self._locale, _MONTH_NAMES["en"])
        return months[d.month - 1]

    def format_datetime(self, dt: datetime) -> str:
        """Format a datetime with locale-appropriate pattern."""
        fmt = _DATETIME_FORMATS.get(self._locale, _DATETIME_FORMATS["en"])
        return dt.strftime(fmt)

    # ------------------------------------------------------------------
    # Number formatting
    # ------------------------------------------------------------------

    def format_number(self, value: float, decimals: int = 0) -> str:
        """Format a number with locale-appropriate separators."""
        if math.isnan(value) or math.isinf(value):
            return "—"
        dec_sep, thou_sep = _NUM_FMT.get(self._locale, _NUM_FMT["en"])
        if decimals == 0:
            int_val = round(value)
            sign = "-" if int_val < 0 else ""
            int_val = abs(int_val)
            s = str(int_val)
            # Insert thousands separators
            groups = []
            while s:
                groups.append(s[-3:])
                s = s[:-3]
            return sign + thou_sep.join(reversed(groups))
        else:
            formatted = f"{value:.{decimals}f}"
            int_part, dec_part = formatted.split(".")
            sign = "-" if int_part.startswith("-") else ""
            int_part = int_part.lstrip("-")
            groups = []
            while int_part:
                groups.append(int_part[-3:])
                int_part = int_part[:-3]
            return sign + thou_sep.join(reversed(groups)) + dec_sep + dec_part


def get_translator(locale_code: str | None = None) -> Translator:
    """Create a Translator for the given or current locale."""
    return Translator(locale_code or get_locale())
