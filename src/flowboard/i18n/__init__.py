"""FlowBoard internationalization (i18n) subsystem.

Provides a lightweight, JSON-based translation layer that supports:
- Two target locales: English (en), Polish (pl)
- Locale detection from config, environment, or explicit selection
- Key-based string lookup with fallback to English
- Interpolation via Python str.format() / str.format_map()
- Pluralization helpers for languages with complex plural rules (e.g. Polish)
- Locale-aware date/number formatting
"""

from flowboard.i18n.translator import (
    Translator,
    get_locale,
    get_translator,
    reset_locale,
    set_locale,
    supported_locales,
)

__all__ = [
    "Translator",
    "get_locale",
    "get_translator",
    "reset_locale",
    "set_locale",
    "supported_locales",
]
