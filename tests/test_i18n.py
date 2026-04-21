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
    """Tests for translator basics."""

    """GIVEN translator basics and the scenario: supported locales"""
    def test_supported_locales(self) -> None:
        """THEN the expected behaviour holds: supported locales"""
        assert "en" in supported_locales()
        assert "pl" in supported_locales()

    """GIVEN translator basics and the scenario: english translator returns values"""
    def test_english_translator_returns_values(self) -> None:
        """WHEN the code under test is exercised for: english translator returns values"""
        t = Translator("en")

        """THEN the expected behaviour holds: english translator returns values"""
        assert t("app.name") == "FlowBoard"
        assert t("tab.overview") == "📋 Overview"

    """GIVEN translator basics and the scenario: polish translator returns polish"""
    def test_polish_translator_returns_polish(self) -> None:
        """WHEN the code under test is exercised for: polish translator returns polish"""
        t = Translator("pl")

        """THEN the expected behaviour holds: polish translator returns polish"""
        assert "Przegląd" in t("tab.overview")
        assert t("card.blocked") == "Zablokowane"

    """GIVEN translator basics and the scenario: interpolation"""
    def test_interpolation(self) -> None:
        """WHEN the code under test is exercised for: interpolation"""
        t = Translator("en")
        result = t("cli.error", error="something broke")

        """THEN the expected behaviour holds: interpolation"""
        assert result == "Error: something broke"

    """GIVEN translator basics and the scenario: polish interpolation"""
    def test_polish_interpolation(self) -> None:
        """WHEN the code under test is exercised for: polish interpolation"""
        t = Translator("pl")
        result = t("cli.error", error="coś się zepsuło")

        """THEN the expected behaviour holds: polish interpolation"""
        assert result == "Błąd: coś się zepsuło"

    """GIVEN translator basics and the scenario: missing key returns key"""
    def test_missing_key_returns_key(self) -> None:
        """WHEN the code under test is exercised for: missing key returns key"""
        t = Translator("en")

        """THEN the expected behaviour holds: missing key returns key"""
        assert t("nonexistent.key") == "nonexistent.key"

    """GIVEN translator basics and the scenario: fallback to english"""
    def test_fallback_to_english(self) -> None:
        """WHEN the code under test is exercised for: fallback to english"""
        t = Translator("pl")

        """THEN the expected behaviour holds: fallback to english"""
        assert t("app.name") == "FlowBoard"  # same in both

    """GIVEN translator basics and the scenario: unsupported locale falls back"""
    def test_unsupported_locale_falls_back(self) -> None:
        """WHEN the code under test is exercised for: unsupported locale falls back"""
        t = Translator("xx")

        """THEN the expected behaviour holds: unsupported locale falls back"""
        assert t.locale == "en"
        assert t("app.name") == "FlowBoard"

    """GIVEN translator basics and the scenario: has key"""
    def test_has_key(self) -> None:
        """WHEN the code under test is exercised for: has key"""
        t = Translator("en")

        """THEN the expected behaviour holds: has key"""
        assert t.has("app.name")
        assert not t.has("nonexistent.key.xyz")


class TestLocaleState:
    """Tests for locale state."""

    """GIVEN locale state and the scenario: default locale"""
    def test_default_locale(self) -> None:
        """WHEN the code under test is exercised for: default locale"""
        set_locale("en")

        """THEN the expected behaviour holds: default locale"""
        assert get_locale() == "en"

    """GIVEN locale state and the scenario: set locale"""
    def test_set_locale(self) -> None:
        """WHEN the code under test is exercised for: set locale"""
        set_locale("pl")

        """THEN the expected behaviour holds: set locale"""
        assert get_locale() == "pl"
        set_locale("en")  # reset

    """GIVEN locale state and the scenario: set unsupported locale falls back"""
    def test_set_unsupported_locale_falls_back(self) -> None:
        """WHEN the code under test is exercised for: set unsupported locale falls back"""
        set_locale("xx")

        """THEN the expected behaviour holds: set unsupported locale falls back"""
        assert get_locale() == "en"

    """GIVEN locale state and the scenario: get translator uses current locale"""
    def test_get_translator_uses_current_locale(self) -> None:
        """WHEN the code under test is exercised for: get translator uses current locale"""
        set_locale("pl")
        t = get_translator()

        """THEN the expected behaviour holds: get translator uses current locale"""
        assert t.locale == "pl"
        set_locale("en")


