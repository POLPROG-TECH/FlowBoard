"""Tests for methodology-aware wizard demo features.

Covers:
- Demo config generation per methodology
- /api/demo endpoint with methodology parameter
- Methodology picker modal in wizard HTML
- i18n keys for methodology labels
"""

from __future__ import annotations

import json
from typing import ClassVar

import pytest

# ===================================================================
# Demo config builder
# ===================================================================


class TestBuildDemoConfigDict:
    """Verify _build_demo_config_dict produces correct configs per methodology."""

    def _build(self, methodology: str = "scrum") -> dict:
        from flowboard.web.server_helpers import build_demo_config_dict

        return build_demo_config_dict(methodology=methodology)

    def test_scrum_default(self):
        cfg = self._build("scrum")
        assert cfg["methodology"] == "scrum"
        assert "pi" in cfg
        assert cfg["pi"]["enabled"] is True
        assert "Scrum" in cfg["dashboard"]["branding"]["subtitle"]

    def test_kanban_config(self):
        cfg = self._build("kanban")
        assert cfg["methodology"] == "kanban"
        assert "pi" not in cfg
        assert "Kanban" in cfg["dashboard"]["branding"]["subtitle"]
        assert cfg["dashboard"]["branding"]["primary_color"] == "#3b82f6"

    def test_waterfall_config(self):
        cfg = self._build("waterfall")
        assert cfg["methodology"] == "waterfall"
        assert "pi" not in cfg
        assert "Waterfall" in cfg["dashboard"]["branding"]["subtitle"]
        assert cfg["dashboard"]["branding"]["primary_color"] == "#8b5cf6"

    def test_hybrid_config(self):
        cfg = self._build("hybrid")
        assert cfg["methodology"] == "hybrid"

    def test_default_is_scrum(self):
        cfg = self._build()
        assert cfg["methodology"] == "scrum"

    def test_common_fields_present(self):
        for m in ("scrum", "kanban", "waterfall", "hybrid"):
            cfg = self._build(m)
            assert "jira" in cfg
            assert "teams" in cfg
            assert len(cfg["teams"]) == 3
            assert "dashboard" in cfg
            assert "branding" in cfg["dashboard"]

    def test_output_path_customizable(self):
        from flowboard.web.server_helpers import build_demo_config_dict

        cfg = build_demo_config_dict(output_path="custom/path.html", methodology="kanban")
        assert cfg["output"]["path"] == "custom/path.html"
        assert cfg["methodology"] == "kanban"


# ===================================================================
# API endpoint /api/demo with methodology
# ===================================================================


class TestDemoAPIMethodology:
    """Verify /api/demo accepts methodology parameter."""

    @pytest.fixture()
    def client(self):
        from fastapi.testclient import TestClient

        from flowboard.web.server import create_app

        app = create_app(config_path=None, first_run=True)
        return TestClient(app, raise_server_exceptions=False)

    def test_demo_accepts_methodology_body(self, client):
        """POST /api/demo with {"methodology": "kanban"} should not 400."""
        from unittest.mock import patch

        with patch(
            "flowboard.web.server.locate_demo_fixture", side_effect=FileNotFoundError("no fixture")
        ):
            resp = client.post(
                "/api/demo",
                json={"methodology": "kanban"},
                headers={"X-Requested-With": "FlowBoard"},
            )
        # 500 because fixture not found, but not 422 (validation error)
        assert resp.status_code == 500

    def test_demo_invalid_methodology_falls_back(self, client):
        """Invalid methodology should fall back to scrum, not crash."""
        from unittest.mock import patch

        with patch(
            "flowboard.web.server.locate_demo_fixture", side_effect=FileNotFoundError("no fixture")
        ):
            resp = client.post(
                "/api/demo",
                json={"methodology": "invalid_method"},
                headers={"X-Requested-With": "FlowBoard"},
            )
        assert resp.status_code == 500  # fixture error, not validation error

    def test_demo_empty_body_defaults_to_scrum(self, client):
        """Empty POST body should default to scrum methodology."""
        from unittest.mock import patch

        with patch(
            "flowboard.web.server.locate_demo_fixture", side_effect=FileNotFoundError("no fixture")
        ):
            resp = client.post(
                "/api/demo",
                headers={"X-Requested-With": "FlowBoard"},
            )
        assert resp.status_code == 500  # fixture error, not crash


# ===================================================================
# Wizard HTML — Methodology picker
# ===================================================================


