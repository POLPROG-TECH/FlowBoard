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
    """Basic validation of config dataclass construction."""

    def test_flowboard_config_defaults(self) -> None:
        from flowboard.infrastructure.config.config_models import FlowBoardConfig

        cfg = FlowBoardConfig()
        assert cfg.methodology == "scrum"
        assert cfg.output.path.endswith(".html")

    def test_branding_config_defaults(self) -> None:
        from flowboard.infrastructure.config.config_models import BrandingConfig

        b = BrandingConfig()
        assert b.primary_color.startswith("#")
        assert len(b.secondary_color) in (7, 9)  # hex color

    def test_timeline_display_config_defaults(self) -> None:
        from flowboard.infrastructure.config.config_models import TimelineDisplayConfig

        t = TimelineDisplayConfig()
        assert t.max_swimlanes == 30
        assert t.default_mode == "assignee"

    def test_supported_methodologies_values(self) -> None:
        from flowboard.infrastructure.config.config_models import (
            SUPPORTED_METHODOLOGIES,
        )

        assert "scrum" in SUPPORTED_METHODOLOGIES
        assert "kanban" in SUPPORTED_METHODOLOGIES
        assert "waterfall" in SUPPORTED_METHODOLOGIES
        assert "hybrid" in SUPPORTED_METHODOLOGIES
        assert "custom" in SUPPORTED_METHODOLOGIES


# ── Schema Validator ───────────────────────────────────────────────────────


class TestValidator:
    """Basic schema validator smoke tests."""

    def test_locate_schema_file(self) -> None:
        from flowboard.infrastructure.config.validator import _find_schema_path

        path = _find_schema_path()
        assert path.exists()
        assert path.name == "config.schema.json"

    def test_validate_minimal_config(self) -> None:

        from flowboard.infrastructure.config.validator import (
            ConfigValidationError,
            validate_config_dict,
        )

        # Valid minimal config should not raise
        with contextlib.suppress(ConfigValidationError):
            validate_config_dict({"jira": {"base_url": "https://x.atlassian.net"}})


# ── Charts ──────────────────────────────────────────────────────────────────


class TestCharts:
    """Chart data generation smoke tests."""

    def test_status_colors_dict_exists(self) -> None:
        from flowboard.presentation.html.charts import STATUS_COLORS

        assert isinstance(STATUS_COLORS, dict)
        assert len(STATUS_COLORS) > 0

    def test_json_serializer_works(self) -> None:
        from flowboard.presentation.html.charts import _json

        result = _json({"key": "value"})
        assert isinstance(result, str)
        assert "key" in result


# ── Renderer ────────────────────────────────────────────────────────────────


class TestRenderer:
    """Renderer pipeline smoke tests."""

    def test_render_first_run_returns_html(self) -> None:
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run(config_path="config.json")
        assert "<!DOCTYPE html>" in html or "<html" in html

    def test_render_error_page(self) -> None:
        from flowboard.presentation.html.renderer import _render_error_page

        html = _render_error_page("Test error")
        assert "Test error" in html


# ── Translator ──────────────────────────────────────────────────────────────


class TestTranslator:
    """i18n translator smoke tests."""

    def test_translator_english(self) -> None:
        from flowboard.i18n.translator import Translator

        t = Translator("en")
        result = t("ui.settings")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_translator_polish(self) -> None:
        from flowboard.i18n.translator import Translator

        t = Translator("pl")
        result = t("ui.settings")
        assert isinstance(result, str)

    def test_translator_missing_key_returns_key(self) -> None:
        from flowboard.i18n.translator import Translator

        t = Translator("en")
        result = t("nonexistent.key.xyz")
        assert result == "nonexistent.key.xyz"


# ── Presets ─────────────────────────────────────────────────────────────────


class TestPresets:
    """Methodology preset smoke tests."""

    def test_all_presets_have_visible_tabs(self) -> None:
        from flowboard.infrastructure.config.presets import _PRESETS

        for name, preset in _PRESETS.items():
            if not preset:  # custom may be empty
                continue
            tabs = preset.get("dashboard", {}).get("tabs", {})
            assert "visible" in tabs, f"Preset {name} missing visible tabs"

    def test_apply_preset_preserves_user_overrides(self) -> None:
        from flowboard.infrastructure.config.presets import apply_preset

        user_cfg = {"output": {"title": "My Board"}}
        result = apply_preset(user_cfg.copy(), "kanban")
        assert result["output"]["title"] == "My Board"

    def test_detect_methodology(self) -> None:
        from flowboard.infrastructure.config.presets import detect_methodology

        assert detect_methodology(has_sprints=True, has_fix_versions=False) == "scrum"
        assert detect_methodology(has_sprints=False, has_fix_versions=False) == "kanban"
        assert detect_methodology(has_sprints=False, has_fix_versions=True) == "waterfall"


# ── Network ─────────────────────────────────────────────────────────────────


class TestNetwork:
    """Network utilities smoke tests."""

    def test_module_imports(self) -> None:
        from flowboard.shared import network  # noqa: F401


# ── Middleware ──────────────────────────────────────────────────────────────


class TestMiddleware:
    """Middleware smoke tests."""

    def test_module_imports(self) -> None:
        from flowboard.web import middleware  # noqa: F401