class TestNormalizeLocale:
    """Tests for normalize locale."""

    """GIVEN normalize locale and the scenario: simple"""
    def test_simple(self) -> None:
        """THEN the expected behaviour holds: simple"""
        assert _normalize_locale("en") == "en"
        assert _normalize_locale("pl") == "pl"

    """GIVEN normalize locale and the scenario: with country"""
    def test_with_country(self) -> None:
        """THEN the expected behaviour holds: with country"""
        assert _normalize_locale("pl_PL") == "pl"
        assert _normalize_locale("en_US") == "en"

    """GIVEN normalize locale and the scenario: with encoding"""
    def test_with_encoding(self) -> None:
        """THEN the expected behaviour holds: with encoding"""
        assert _normalize_locale("pl_PL.UTF-8") == "pl"

    """GIVEN normalize locale and the scenario: uppercase"""
    def test_uppercase(self) -> None:
        """THEN the expected behaviour holds: uppercase"""
        assert _normalize_locale("PL") == "pl"
        assert _normalize_locale("EN") == "en"


class TestPluralization:
    """Tests for pluralization."""

    """GIVEN pluralization and the scenario: english singular"""
    def test_english_singular(self) -> None:
        """WHEN the code under test is exercised for: english singular"""
        t = Translator("en")
        # English: 2 forms - one/other
        result = t.plural(1, "plural.day.one", "plural.day.other")

        """THEN the expected behaviour holds: english singular"""
        assert "1" in result

    """GIVEN pluralization and the scenario: english plural"""
    def test_english_plural(self) -> None:
        """WHEN the code under test is exercised for: english plural"""
        t = Translator("en")
        result = t.plural(5, "plural.day.one", "plural.day.other")

        """THEN the expected behaviour holds: english plural"""
        assert "5" in result

    """GIVEN pluralization and the scenario: polish singular"""
    def test_polish_singular(self) -> None:
        """WHEN the code under test is exercised for: polish singular"""
        t = Translator("pl")
        result = t.plural(1, "plural.day.one", "plural.day.few", "plural.day.many")

        """THEN the expected behaviour holds: polish singular"""
        assert "1" in result

    """GIVEN pluralization and the scenario: polish few"""
    def test_polish_few(self) -> None:
        """WHEN the code under test is exercised for: polish few"""
        t = Translator("pl")
        # 2, 3, 4 → few form
        result = t.plural(3, "plural.day.one", "plural.day.few", "plural.day.many")

        """THEN the expected behaviour holds: polish few"""
        assert "3" in result

    """GIVEN pluralization and the scenario: polish many"""
    def test_polish_many(self) -> None:
        """WHEN the code under test is exercised for: polish many"""
        t = Translator("pl")
        # 5+ → many form
        result = t.plural(5, "plural.day.one", "plural.day.few", "plural.day.many")

        """THEN the expected behaviour holds: polish many"""
        assert "5" in result

    """GIVEN pluralization and the scenario: polish teen numbers use many"""
    def test_polish_teen_numbers_use_many(self) -> None:
        """WHEN the code under test is exercised for: polish teen numbers use many"""
        t = Translator("pl")
        # 12, 13, 14 → many (not few)
        result = t.plural(12, "plural.day.one", "plural.day.few", "plural.day.many")

        """THEN the expected behaviour holds: polish teen numbers use many"""
        assert "12" in result

    """GIVEN pluralization and the scenario: polish 22 uses few"""
    def test_polish_22_uses_few(self) -> None:
        """WHEN the code under test is exercised for: polish 22 uses few"""
        t = Translator("pl")
        result = t.plural(22, "plural.day.one", "plural.day.few", "plural.day.many")

        """THEN the expected behaviour holds: polish 22 uses few"""
        assert "22" in result


class TestDateFormatting:
    """Tests for date formatting."""

    """GIVEN date formatting and the scenario: english short date"""
    def test_english_short_date(self) -> None:
        """WHEN the code under test is exercised for: english short date"""
        t = Translator("en")
        d = date(2026, 3, 18)

        """THEN the expected behaviour holds: english short date"""
        assert t.format_date_short(d) == "Mar 18"

    """GIVEN date formatting and the scenario: polish short date"""
    def test_polish_short_date(self) -> None:
        """WHEN the code under test is exercised for: polish short date"""
        t = Translator("pl")
        d = date(2026, 3, 18)

        """THEN the expected behaviour holds: polish short date"""
        assert t.format_date_short(d) == "18 mar"

    """GIVEN date formatting and the scenario: english full date"""
    def test_english_full_date(self) -> None:
        """WHEN the code under test is exercised for: english full date"""
        t = Translator("en")
        d = date(2026, 3, 18)

        """THEN the expected behaviour holds: english full date"""
        assert t.format_date_full(d) == "Mar 18, 2026"

    """GIVEN date formatting and the scenario: polish full date"""
    def test_polish_full_date(self) -> None:
        """WHEN the code under test is exercised for: polish full date"""
        t = Translator("pl")
        d = date(2026, 3, 18)

        """THEN the expected behaviour holds: polish full date"""
        assert t.format_date_full(d) == "18 mar 2026"

    """GIVEN date formatting and the scenario: datetime format"""
    def test_datetime_format(self) -> None:
        """WHEN the code under test is exercised for: datetime format"""
        t = Translator("en")
        dt = datetime(2026, 3, 18, 14, 30)

        """THEN the expected behaviour holds: datetime format"""
        assert t.format_datetime(dt) == "2026-03-18 14:30"