class TestWizardMethodologyPicker:
    """Verify methodology picker appears in wizard HTML."""

    @pytest.fixture()
    def wizard_html(self) -> str:
        from flowboard.presentation.html.renderer import render_first_run

        return render_first_run()

    def test_demo_picker_js_function_exists(self, wizard_html):
        assert "showDemoMethodologyPicker" in wizard_html

    def test_demo_picker_overlay_id(self, wizard_html):
        assert "demoPickerOverlay" in wizard_html

    def test_methodology_cards_defined(self, wizard_html):
        assert "DEMO_METHODOLOGIES" in wizard_html

    def test_scrum_methodology_in_js(self, wizard_html):
        assert "'scrum'" in wizard_html

    def test_kanban_methodology_in_js(self, wizard_html):
        assert "'kanban'" in wizard_html

    def test_waterfall_methodology_in_js(self, wizard_html):
        assert "'waterfall'" in wizard_html

    def test_hybrid_methodology_in_js(self, wizard_html):
        assert "'hybrid'" in wizard_html

    def test_demo_grid_css(self, wizard_html):
        assert "wz-demo-grid" in wizard_html

    def test_demo_method_card_css(self, wizard_html):
        assert "wz-demo-method-card" in wizard_html

    def test_focus_trap_for_picker(self, wizard_html):
        assert "trapDemoPickerFocus" in wizard_html

    def test_launch_demo_sends_methodology(self, wizard_html):
        assert "launchDemo(m.key)" in wizard_html

    def test_api_demo_call_includes_methodology(self, wizard_html):
        assert "methodology:" in wizard_html

    def test_close_demo_picker(self, wizard_html):
        assert "closeDemoPicker" in wizard_html

    def test_aria_modal_on_picker(self, wizard_html):
        assert "'aria-modal': 'true'" in wizard_html

    def test_demo_method_accent_bar_css(self, wizard_html):
        assert "wz-demo-method-accent" in wizard_html

    def test_responsive_grid_breakpoint(self, wizard_html):
        assert "grid-template-columns: 1fr" in wizard_html


# ===================================================================
# i18n — methodology demo keys
# ===================================================================


class TestMethodologyDemoI18n:
    """Verify i18n keys for methodology demo picker."""

    REQUIRED_KEYS: ClassVar[list[str]] = [
        "wizard.choose_methodology",
        "wizard.choose_methodology_desc",
        "wizard.demo_scrum",
        "wizard.demo_scrum_desc",
        "wizard.demo_kanban",
        "wizard.demo_kanban_desc",
        "wizard.demo_waterfall",
        "wizard.demo_waterfall_desc",
        "wizard.demo_hybrid",
        "wizard.demo_hybrid_desc",
        "wizard.generating_demo",
    ]

    @pytest.fixture()
    def en_data(self) -> dict:
        from pathlib import Path

        p = Path(__file__).resolve().parents[1] / "src" / "flowboard" / "i18n" / "en.json"
        return json.loads(p.read_text())

    @pytest.fixture()
    def pl_data(self) -> dict:
        from pathlib import Path

        p = Path(__file__).resolve().parents[1] / "src" / "flowboard" / "i18n" / "pl.json"
        return json.loads(p.read_text())

    @pytest.mark.parametrize("key", REQUIRED_KEYS)
    def test_en_has_key(self, en_data, key):
        assert key in en_data, f"Missing en.json key: {key}"
        assert len(en_data[key]) > 0

    @pytest.mark.parametrize("key", REQUIRED_KEYS)
    def test_pl_has_key(self, pl_data, key):
        assert key in pl_data, f"Missing pl.json key: {key}"
        assert len(pl_data[key]) > 0

    def test_generating_demo_has_placeholder(self, en_data):
        assert "{methodology}" in en_data["wizard.generating_demo"]

    def test_generating_demo_pl_has_placeholder(self, pl_data):
        assert "{methodology}" in pl_data["wizard.generating_demo"]

    def test_i18n_keys_in_wizard_html(self):
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()
        assert "choose_methodology" in html
        assert "demo_scrum" in html
        assert "demo_kanban" in html
        assert "demo_waterfall" in html
        assert "demo_hybrid" in html
        assert "generating_demo" in html


# ===================================================================
# Backward compatibility
# ===================================================================


