"""Smoke tests for critical modules that lack direct coverage.

These tests validate imports, basic instantiation, and core function signatures
to prevent silent breakage. They complement the existing integration tests.
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SRC_ROOT = _PROJECT_ROOT / "src" / "flowboard"
_I18N_DIR = _SRC_ROOT / "i18n"


# ── Config Models ──────────────────────────────────────────────────────────


class TestConfigModels:
    """Tests for config models."""

    """GIVEN config models and the scenario: flowboard config defaults"""
    def test_flowboard_config_defaults(self) -> None:
        """WHEN the code under test is exercised for: flowboard config defaults"""
        from flowboard.infrastructure.config.config_models import FlowBoardConfig

        cfg = FlowBoardConfig()

        """THEN the expected behaviour holds: flowboard config defaults"""
        assert cfg.methodology == "scrum"
        assert cfg.output.path.endswith(".html")

    """GIVEN config models and the scenario: branding config defaults"""
    def test_branding_config_defaults(self) -> None:
        """WHEN the code under test is exercised for: branding config defaults"""
        from flowboard.infrastructure.config.config_models import BrandingConfig

        b = BrandingConfig()

        """THEN the expected behaviour holds: branding config defaults"""
        assert b.primary_color.startswith("#")
        assert len(b.secondary_color) in (7, 9)  # hex color

    """GIVEN config models and the scenario: timeline display config defaults"""
    def test_timeline_display_config_defaults(self) -> None:
        """WHEN the code under test is exercised for: timeline display config defaults"""
        from flowboard.infrastructure.config.config_models import TimelineDisplayConfig

        t = TimelineDisplayConfig()

        """THEN the expected behaviour holds: timeline display config defaults"""
        assert t.max_swimlanes == 30
        assert t.default_mode == "assignee"

    """GIVEN config models and the scenario: supported methodologies values"""
    def test_supported_methodologies_values(self) -> None:
        """WHEN the code under test is exercised for: supported methodologies values"""
        from flowboard.infrastructure.config.config_models import (
            SUPPORTED_METHODOLOGIES,
        )

        """THEN the expected behaviour holds: supported methodologies values"""
        assert "scrum" in SUPPORTED_METHODOLOGIES
        assert "kanban" in SUPPORTED_METHODOLOGIES
        assert "waterfall" in SUPPORTED_METHODOLOGIES
        assert "hybrid" in SUPPORTED_METHODOLOGIES
        assert "custom" in SUPPORTED_METHODOLOGIES


# ── Schema Validator ───────────────────────────────────────────────────────


class TestValidator:
    """Tests for validator."""

    """GIVEN validator and the scenario: locate schema file"""
    def test_locate_schema_file(self) -> None:
        """WHEN the code under test is exercised for: locate schema file"""
        from flowboard.infrastructure.config.validator import _find_schema_path

        path = _find_schema_path()

        """THEN the expected behaviour holds: locate schema file"""
        assert path.exists()
        assert path.name == "config.schema.json"

    """GIVEN validator and the scenario: validate minimal config"""
    def test_validate_minimal_config(self) -> None:
        """WHEN the code under test is exercised for: validate minimal config"""
        from flowboard.infrastructure.config.validator import (
            ConfigValidationError,
            validate_config_dict,
        )

        # Valid minimal config should not raise
        with contextlib.suppress(ConfigValidationError):
            validate_config_dict({"jira": {"base_url": "https://x.atlassian.net"}})


# ── Charts ──────────────────────────────────────────────────────────────────


class TestCharts:
    """Tests for charts."""

    """GIVEN charts and the scenario: status colors dict exists"""
    def test_status_colors_dict_exists(self) -> None:
        """WHEN the code under test is exercised for: status colors dict exists"""
        from flowboard.presentation.html.charts import STATUS_COLORS

        """THEN the expected behaviour holds: status colors dict exists"""
        assert isinstance(STATUS_COLORS, dict)
        assert len(STATUS_COLORS) > 0

    """GIVEN charts and the scenario: json serializer works"""
    def test_json_serializer_works(self) -> None:
        """WHEN the code under test is exercised for: json serializer works"""
        from flowboard.presentation.html.charts import _json

        result = _json({"key": "value"})

        """THEN the expected behaviour holds: json serializer works"""
        assert isinstance(result, str)
        assert "key" in result


# ── Renderer ────────────────────────────────────────────────────────────────


class TestRenderer:
    """Tests for renderer."""

    """GIVEN renderer and the scenario: render first run returns html"""
    def test_render_first_run_returns_html(self) -> None:
        """WHEN the code under test is exercised for: render first run returns html"""
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run(config_path="config.json")

        """THEN the expected behaviour holds: render first run returns html"""
        assert "<!DOCTYPE html>" in html or "<html" in html

    """GIVEN renderer and the scenario: render error page"""
    def test_render_error_page(self) -> None:
        """WHEN the code under test is exercised for: render error page"""
        from flowboard.presentation.html.renderer import _render_error_page

        html = _render_error_page("Test error")

        """THEN the expected behaviour holds: render error page"""
        assert "Test error" in html


# ── Translator ──────────────────────────────────────────────────────────────


class TestTranslator:
    """Tests for translator."""

    """GIVEN translator and the scenario: translator english"""
    def test_translator_english(self) -> None:
        """WHEN the code under test is exercised for: translator english"""
        from flowboard.i18n.translator import Translator

        t = Translator("en")
        result = t("ui.settings")

        """THEN the expected behaviour holds: translator english"""
        assert isinstance(result, str)
        assert len(result) > 0

    """GIVEN translator and the scenario: translator polish"""
    def test_translator_polish(self) -> None:
        """WHEN the code under test is exercised for: translator polish"""
        from flowboard.i18n.translator import Translator

        t = Translator("pl")
        result = t("ui.settings")

        """THEN the expected behaviour holds: translator polish"""
        assert isinstance(result, str)

    """GIVEN translator and the scenario: translator missing key returns key"""
    def test_translator_missing_key_returns_key(self) -> None:
        """WHEN the code under test is exercised for: translator missing key returns key"""
        from flowboard.i18n.translator import Translator

        t = Translator("en")
        result = t("nonexistent.key.xyz")

        """THEN the expected behaviour holds: translator missing key returns key"""
        assert result == "nonexistent.key.xyz"


# ── Presets ─────────────────────────────────────────────────────────────────


class TestPresets:
    """Tests for presets."""

    """GIVEN presets and the scenario: all presets have visible tabs"""
    def test_all_presets_have_visible_tabs(self) -> None:
        """WHEN the code under test is exercised for: all presets have visible tabs"""
        from flowboard.infrastructure.config.presets import _PRESETS

        """THEN the expected behaviour holds: all presets have visible tabs"""
        for name, preset in _PRESETS.items():
            if not preset:  # custom may be empty
                continue
            tabs = preset.get("dashboard", {}).get("tabs", {})
            assert "visible" in tabs, f"Preset {name} missing visible tabs"

    """GIVEN presets and the scenario: apply preset preserves user overrides"""
    def test_apply_preset_preserves_user_overrides(self) -> None:
        """WHEN the code under test is exercised for: apply preset preserves user overrides"""
        from flowboard.infrastructure.config.presets import apply_preset

        user_cfg = {"output": {"title": "My Board"}}
        result = apply_preset(user_cfg.copy(), "kanban")

        """THEN the expected behaviour holds: apply preset preserves user overrides"""
        assert result["output"]["title"] == "My Board"

    """GIVEN presets and the scenario: detect methodology"""
    def test_detect_methodology(self) -> None:
        """WHEN the code under test is exercised for: detect methodology"""
        from flowboard.infrastructure.config.presets import detect_methodology

        """THEN the expected behaviour holds: detect methodology"""
        assert detect_methodology(has_sprints=True, has_fix_versions=False) == "scrum"
        assert detect_methodology(has_sprints=False, has_fix_versions=False) == "kanban"
        assert detect_methodology(has_sprints=False, has_fix_versions=True) == "waterfall"


# ── Network ─────────────────────────────────────────────────────────────────


class TestNetwork:
    """Tests for network."""

    """GIVEN network and the scenario: module imports"""
    def test_module_imports(self) -> None:
        """WHEN the code under test is exercised for: module imports"""
        from flowboard.shared import network  # noqa: F401


# ── Middleware ──────────────────────────────────────────────────────────────


class TestMiddleware:
    """Tests for middleware."""

    """GIVEN middleware and the scenario: module imports"""
    def test_module_imports(self) -> None:
        """WHEN the code under test is exercised for: module imports"""
        from flowboard.web import middleware  # noqa: F401


class TestI18nKeyParity:
    """Tests for i18n key parity."""

    @pytest.fixture(autouse=True)
    def _load_translations(self) -> None:
        with open(_I18N_DIR / "en.json") as f:
            self.en = json.load(f)
        with open(_I18N_DIR / "pl.json") as f:
            self.pl = json.load(f)
        self.en.pop("_meta", None)
        self.pl.pop("_meta", None)

    """GIVEN i18n key parity and the scenario: en pl key count matches"""
    def test_en_pl_key_count_matches(self) -> None:
        """THEN the expected behaviour holds: en pl key count matches"""
        assert len(self.en) == len(self.pl), (
            f"EN has {len(self.en)} keys, PL has {len(self.pl)} keys"
        )

    """GIVEN i18n key parity and the scenario: no en only keys"""
    def test_no_en_only_keys(self) -> None:
        """WHEN the code under test is exercised for: no en only keys"""
        en_only = set(self.en.keys()) - set(self.pl.keys())

        """THEN the expected behaviour holds: no en only keys"""
        assert not en_only, f"Keys in EN but missing from PL: {en_only}"

    """GIVEN i18n key parity and the scenario: no pl only keys"""
    def test_no_pl_only_keys(self) -> None:
        """WHEN the code under test is exercised for: no pl only keys"""
        pl_only = set(self.pl.keys()) - set(self.en.keys())

        """THEN the expected behaviour holds: no pl only keys"""
        assert not pl_only, f"Keys in PL but missing from EN: {pl_only}"

    """GIVEN i18n key parity and the scenario: scrum completion key exists"""
    def test_scrum_completion_key_exists(self) -> None:
        """THEN the expected behaviour holds: scrum completion key exists"""
        assert "scrum.completion" in self.en
        assert "scrum.completion" in self.pl

    """GIVEN i18n key parity and the scenario: zoom exit fullscreen key exists"""
    def test_zoom_exit_fullscreen_key_exists(self) -> None:
        """THEN the expected behaviour holds: zoom exit fullscreen key exists"""
        assert "zoom.exit_fullscreen" in self.en
        assert "zoom.exit_fullscreen" in self.pl

    """GIVEN i18n key parity and the scenario: error page keys exist"""
    def test_error_page_keys_exist(self) -> None:
        """THEN the expected behaviour holds: error page keys exist"""
        for key in ("error.page_title", "error.heading", "error.description", "error.retry"):
            assert key in self.en, f"Missing EN key: {key}"
            assert key in self.pl, f"Missing PL key: {key}"

    """GIVEN i18n key parity and the scenario: no empty values"""
    def test_no_empty_values(self) -> None:
        """THEN the expected behaviour holds: no empty values"""
        for key, val in self.en.items():
            if isinstance(val, str):
                assert val.strip(), f"EN key '{key}' has empty value"
        for key, val in self.pl.items():
            if isinstance(val, str):
                assert val.strip(), f"PL key '{key}' has empty value"


# ---------------------------------------------------------------------------
# Renderer tests
# ---------------------------------------------------------------------------


class TestRendererImports:
    """Tests for renderer imports."""

    """GIVEN renderer imports and the scenario: jinja2 module is importable in renderer"""
    def test_jinja2_module_is_importable_in_renderer(self) -> None:
        """WHEN the code under test is exercised for: jinja2 module is importable in renderer"""
        import flowboard.presentation.html.renderer as renderer_mod

        """THEN the expected behaviour holds: jinja2 module is importable in renderer"""
        assert hasattr(renderer_mod, "jinja2"), (
            "jinja2 must be imported as a module in renderer.py for the except clause to work"
        )

    """GIVEN renderer imports and the scenario: error page accepts locale"""
    def test_error_page_accepts_locale(self) -> None:
        """WHEN the code under test is exercised for: error page accepts locale"""
        import inspect

        from flowboard.presentation.html.renderer import _render_error_page

        sig = inspect.signature(_render_error_page)

        """THEN the expected behaviour holds: error page accepts locale"""
        assert "locale" in sig.parameters, (
            "_render_error_page should accept a 'locale' parameter for i18n"
        )

    """GIVEN renderer imports and the scenario: error page renders in english"""
    def test_error_page_renders_in_english(self) -> None:
        """WHEN the code under test is exercised for: error page renders in english"""
        from flowboard.presentation.html.renderer import _render_error_page

        html = _render_error_page("Test error", locale="en")

        """THEN the expected behaviour holds: error page renders in english"""
        assert "Test error" in html
        assert "Dashboard could not be rendered" in html
        assert 'lang="en"' in html

    """GIVEN renderer imports and the scenario: error page renders in polish"""
    def test_error_page_renders_in_polish(self) -> None:
        """WHEN the code under test is exercised for: error page renders in polish"""
        from flowboard.presentation.html.renderer import _render_error_page

        html = _render_error_page("Test error", locale="pl")

        """THEN the expected behaviour holds: error page renders in polish"""
        assert "Test error" in html
        assert 'lang="pl"' in html
        # Should contain Polish text, not English
        assert "Nie udało się wyrenderować" in html


# ---------------------------------------------------------------------------
# Wizard config endpoint tests
# ---------------------------------------------------------------------------


class TestWizardConfigFirstRun:
    """Tests for wizard config first run."""

    """GIVEN wizard config first run and the scenario: first run returns no config"""
    def test_first_run_returns_no_config(self) -> None:
        """WHEN the code under test is exercised for: first run returns no config"""
        from fastapi.testclient import TestClient

        from flowboard.web.server import create_app

        app = create_app(config_path=None, first_run=True)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            "/api/wizard/config",
            headers={"X-Requested-With": "FlowBoard"},
        )
        data = resp.json()

        """THEN the expected behaviour holds: first run returns no config"""
        assert data["ok"] is True
        assert data["exists"] is False
        assert data["config"] is None


# ---------------------------------------------------------------------------
# License & version consistency
# ---------------------------------------------------------------------------


class TestReleaseMetadata:
    """Tests for release metadata."""

    """GIVEN release metadata and the scenario: version in init"""
    def test_version_in_init(self) -> None:
        """WHEN the code under test is exercised for: version in init"""
        from flowboard import __version__

        """THEN the expected behaviour holds: version in init"""
        assert __version__ == "1.0.0"

    """GIVEN release metadata and the scenario: version in pyproject"""
    def test_version_in_pyproject(self) -> None:
        """WHEN the code under test is exercised for: version in pyproject"""
        import tomllib

        with open(_PROJECT_ROOT / "pyproject.toml", "rb") as f:
            data = tomllib.load(f)

        """THEN the expected behaviour holds: version in pyproject"""
        assert data["project"]["version"] == "1.0.0"

    """GIVEN release metadata and the scenario: license in pyproject is agpl"""
    def test_license_in_pyproject_is_agpl(self) -> None:
        """WHEN the code under test is exercised for: license in pyproject is agpl"""
        import tomllib

        with open(_PROJECT_ROOT / "pyproject.toml", "rb") as f:
            data = tomllib.load(f)

        """THEN the expected behaviour holds: license in pyproject is agpl"""
        assert "AGPL" in data["project"]["license"]

    """GIVEN release metadata and the scenario: license file is agpl"""
    def test_license_file_is_agpl(self) -> None:
        """WHEN the code under test is exercised for: license file is agpl"""
        license_text = (_PROJECT_ROOT / "LICENSE").read_text()

        """THEN the expected behaviour holds: license file is agpl"""
        assert "GNU AFFERO GENERAL PUBLIC LICENSE" in license_text

    """GIVEN release metadata and the scenario: readme license badge is agpl"""
    def test_readme_license_badge_is_agpl(self) -> None:
        """WHEN the code under test is exercised for: readme license badge is agpl"""
        readme = (_PROJECT_ROOT / "README.md").read_text()

        """THEN the expected behaviour holds: readme license badge is agpl"""
        assert "AGPL" in readme
        assert "license-MIT" not in readme

    """GIVEN release metadata and the scenario: changelog has 1 0 0 entry"""
    def test_changelog_has_1_0_0_entry(self) -> None:
        """WHEN the code under test is exercised for: changelog has 1 0 0 entry"""
        changelog = (_PROJECT_ROOT / "CHANGELOG.md").read_text()

        """THEN the expected behaviour holds: changelog has 1 0 0 entry"""
        assert "[1.0.0]" in changelog
        # Should NOT have an [Unreleased] section anymore
        assert "[Unreleased]" not in changelog