class TestNumberFormatting:
    """Tests for number formatting."""

    """GIVEN number formatting and the scenario: english integer"""
    def test_english_integer(self) -> None:
        """WHEN the code under test is exercised for: english integer"""
        t = Translator("en")

        """THEN the expected behaviour holds: english integer"""
        assert t.format_number(1234) == "1,234"

    """GIVEN number formatting and the scenario: polish integer"""
    def test_polish_integer(self) -> None:
        """WHEN the code under test is exercised for: polish integer"""
        t = Translator("pl")
        result = t.format_number(1234)

        """THEN the expected behaviour holds: polish integer"""
        assert "1" in result and "234" in result
        assert "," not in result  # Polish doesn't use comma for thousands

    """GIVEN number formatting and the scenario: english decimal"""
    def test_english_decimal(self) -> None:
        """WHEN the code under test is exercised for: english decimal"""
        t = Translator("en")

        """THEN the expected behaviour holds: english decimal"""
        assert t.format_number(1234.56, decimals=2) == "1,234.56"

    """GIVEN number formatting and the scenario: polish decimal"""
    def test_polish_decimal(self) -> None:
        """WHEN the code under test is exercised for: polish decimal"""
        t = Translator("pl")
        result = t.format_number(1234.56, decimals=2)

        """THEN the expected behaviour holds: polish decimal"""
        assert "1234,56" in result or "234,56" in result
        assert "," in result  # Polish uses comma as decimal separator

    """GIVEN number formatting and the scenario: small number"""
    def test_small_number(self) -> None:
        """WHEN the code under test is exercised for: small number"""
        t = Translator("en")

        """THEN the expected behaviour holds: small number"""
        assert t.format_number(42) == "42"

    """GIVEN number formatting and the scenario: zero"""
    def test_zero(self) -> None:
        """WHEN the code under test is exercised for: zero"""
        t = Translator("en")

        """THEN the expected behaviour holds: zero"""
        assert t.format_number(0) == "0"