class TestDemoBackwardCompat:
    """Ensure existing demo behavior is preserved."""

    def test_build_demo_config_no_args_is_scrum(self):
        from flowboard.web.server_helpers import build_demo_config_dict

        cfg = build_demo_config_dict()
        assert cfg["methodology"] == "scrum"
        assert "pi" in cfg

    def test_all_demo_configs_loadable(self):
        from flowboard.infrastructure.config.loader import load_config_from_dict
        from flowboard.web.server_helpers import build_demo_config_dict

        for m in ("scrum", "kanban", "waterfall", "hybrid"):
            cfg_dict = build_demo_config_dict(methodology=m)
            cfg = load_config_from_dict(cfg_dict)
            assert cfg.methodology == m


# ===================================================================
# Demo toolbar in rendered dashboard
# ===================================================================


class TestDemoToolbar:
    """Verify demo toolbar appears in dashboard when is_demo=True."""

    def _render(self, is_demo: bool = False, methodology: str = "scrum") -> str:
        from flowboard.domain.models import BoardSnapshot
        from flowboard.infrastructure.config.loader import load_config_from_dict
        from flowboard.presentation.html.renderer import render_dashboard
        from flowboard.web.server_helpers import build_demo_config_dict

        cfg = load_config_from_dict(build_demo_config_dict(methodology=methodology))
        snapshot = BoardSnapshot()
        return render_dashboard(snapshot, cfg, is_demo=is_demo)

    def test_toolbar_present_when_demo(self):
        html = self._render(is_demo=True)
        assert 'class="demo-toolbar"' in html

    def test_toolbar_absent_when_not_demo(self):
        html = self._render(is_demo=False)
        assert 'class="demo-toolbar"' not in html

    def test_toolbar_has_methodology_buttons(self):
        html = self._render(is_demo=True)
        assert "switchDemo('scrum')" in html
        assert "switchDemo('kanban')" in html
        assert "switchDemo('waterfall')" in html
        assert "switchDemo('hybrid')" in html

    def test_toolbar_active_scrum(self):
        html = self._render(is_demo=True, methodology="scrum")
        assert 'aria-pressed="true">🏃 Scrum</button>' in html
        assert "onclick=\"switchDemo('kanban')\" " in html
        assert 'aria-pressed="false">📊 Kanban</button>' in html

    def test_toolbar_active_kanban(self):
        html = self._render(is_demo=True, methodology="kanban")
        assert 'aria-pressed="true">📊 Kanban</button>' in html
        assert "onclick=\"switchDemo('scrum')\" " in html
        assert 'aria-pressed="false">🏃 Scrum</button>' in html

    def test_toolbar_has_back_button(self):
        html = self._render(is_demo=True)
        assert "backToWizard" in html

    def test_toolbar_has_demo_badge(self):
        html = self._render(is_demo=True)
        assert "demo-toolbar-badge" in html

    def test_toolbar_has_aria_label(self):
        html = self._render(is_demo=True)
        assert 'role="banner"' in html

    def test_toolbar_css_present(self):
        html = self._render(is_demo=True)
        assert ".demo-toolbar" in html
        assert "demo-toolbar-btn" in html


class TestDemoToolbarI18n:
    """Verify demo toolbar i18n keys exist."""

    TOOLBAR_KEYS: ClassVar[list[str]] = [
        "demo.toolbar_label",
        "demo.badge",
        "demo.current_methodology",
        "demo.back_to_setup",
    ]

    @pytest.fixture()
    def en_data(self) -> dict:
        from pathlib import Path

        p = Path(__file__).resolve().parents[1] / "src" / "flowboard" / "i18n" / "en.json"
        return json.loads(p.read_text())

    @pytest.fixture()
    def pl_data(self) -> dict:
        from pathlib import Path

        p = Path(__file__).resolve().parents[1] / "src" / "flowboard" / "i18n" / "pl.json"
        return json.loads(p.read_text())

    @pytest.mark.parametrize("key", TOOLBAR_KEYS)
    def test_en_has_key(self, en_data, key):
        assert key in en_data

    @pytest.mark.parametrize("key", TOOLBAR_KEYS)
    def test_pl_has_key(self, pl_data, key):
        assert key in pl_data


class TestResetEndpoint:
    """Verify /?reset=1 clears demo state."""

    @pytest.fixture()
    def client(self):
        from fastapi.testclient import TestClient

        from flowboard.web.server import create_app

        app = create_app(config_path=None, first_run=True)
        return TestClient(app, raise_server_exceptions=False)

    def test_reset_returns_wizard(self, client):
        resp = client.get("/?reset=1")
        assert resp.status_code == 200
        # Should show first-run wizard, not a dashboard
        assert (
            "wizard" in resp.text.lower() or "first-run" in resp.text.lower() or "wz-" in resp.text
        )