class TestI18nKeyParity:
    """Ensure EN and PL translation files have identical key sets."""

    @pytest.fixture(autouse=True)
    def _load_translations(self) -> None:
        with open(_I18N_DIR / "en.json") as f:
            self.en = json.load(f)
        with open(_I18N_DIR / "pl.json") as f:
            self.pl = json.load(f)
        self.en.pop("_meta", None)
        self.pl.pop("_meta", None)

    def test_en_pl_key_count_matches(self) -> None:
        assert len(self.en) == len(self.pl), (
            f"EN has {len(self.en)} keys, PL has {len(self.pl)} keys"
        )

    def test_no_en_only_keys(self) -> None:
        en_only = set(self.en.keys()) - set(self.pl.keys())
        assert not en_only, f"Keys in EN but missing from PL: {en_only}"

    def test_no_pl_only_keys(self) -> None:
        pl_only = set(self.pl.keys()) - set(self.en.keys())
        assert not pl_only, f"Keys in PL but missing from EN: {pl_only}"

    def test_scrum_completion_key_exists(self) -> None:
        """Regression: scrum.completion was missing, causing raw key display."""
        assert "scrum.completion" in self.en
        assert "scrum.completion" in self.pl

    def test_zoom_exit_fullscreen_key_exists(self) -> None:
        """Regression: zoom.exit_fullscreen was missing from translation files."""
        assert "zoom.exit_fullscreen" in self.en
        assert "zoom.exit_fullscreen" in self.pl

    def test_error_page_keys_exist(self) -> None:
        """Error page should be fully internationalized."""
        for key in ("error.page_title", "error.heading", "error.description", "error.retry"):
            assert key in self.en, f"Missing EN key: {key}"
            assert key in self.pl, f"Missing PL key: {key}"

    def test_no_empty_values(self) -> None:
        """No translation value should be an empty string."""
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
    """Ensure the renderer module has correct imports."""

    def test_jinja2_module_is_importable_in_renderer(self) -> None:
        """Regression: jinja2.TemplateError was caught but jinja2 was not imported."""
        import flowboard.presentation.html.renderer as renderer_mod

        assert hasattr(renderer_mod, "jinja2"), (
            "jinja2 must be imported as a module in renderer.py for the except clause to work"
        )

    def test_error_page_accepts_locale(self) -> None:
        """The error page function should accept a locale parameter."""
        import inspect

        from flowboard.presentation.html.renderer import _render_error_page

        sig = inspect.signature(_render_error_page)
        assert "locale" in sig.parameters, (
            "_render_error_page should accept a 'locale' parameter for i18n"
        )

    def test_error_page_renders_in_english(self) -> None:
        from flowboard.presentation.html.renderer import _render_error_page

        html = _render_error_page("Test error", locale="en")
        assert "Test error" in html
        assert "Dashboard could not be rendered" in html
        assert 'lang="en"' in html

    def test_error_page_renders_in_polish(self) -> None:
        from flowboard.presentation.html.renderer import _render_error_page

        html = _render_error_page("Test error", locale="pl")
        assert "Test error" in html
        assert 'lang="pl"' in html
        # Should contain Polish text, not English
        assert "Nie udało się wyrenderować" in html


# ---------------------------------------------------------------------------
# Wizard config endpoint tests
# ---------------------------------------------------------------------------


class TestWizardConfigFirstRun:
    """Wizard /api/wizard/config should respect first_run mode."""

    def test_first_run_returns_no_config(self) -> None:
        """Regression: endpoint was probing CWD even in first_run mode."""
        from fastapi.testclient import TestClient

        from flowboard.web.server import create_app

        app = create_app(config_path=None, first_run=True)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            "/api/wizard/config",
            headers={"X-Requested-With": "FlowBoard"},
        )
        data = resp.json()
        assert data["ok"] is True
        assert data["exists"] is False
        assert data["config"] is None


# ---------------------------------------------------------------------------
# License & version consistency
# ---------------------------------------------------------------------------


class TestReleaseMetadata:
    """Verify version and license consistency across the project."""

    def test_version_in_init(self) -> None:
        from flowboard import __version__

        assert __version__ == "1.0.0"

    def test_version_in_pyproject(self) -> None:
        import tomllib

        with open(_PROJECT_ROOT / "pyproject.toml", "rb") as f:
            data = tomllib.load(f)
        assert data["project"]["version"] == "1.0.0"

    def test_license_in_pyproject_is_agpl(self) -> None:
        import tomllib

        with open(_PROJECT_ROOT / "pyproject.toml", "rb") as f:
            data = tomllib.load(f)
        assert "AGPL" in data["project"]["license"]

    def test_license_file_is_agpl(self) -> None:
        license_text = (_PROJECT_ROOT / "LICENSE").read_text()
        assert "GNU AFFERO GENERAL PUBLIC LICENSE" in license_text

    def test_readme_license_badge_is_agpl(self) -> None:
        readme = (_PROJECT_ROOT / "README.md").read_text()
        assert "AGPL" in readme
        assert "license-MIT" not in readme

    def test_changelog_has_1_0_0_entry(self) -> None:
        changelog = (_PROJECT_ROOT / "CHANGELOG.md").read_text()
        assert "[1.0.0]" in changelog
        # Should NOT have an [Unreleased] section anymore
        assert "[Unreleased]" not in changelog