class TestPolishRendering:
    """Tests for polish rendering."""

    @pytest.fixture()
    def t(self) -> Translator:
        return Translator("pl")

    """GIVEN polish rendering and the scenario: tab labels are polish"""
    def test_tab_labels_are_polish(self, t: Translator) -> None:
        """THEN the expected behaviour holds: tab labels are polish"""
        assert "Przegląd" in t("tab.overview")
        assert "Obciążenie" in t("tab.workload")
        assert "Sprinty" in t("tab.sprints")
        assert "Ryzyka" in t("tab.risks")
        assert "Konflikty" in t("tab.conflicts")
        assert "Zależności" in t("tab.dependencies")
        assert "Wszystkie zadania" in t("tab.issues")

    """GIVEN polish rendering and the scenario: section titles are polish"""
    def test_section_titles_are_polish(self, t: Translator) -> None:
        """THEN the expected behaviour holds: section titles are polish"""
        assert t("section.executive_summary") == "Podsumowanie"
        assert "Obciążenie" in t("section.workload")
        assert "Kondycja" in t("section.sprint_health")
        assert "Sygnały ryzyka" in t("section.risks")

    """GIVEN polish rendering and the scenario: card labels are polish"""
    def test_card_labels_are_polish(self, t: Translator) -> None:
        """THEN the expected behaviour holds: card labels are polish"""
        assert t("card.total_issues") == "Wszystkie zadania"
        assert t("card.blocked") == "Zablokowane"
        assert t("card.story_points") == "Punkty historii"

    """GIVEN polish rendering and the scenario: table headers are polish"""
    def test_table_headers_are_polish(self, t: Translator) -> None:
        """THEN the expected behaviour holds: table headers are polish"""
        assert t("table.person") == "Osoba"
        assert t("table.team") == "Zespół"
        assert t("table.assignee") == "Przypisany"
        assert t("table.priority") == "Priorytet"

    """GIVEN polish rendering and the scenario: empty states are polish"""
    def test_empty_states_are_polish(self, t: Translator) -> None:
        """THEN the expected behaviour holds: empty states are polish"""
        assert "Nie wykryto" in t("empty.no_risks")
        assert "Brak" in t("empty.no_sprints")

    """GIVEN polish rendering and the scenario: settings are polish"""
    def test_settings_are_polish(self, t: Translator) -> None:
        """THEN the expected behaviour holds: settings are polish"""
        assert "Ustawienia" in t("settings.title")
        assert t("settings.btn_cancel") == "Anuluj"

    """GIVEN polish rendering and the scenario: error messages are polish"""
    def test_error_messages_are_polish(self, t: Translator) -> None:
        """WHEN the code under test is exercised for: error messages are polish"""
        result = t("error.auth_failed", code=401)

        """THEN the expected behaviour holds: error messages are polish"""
        assert "401" in result
        assert "Uwierzytelnianie" in result

    """GIVEN polish rendering and the scenario: risk messages are polish"""
    def test_risk_messages_are_polish(self, t: Translator) -> None:
        """WHEN the code under test is exercised for: risk messages are polish"""
        result = t("risk.overloaded", name="Jan")

        """THEN the expected behaviour holds: risk messages are polish"""
        assert "Jan" in result
        assert "przeciążony" in result

    """GIVEN polish rendering and the scenario: enum translations are polish"""
    def test_enum_translations_are_polish(self, t: Translator) -> None:
        """THEN the expected behaviour holds: enum translations are polish"""
        assert t("enum.issue_type.epic") == "Epik"
        assert t("enum.issue_type.bug") == "Błąd"
        assert t("enum.status_category.done") == "Gotowe"
        assert t("enum.priority.high") == "Wysoki"
        assert t("enum.risk_severity.critical") == "Krytyczny"
        assert t("enum.sprint_state.active") == "Aktywny"

    """GIVEN polish rendering and the scenario: conflict messages are polish"""
    def test_conflict_messages_are_polish(self, t: Translator) -> None:
        """WHEN the code under test is exercised for: conflict messages are polish"""
        result = t("conflict.resource_wip", name="Jan", count=6, limit=5)

        """THEN the expected behaviour holds: conflict messages are polish"""
        assert "Jan" in result
        assert "6" in result


class TestTranslationFileConsistency:
    """Tests for translation file consistency."""

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

    """GIVEN translation file consistency and the scenario: polish has all english keys"""
    def test_polish_has_all_english_keys(self, en_keys: set[str], pl_keys: set[str]) -> None:
        """WHEN the code under test is exercised for: polish has all english keys"""
        missing = en_keys - pl_keys

        """THEN the expected behaviour holds: polish has all english keys"""
        assert not missing, f"Polish translation missing keys: {missing}"

    """GIVEN translation file consistency and the scenario: english has all polish keys"""
    def test_english_has_all_polish_keys(self, en_keys: set[str], pl_keys: set[str]) -> None:
        """WHEN the code under test is exercised for: english has all polish keys"""
        extra = pl_keys - en_keys

        """THEN the expected behaviour holds: english has all polish keys"""
        assert not extra, f"Polish has extra keys not in English: {extra}"

    """GIVEN translation file consistency and the scenario: no empty translations in english"""
    def test_no_empty_translations_in_english(self, en_keys: set[str]) -> None:
        """WHEN the code under test is exercised for: no empty translations in english"""
        with (_LOCALE_DIR / "en.json").open() as f:
            data = json.load(f)
        data.pop("_meta", None)
        empty = [k for k, v in data.items() if isinstance(v, str) and not v.strip()]

        """THEN the expected behaviour holds: no empty translations in english"""
        assert not empty, f"Empty English translations: {empty}"

    """GIVEN translation file consistency and the scenario: no empty translations in polish"""
    def test_no_empty_translations_in_polish(self, pl_keys: set[str]) -> None:
        """WHEN the code under test is exercised for: no empty translations in polish"""
        with (_LOCALE_DIR / "pl.json").open() as f:
            data = json.load(f)
        data.pop("_meta", None)
        empty = [k for k, v in data.items() if isinstance(v, str) and not v.strip()]

        """THEN the expected behaviour holds: no empty translations in polish"""
        assert not empty, f"Empty Polish translations: {empty}"

    """GIVEN translation file consistency and the scenario: translation files are valid json"""
    def test_translation_files_are_valid_json(self) -> None:
        """THEN the expected behaviour holds: translation files are valid json"""
        for locale_file in _LOCALE_DIR.glob("*.json"):
            with locale_file.open() as f:
                data = json.load(f)
            assert isinstance(data, dict), f"{locale_file.name} is not a JSON object"

    """GIVEN translation file consistency and the scenario: meta present"""
    def test_meta_present(self) -> None:
        """THEN the expected behaviour holds: meta present"""
        for code in ("en", "pl"):
            with (_LOCALE_DIR / f"{code}.json").open() as f:
                data = json.load(f)
            assert "_meta" in data
            assert data["_meta"]["locale"] == code


