"""Tests for the FlowBoard i18n subsystem."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import pytest

from flowboard.i18n.translator import (
    _LOCALE_DIR,
    Translator,
    _normalize_locale,
    get_locale,
    get_translator,
    set_locale,
    supported_locales,
)

I18N_DIR = Path(__file__).resolve().parent.parent / "src" / "flowboard" / "i18n"


class TestTranslatorBasics:
    """Core translator functionality."""

    def test_supported_locales(self) -> None:
        assert "en" in supported_locales()
        assert "pl" in supported_locales()

    def test_english_translator_returns_values(self) -> None:
        t = Translator("en")
        assert t("app.name") == "FlowBoard"
        assert t("tab.overview") == "📋 Overview"

    def test_polish_translator_returns_polish(self) -> None:
        t = Translator("pl")
        assert "Przegląd" in t("tab.overview")
        assert t("card.blocked") == "Zablokowane"

    def test_interpolation(self) -> None:
        t = Translator("en")
        result = t("cli.error", error="something broke")
        assert result == "Error: something broke"

    def test_polish_interpolation(self) -> None:
        t = Translator("pl")
        result = t("cli.error", error="coś się zepsuło")
        assert result == "Błąd: coś się zepsuło"

    def test_missing_key_returns_key(self) -> None:
        t = Translator("en")
        assert t("nonexistent.key") == "nonexistent.key"

    def test_fallback_to_english(self) -> None:
        t = Translator("pl")
        assert t("app.name") == "FlowBoard"  # same in both

    def test_unsupported_locale_falls_back(self) -> None:
        t = Translator("xx")
        assert t.locale == "en"
        assert t("app.name") == "FlowBoard"

    def test_has_key(self) -> None:
        t = Translator("en")
        assert t.has("app.name")
        assert not t.has("nonexistent.key.xyz")


class TestLocaleState:
    """Test global locale state management."""

    def test_default_locale(self) -> None:
        set_locale("en")
        assert get_locale() == "en"

    def test_set_locale(self) -> None:
        set_locale("pl")
        assert get_locale() == "pl"
        set_locale("en")  # reset

    def test_set_unsupported_locale_falls_back(self) -> None:
        set_locale("xx")
        assert get_locale() == "en"

    def test_get_translator_uses_current_locale(self) -> None:
        set_locale("pl")
        t = get_translator()
        assert t.locale == "pl"
        set_locale("en")


class TestNormalizeLocale:
    """Test locale code normalization."""

    def test_simple(self) -> None:
        assert _normalize_locale("en") == "en"
        assert _normalize_locale("pl") == "pl"

    def test_with_country(self) -> None:
        assert _normalize_locale("pl_PL") == "pl"
        assert _normalize_locale("en_US") == "en"

    def test_with_encoding(self) -> None:
        assert _normalize_locale("pl_PL.UTF-8") == "pl"

    def test_uppercase(self) -> None:
        assert _normalize_locale("PL") == "pl"
        assert _normalize_locale("EN") == "en"


class TestPluralization:
    """Test plural form selection."""

    def test_english_singular(self) -> None:
        t = Translator("en")
        # English: 2 forms — one/other
        result = t.plural(1, "plural.day.one", "plural.day.other")
        assert "1" in result

    def test_english_plural(self) -> None:
        t = Translator("en")
        result = t.plural(5, "plural.day.one", "plural.day.other")
        assert "5" in result

    def test_polish_singular(self) -> None:
        t = Translator("pl")
        result = t.plural(1, "plural.day.one", "plural.day.few", "plural.day.many")
        assert "1" in result

    def test_polish_few(self) -> None:
        t = Translator("pl")
        # 2, 3, 4 → few form
        result = t.plural(3, "plural.day.one", "plural.day.few", "plural.day.many")
        assert "3" in result

    def test_polish_many(self) -> None:
        t = Translator("pl")
        # 5+ → many form
        result = t.plural(5, "plural.day.one", "plural.day.few", "plural.day.many")
        assert "5" in result

    def test_polish_teen_numbers_use_many(self) -> None:
        t = Translator("pl")
        # 12, 13, 14 → many (not few)
        result = t.plural(12, "plural.day.one", "plural.day.few", "plural.day.many")
        assert "12" in result

    def test_polish_22_uses_few(self) -> None:
        t = Translator("pl")
        result = t.plural(22, "plural.day.one", "plural.day.few", "plural.day.many")
        assert "22" in result


class TestDateFormatting:
    """Test locale-aware date formatting."""

    def test_english_short_date(self) -> None:
        t = Translator("en")
        d = date(2026, 3, 18)
        assert t.format_date_short(d) == "Mar 18"

    def test_polish_short_date(self) -> None:
        t = Translator("pl")
        d = date(2026, 3, 18)
        assert t.format_date_short(d) == "18 mar"

    def test_english_full_date(self) -> None:
        t = Translator("en")
        d = date(2026, 3, 18)
        assert t.format_date_full(d) == "Mar 18, 2026"

    def test_polish_full_date(self) -> None:
        t = Translator("pl")
        d = date(2026, 3, 18)
        assert t.format_date_full(d) == "18 mar 2026"

    def test_datetime_format(self) -> None:
        t = Translator("en")
        dt = datetime(2026, 3, 18, 14, 30)
        assert t.format_datetime(dt) == "2026-03-18 14:30"


class TestNumberFormatting:
    """Test locale-aware number formatting."""

    def test_english_integer(self) -> None:
        t = Translator("en")
        assert t.format_number(1234) == "1,234"

    def test_polish_integer(self) -> None:
        t = Translator("pl")
        result = t.format_number(1234)
        assert "1" in result and "234" in result
        assert "," not in result  # Polish doesn't use comma for thousands

    def test_english_decimal(self) -> None:
        t = Translator("en")
        assert t.format_number(1234.56, decimals=2) == "1,234.56"

    def test_polish_decimal(self) -> None:
        t = Translator("pl")
        result = t.format_number(1234.56, decimals=2)
        assert "1234,56" in result or "234,56" in result
        assert "," in result  # Polish uses comma as decimal separator

    def test_small_number(self) -> None:
        t = Translator("en")
        assert t.format_number(42) == "42"

    def test_zero(self) -> None:
        t = Translator("en")
        assert t.format_number(0) == "0"


class TestPolishRendering:
    """Verify Polish translations render correctly for key UI areas."""

    @pytest.fixture()
    def t(self) -> Translator:
        return Translator("pl")

    def test_tab_labels_are_polish(self, t: Translator) -> None:
        assert "Przegląd" in t("tab.overview")
        assert "Obciążenie" in t("tab.workload")
        assert "Sprinty" in t("tab.sprints")
        assert "Ryzyka" in t("tab.risks")
        assert "Konflikty" in t("tab.conflicts")
        assert "Zależności" in t("tab.dependencies")
        assert "Wszystkie zadania" in t("tab.issues")

    def test_section_titles_are_polish(self, t: Translator) -> None:
        assert t("section.executive_summary") == "Podsumowanie"
        assert "Obciążenie" in t("section.workload")
        assert "Kondycja" in t("section.sprint_health")
        assert "Sygnały ryzyka" in t("section.risks")

    def test_card_labels_are_polish(self, t: Translator) -> None:
        assert t("card.total_issues") == "Wszystkie zadania"
        assert t("card.blocked") == "Zablokowane"
        assert t("card.story_points") == "Punkty historii"

    def test_table_headers_are_polish(self, t: Translator) -> None:
        assert t("table.person") == "Osoba"
        assert t("table.team") == "Zespół"
        assert t("table.assignee") == "Przypisany"
        assert t("table.priority") == "Priorytet"

    def test_empty_states_are_polish(self, t: Translator) -> None:
        assert "Nie wykryto" in t("empty.no_risks")
        assert "Brak" in t("empty.no_sprints")

    def test_settings_are_polish(self, t: Translator) -> None:
        assert "Ustawienia" in t("settings.title")
        assert t("settings.btn_cancel") == "Anuluj"

    def test_error_messages_are_polish(self, t: Translator) -> None:
        result = t("error.auth_failed", code=401)
        assert "401" in result
        assert "Uwierzytelnianie" in result

    def test_risk_messages_are_polish(self, t: Translator) -> None:
        result = t("risk.overloaded", name="Jan")
        assert "Jan" in result
        assert "przeciążony" in result

    def test_enum_translations_are_polish(self, t: Translator) -> None:
        assert t("enum.issue_type.epic") == "Epik"
        assert t("enum.issue_type.bug") == "Błąd"
        assert t("enum.status_category.done") == "Gotowe"
        assert t("enum.priority.high") == "Wysoki"
        assert t("enum.risk_severity.critical") == "Krytyczny"
        assert t("enum.sprint_state.active") == "Aktywny"

    def test_conflict_messages_are_polish(self, t: Translator) -> None:
        result = t("conflict.resource_wip", name="Jan", count=6, limit=5)
        assert "Jan" in result
        assert "6" in result


class TestTranslationFileConsistency:
    """Verify both locale files have matching keys."""

    @pytest.fixture()
    def en_keys(self) -> set[str]:
        with (_LOCALE_DIR / "en.json").open() as f:
            data = json.load(f)
        data.pop("_meta", None)
        return set(data.keys())

    @pytest.fixture()
    def pl_keys(self) -> set[str]:
        with (_LOCALE_DIR / "pl.json").open() as f:
            data = json.load(f)
        data.pop("_meta", None)
        return set(data.keys())

    def test_polish_has_all_english_keys(self, en_keys: set[str], pl_keys: set[str]) -> None:
        missing = en_keys - pl_keys
        assert not missing, f"Polish translation missing keys: {missing}"

    def test_english_has_all_polish_keys(self, en_keys: set[str], pl_keys: set[str]) -> None:
        extra = pl_keys - en_keys
        assert not extra, f"Polish has extra keys not in English: {extra}"

    def test_no_empty_translations_in_english(self, en_keys: set[str]) -> None:
        with (_LOCALE_DIR / "en.json").open() as f:
            data = json.load(f)
        data.pop("_meta", None)
        empty = [k for k, v in data.items() if isinstance(v, str) and not v.strip()]
        assert not empty, f"Empty English translations: {empty}"

    def test_no_empty_translations_in_polish(self, pl_keys: set[str]) -> None:
        with (_LOCALE_DIR / "pl.json").open() as f:
            data = json.load(f)
        data.pop("_meta", None)
        empty = [k for k, v in data.items() if isinstance(v, str) and not v.strip()]
        assert not empty, f"Empty Polish translations: {empty}"

    def test_translation_files_are_valid_json(self) -> None:
        for locale_file in _LOCALE_DIR.glob("*.json"):
            with locale_file.open() as f:
                data = json.load(f)
            assert isinstance(data, dict), f"{locale_file.name} is not a JSON object"

    def test_meta_present(self) -> None:
        for code in ("en", "pl"):
            with (_LOCALE_DIR / f"{code}.json").open() as f:
                data = json.load(f)
            assert "_meta" in data
            assert data["_meta"]["locale"] == code


class TestKeyExistenceValidation:
    """Verify all translation keys used in source code exist in both locales."""

    @pytest.fixture()
    def en_data(self) -> dict[str, str]:
        with (_LOCALE_DIR / "en.json").open() as f:
            data = json.load(f)
        data.pop("_meta", None)
        return data

    @pytest.fixture()
    def pl_data(self) -> dict[str, str]:
        with (_LOCALE_DIR / "pl.json").open() as f:
            data = json.load(f)
        data.pop("_meta", None)
        return data

    def test_interpolation_placeholders_match(self, en_data: dict, pl_data: dict) -> None:
        """Verify that interpolation placeholders in en and pl match."""
        import re

        placeholder_re = re.compile(r"\{(\w+)\}")
        mismatches = []
        for key in en_data:
            if key not in pl_data:
                continue
            en_val = en_data[key]
            pl_val = pl_data[key]
            if not isinstance(en_val, str) or not isinstance(pl_val, str):
                continue
            en_placeholders = set(placeholder_re.findall(en_val))
            pl_placeholders = set(placeholder_re.findall(pl_val))
            if en_placeholders != pl_placeholders:
                mismatches.append(f"{key}: EN has {en_placeholders}, PL has {pl_placeholders}")
        assert not mismatches, "Placeholder mismatches:\n" + "\n".join(mismatches)

    def test_all_enum_keys_exist(self, en_data: dict) -> None:
        """Verify enum display translation keys exist for all enums."""
        from flowboard.shared.types import (
            IssueType,
            Priority,
            RiskCategory,
            RiskSeverity,
            SprintState,
            StatusCategory,
        )

        missing = []
        for enum_cls, prefix in [
            (IssueType, "enum.issue_type"),
            (StatusCategory, "enum.status_category"),
            (Priority, "enum.priority"),
            (RiskSeverity, "enum.risk_severity"),
            (RiskCategory, "enum.risk_category"),
            (SprintState, "enum.sprint_state"),
        ]:
            for member in enum_cls:
                key = f"{prefix}.{member.value}"
                if key not in en_data:
                    # Try with lowercase/normalized value
                    normalized = member.value.lower().replace(" ", "_").replace("-", "_")
                    key_alt = f"{prefix}.{normalized}"
                    if key_alt not in en_data:
                        missing.append(key)
        assert not missing, f"Missing enum translation keys: {missing}"

    def test_all_risk_keys_exist(self, en_data: dict) -> None:
        """Verify all risk.* keys used in risk.py exist."""
        risk_keys = [k for k in en_data if k.startswith("risk.")]
        assert len(risk_keys) >= 30, f"Expected ≥30 risk keys, found {len(risk_keys)}"

    def test_all_conflict_keys_exist(self, en_data: dict) -> None:
        """Verify all conflict.* keys used in overlap.py exist."""
        conflict_keys = [k for k in en_data if k.startswith("conflict.")]
        assert len(conflict_keys) >= 10, f"Expected ≥10 conflict keys, found {len(conflict_keys)}"


class TestI18nKeyParity:
    """Verify en.json and pl.json have identical key sets."""

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        self.en = json.loads((I18N_DIR / "en.json").read_text(encoding="utf-8"))
        self.pl = json.loads((I18N_DIR / "pl.json").read_text(encoding="utf-8"))

    def test_same_key_count(self) -> None:
        assert len(self.en) == len(self.pl), (
            f"en has {len(self.en)} keys, pl has {len(self.pl)} keys"
        )

    def test_no_missing_in_pl(self) -> None:
        missing = set(self.en.keys()) - set(self.pl.keys())
        assert not missing, f"Keys in en but not pl: {sorted(missing)}"

    def test_no_missing_in_en(self) -> None:
        missing = set(self.pl.keys()) - set(self.en.keys())
        assert not missing, f"Keys in pl but not en: {sorted(missing)}"

    def test_no_empty_values_in_en(self) -> None:
        empty = [k for k, v in self.en.items() if isinstance(v, str) and not v.strip()]
        assert not empty, f"Empty values in en.json: {empty}"

    def test_no_empty_values_in_pl(self) -> None:
        empty = [k for k, v in self.pl.items() if isinstance(v, str) and not v.strip()]
        assert not empty, f"Empty values in pl.json: {empty}"