class TestKeyExistenceValidation:
    """Tests for key existence validation."""

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

    """GIVEN key existence validation and the scenario: interpolation placeholders match"""
    def test_interpolation_placeholders_match(self, en_data: dict, pl_data: dict) -> None:
        """WHEN the code under test is exercised for: interpolation placeholders match"""
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

        """THEN the expected behaviour holds: interpolation placeholders match"""
        assert not mismatches, "Placeholder mismatches:\n" + "\n".join(mismatches)

    """GIVEN key existence validation and the scenario: all enum keys exist"""
    def test_all_enum_keys_exist(self, en_data: dict) -> None:
        """WHEN the code under test is exercised for: all enum keys exist"""
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

        """THEN the expected behaviour holds: all enum keys exist"""
        assert not missing, f"Missing enum translation keys: {missing}"

    """GIVEN key existence validation and the scenario: all risk keys exist"""
    def test_all_risk_keys_exist(self, en_data: dict) -> None:
        """WHEN the code under test is exercised for: all risk keys exist"""
        risk_keys = [k for k in en_data if k.startswith("risk.")]

        """THEN the expected behaviour holds: all risk keys exist"""
        assert len(risk_keys) >= 30, f"Expected ≥30 risk keys, found {len(risk_keys)}"

    """GIVEN key existence validation and the scenario: all conflict keys exist"""
    def test_all_conflict_keys_exist(self, en_data: dict) -> None:
        """WHEN the code under test is exercised for: all conflict keys exist"""
        conflict_keys = [k for k in en_data if k.startswith("conflict.")]

        """THEN the expected behaviour holds: all conflict keys exist"""
        assert len(conflict_keys) >= 10, f"Expected ≥10 conflict keys, found {len(conflict_keys)}"


class TestI18nKeyParity:
    """Tests for i18n key parity."""

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        self.en = json.loads((I18N_DIR / "en.json").read_text(encoding="utf-8"))
        self.pl = json.loads((I18N_DIR / "pl.json").read_text(encoding="utf-8"))

    """GIVEN i18n key parity and the scenario: same key count"""
    def test_same_key_count(self) -> None:
        """THEN the expected behaviour holds: same key count"""
        assert len(self.en) == len(self.pl), (
            f"en has {len(self.en)} keys, pl has {len(self.pl)} keys"
        )

    """GIVEN i18n key parity and the scenario: no missing in pl"""
    def test_no_missing_in_pl(self) -> None:
        """WHEN the code under test is exercised for: no missing in pl"""
        missing = set(self.en.keys()) - set(self.pl.keys())

        """THEN the expected behaviour holds: no missing in pl"""
        assert not missing, f"Keys in en but not pl: {sorted(missing)}"

    """GIVEN i18n key parity and the scenario: no missing in en"""
    def test_no_missing_in_en(self) -> None:
        """WHEN the code under test is exercised for: no missing in en"""
        missing = set(self.pl.keys()) - set(self.en.keys())

        """THEN the expected behaviour holds: no missing in en"""
        assert not missing, f"Keys in pl but not en: {sorted(missing)}"

    """GIVEN i18n key parity and the scenario: no empty values in en"""
    def test_no_empty_values_in_en(self) -> None:
        """WHEN the code under test is exercised for: no empty values in en"""
        empty = [k for k, v in self.en.items() if isinstance(v, str) and not v.strip()]

        """THEN the expected behaviour holds: no empty values in en"""
        assert not empty, f"Empty values in en.json: {empty}"

    """GIVEN i18n key parity and the scenario: no empty values in pl"""
    def test_no_empty_values_in_pl(self) -> None:
        """WHEN the code under test is exercised for: no empty values in pl"""
        empty = [k for k, v in self.pl.items() if isinstance(v, str) and not v.strip()]

        """THEN the expected behaviour holds: no empty values in pl"""
        assert not empty, f"Empty values in pl.json: {empty}"
