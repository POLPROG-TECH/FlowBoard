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
    """Tests for build demo config dict."""

    def _build(self, methodology: str = "scrum") -> dict:
        from flowboard.web.server_helpers import build_demo_config_dict

        return build_demo_config_dict(methodology=methodology)

    """GIVEN build demo config dict and the scenario: scrum default"""
    def test_scrum_default(self):
        """WHEN the code under test is exercised for: scrum default"""
        cfg = self._build("scrum")

        """THEN the expected behaviour holds: scrum default"""
        assert cfg["methodology"] == "scrum"
        assert "pi" in cfg
        assert cfg["pi"]["enabled"] is True
        assert "Scrum" in cfg["dashboard"]["branding"]["subtitle"]

    """GIVEN build demo config dict and the scenario: kanban config"""
    def test_kanban_config(self):
        """WHEN the code under test is exercised for: kanban config"""
        cfg = self._build("kanban")

        """THEN the expected behaviour holds: kanban config"""
        assert cfg["methodology"] == "kanban"
        assert "pi" not in cfg
        assert "Kanban" in cfg["dashboard"]["branding"]["subtitle"]
        assert cfg["dashboard"]["branding"]["primary_color"] == "#3b82f6"

    """GIVEN build demo config dict and the scenario: waterfall config"""
    def test_waterfall_config(self):
        """WHEN the code under test is exercised for: waterfall config"""
        cfg = self._build("waterfall")

        """THEN the expected behaviour holds: waterfall config"""
        assert cfg["methodology"] == "waterfall"
        assert "pi" not in cfg
        assert "Waterfall" in cfg["dashboard"]["branding"]["subtitle"]
        assert cfg["dashboard"]["branding"]["primary_color"] == "#8b5cf6"

    """GIVEN build demo config dict and the scenario: hybrid config"""
    def test_hybrid_config(self):
        """WHEN the code under test is exercised for: hybrid config"""
        cfg = self._build("hybrid")

        """THEN the expected behaviour holds: hybrid config"""
        assert cfg["methodology"] == "hybrid"

    """GIVEN build demo config dict and the scenario: default is scrum"""
    def test_default_is_scrum(self):
        """WHEN the code under test is exercised for: default is scrum"""
        cfg = self._build()

        """THEN the expected behaviour holds: default is scrum"""
        assert cfg["methodology"] == "scrum"

    """GIVEN build demo config dict and the scenario: common fields present"""
    def test_common_fields_present(self):
        """THEN the expected behaviour holds: common fields present"""
        for m in ("scrum", "kanban", "waterfall", "hybrid"):
            cfg = self._build(m)
            assert "jira" in cfg
            assert "teams" in cfg
            assert len(cfg["teams"]) == 3
            assert "dashboard" in cfg
            assert "branding" in cfg["dashboard"]

    """GIVEN build demo config dict and the scenario: output path customizable"""
    def test_output_path_customizable(self):
        """WHEN the code under test is exercised for: output path customizable"""
        from flowboard.web.server_helpers import build_demo_config_dict

        cfg = build_demo_config_dict(output_path="custom/path.html", methodology="kanban")

        """THEN the expected behaviour holds: output path customizable"""
        assert cfg["output"]["path"] == "custom/path.html"
        assert cfg["methodology"] == "kanban"


# ===================================================================
# API endpoint /api/demo with methodology
# ===================================================================


class TestDemoAPIMethodology:
    """Tests for demo a p i methodology."""

    @pytest.fixture()
    def client(self):
        from fastapi.testclient import TestClient

        from flowboard.web.server import create_app

        app = create_app(config_path=None, first_run=True)
        return TestClient(app, raise_server_exceptions=False)

    """GIVEN demo a p i methodology and the scenario: demo accepts methodology body"""
    def test_demo_accepts_methodology_body(self, client):
        """WHEN the code under test is exercised for: demo accepts methodology body"""
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

        """THEN the expected behaviour holds: demo accepts methodology body"""
        assert resp.status_code == 500

    """GIVEN demo a p i methodology and the scenario: demo invalid methodology falls back"""
    def test_demo_invalid_methodology_falls_back(self, client):
        """WHEN the code under test is exercised for: demo invalid methodology falls back"""
        from unittest.mock import patch

        with patch(
            "flowboard.web.server.locate_demo_fixture", side_effect=FileNotFoundError("no fixture")
        ):
            resp = client.post(
                "/api/demo",
                json={"methodology": "invalid_method"},
                headers={"X-Requested-With": "FlowBoard"},
            )

        """THEN the expected behaviour holds: demo invalid methodology falls back"""
        assert resp.status_code == 500  # fixture error, not validation error

    """GIVEN demo a p i methodology and the scenario: demo empty body defaults to scrum"""
    def test_demo_empty_body_defaults_to_scrum(self, client):
        """WHEN the code under test is exercised for: demo empty body defaults to scrum"""
        from unittest.mock import patch

        with patch(
            "flowboard.web.server.locate_demo_fixture", side_effect=FileNotFoundError("no fixture")
        ):
            resp = client.post(
                "/api/demo",
                headers={"X-Requested-With": "FlowBoard"},
            )

        """THEN the expected behaviour holds: demo empty body defaults to scrum"""
        assert resp.status_code == 500  # fixture error, not crash


# ===================================================================
# Wizard HTML - Methodology picker
# ===================================================================


class TestWizardMethodologyPicker:
    """Tests for wizard methodology picker."""

    @pytest.fixture()
    def wizard_html(self) -> str:
        from flowboard.presentation.html.renderer import render_first_run

        return render_first_run()

    """GIVEN wizard methodology picker and the scenario: demo picker js function exists"""
    def test_demo_picker_js_function_exists(self, wizard_html):
        """THEN the expected behaviour holds: demo picker js function exists"""
        assert "showDemoMethodologyPicker" in wizard_html

    """GIVEN wizard methodology picker and the scenario: demo picker overlay id"""
    def test_demo_picker_overlay_id(self, wizard_html):
        """THEN the expected behaviour holds: demo picker overlay id"""
        assert "demoPickerOverlay" in wizard_html

    """GIVEN wizard methodology picker and the scenario: methodology cards defined"""
    def test_methodology_cards_defined(self, wizard_html):
        """THEN the expected behaviour holds: methodology cards defined"""
        assert "DEMO_METHODOLOGIES" in wizard_html

    """GIVEN wizard methodology picker and the scenario: scrum methodology in js"""
    def test_scrum_methodology_in_js(self, wizard_html):
        """THEN the expected behaviour holds: scrum methodology in js"""
        assert "'scrum'" in wizard_html

    """GIVEN wizard methodology picker and the scenario: kanban methodology in js"""
    def test_kanban_methodology_in_js(self, wizard_html):
        """THEN the expected behaviour holds: kanban methodology in js"""
        assert "'kanban'" in wizard_html

    """GIVEN wizard methodology picker and the scenario: waterfall methodology in js"""
    def test_waterfall_methodology_in_js(self, wizard_html):
        """THEN the expected behaviour holds: waterfall methodology in js"""
        assert "'waterfall'" in wizard_html

    """GIVEN wizard methodology picker and the scenario: hybrid methodology in js"""
    def test_hybrid_methodology_in_js(self, wizard_html):
        """THEN the expected behaviour holds: hybrid methodology in js"""
        assert "'hybrid'" in wizard_html

    """GIVEN wizard methodology picker and the scenario: demo grid css"""
    def test_demo_grid_css(self, wizard_html):
        """THEN the expected behaviour holds: demo grid css"""
        assert "wz-demo-grid" in wizard_html

    """GIVEN wizard methodology picker and the scenario: demo method card css"""
    def test_demo_method_card_css(self, wizard_html):
        """THEN the expected behaviour holds: demo method card css"""
        assert "wz-demo-method-card" in wizard_html

    """GIVEN wizard methodology picker and the scenario: focus trap for picker"""
    def test_focus_trap_for_picker(self, wizard_html):
        """THEN the expected behaviour holds: focus trap for picker"""
        assert "trapDemoPickerFocus" in wizard_html

    """GIVEN wizard methodology picker and the scenario: launch demo sends methodology"""
    def test_launch_demo_sends_methodology(self, wizard_html):
        """THEN the expected behaviour holds: launch demo sends methodology"""
        assert "launchDemo(m.key)" in wizard_html

    """GIVEN wizard methodology picker and the scenario: api demo call includes methodology"""
    def test_api_demo_call_includes_methodology(self, wizard_html):
        """THEN the expected behaviour holds: api demo call includes methodology"""
        assert "methodology:" in wizard_html

    """GIVEN wizard methodology picker and the scenario: close demo picker"""
    def test_close_demo_picker(self, wizard_html):
        """THEN the expected behaviour holds: close demo picker"""
        assert "closeDemoPicker" in wizard_html

    """GIVEN wizard methodology picker and the scenario: aria modal on picker"""
    def test_aria_modal_on_picker(self, wizard_html):
        """THEN the expected behaviour holds: aria modal on picker"""
        assert "'aria-modal': 'true'" in wizard_html

    """GIVEN wizard methodology picker and the scenario: demo method accent bar css"""
    def test_demo_method_accent_bar_css(self, wizard_html):
        """THEN the expected behaviour holds: demo method accent bar css"""
        assert "wz-demo-method-accent" in wizard_html

    """GIVEN wizard methodology picker and the scenario: responsive grid breakpoint"""
    def test_responsive_grid_breakpoint(self, wizard_html):
        """THEN the expected behaviour holds: responsive grid breakpoint"""
        assert "grid-template-columns: 1fr" in wizard_html


# ===================================================================
# i18n - methodology demo keys
# ===================================================================


class TestMethodologyDemoI18n:
    """Tests for methodology demo i18n."""

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

    """GIVEN methodology demo i18n and the scenario: en has key"""

    @pytest.mark.parametrize("key", REQUIRED_KEYS)
    def test_en_has_key(self, en_data, key):
        """THEN the expected behaviour holds: en has key"""
        assert key in en_data, f"Missing en.json key: {key}"
        assert len(en_data[key]) > 0

    """GIVEN methodology demo i18n and the scenario: pl has key"""

    @pytest.mark.parametrize("key", REQUIRED_KEYS)
    def test_pl_has_key(self, pl_data, key):
        """THEN the expected behaviour holds: pl has key"""
        assert key in pl_data, f"Missing pl.json key: {key}"
        assert len(pl_data[key]) > 0

    """GIVEN methodology demo i18n and the scenario: generating demo has placeholder"""
    def test_generating_demo_has_placeholder(self, en_data):
        """THEN the expected behaviour holds: generating demo has placeholder"""
        assert "{methodology}" in en_data["wizard.generating_demo"]

    """GIVEN methodology demo i18n and the scenario: generating demo pl has placeholder"""
    def test_generating_demo_pl_has_placeholder(self, pl_data):
        """THEN the expected behaviour holds: generating demo pl has placeholder"""
        assert "{methodology}" in pl_data["wizard.generating_demo"]

    """GIVEN methodology demo i18n and the scenario: i18n keys in wizard html"""
    def test_i18n_keys_in_wizard_html(self):
        """WHEN the code under test is exercised for: i18n keys in wizard html"""
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()

        """THEN the expected behaviour holds: i18n keys in wizard html"""
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
    """Tests for demo backward compat."""

    """GIVEN demo backward compat and the scenario: build demo config no args is scrum"""
    def test_build_demo_config_no_args_is_scrum(self):
        """WHEN the code under test is exercised for: build demo config no args is scrum"""
        from flowboard.web.server_helpers import build_demo_config_dict

        cfg = build_demo_config_dict()

        """THEN the expected behaviour holds: build demo config no args is scrum"""
        assert cfg["methodology"] == "scrum"
        assert "pi" in cfg

    """GIVEN demo backward compat and the scenario: all demo configs loadable"""
    def test_all_demo_configs_loadable(self):
        """WHEN the code under test is exercised for: all demo configs loadable"""
        from flowboard.infrastructure.config.loader import load_config_from_dict
        from flowboard.web.server_helpers import build_demo_config_dict

        """THEN the expected behaviour holds: all demo configs loadable"""
        for m in ("scrum", "kanban", "waterfall", "hybrid"):
            cfg_dict = build_demo_config_dict(methodology=m)
            cfg = load_config_from_dict(cfg_dict)
            assert cfg.methodology == m


# ===================================================================
# Demo toolbar in rendered dashboard
# ===================================================================


class TestDemoToolbar:
    """Tests for demo toolbar."""

    def _render(self, is_demo: bool = False, methodology: str = "scrum") -> str:
        from flowboard.domain.models import BoardSnapshot
        from flowboard.infrastructure.config.loader import load_config_from_dict
        from flowboard.presentation.html.renderer import render_dashboard
        from flowboard.web.server_helpers import build_demo_config_dict

        cfg = load_config_from_dict(build_demo_config_dict(methodology=methodology))
        snapshot = BoardSnapshot()
        return render_dashboard(snapshot, cfg, is_demo=is_demo)

    """GIVEN demo toolbar and the scenario: toolbar present when demo"""
    def test_toolbar_present_when_demo(self):
        """WHEN the code under test is exercised for: toolbar present when demo"""
        html = self._render(is_demo=True)

        """THEN the expected behaviour holds: toolbar present when demo"""
        assert 'class="demo-toolbar"' in html

    """GIVEN demo toolbar and the scenario: toolbar absent when not demo"""
    def test_toolbar_absent_when_not_demo(self):
        """WHEN the code under test is exercised for: toolbar absent when not demo"""
        html = self._render(is_demo=False)

        """THEN the expected behaviour holds: toolbar absent when not demo"""
        assert 'class="demo-toolbar"' not in html

    """GIVEN demo toolbar and the scenario: toolbar has methodology buttons"""
    def test_toolbar_has_methodology_buttons(self):
        """WHEN the code under test is exercised for: toolbar has methodology buttons"""
        html = self._render(is_demo=True)

        """THEN the expected behaviour holds: toolbar has methodology buttons"""
        assert "switchDemo('scrum')" in html
        assert "switchDemo('kanban')" in html
        assert "switchDemo('waterfall')" in html
        assert "switchDemo('hybrid')" in html

    """GIVEN demo toolbar and the scenario: toolbar active scrum"""
    def test_toolbar_active_scrum(self):
        """WHEN the code under test is exercised for: toolbar active scrum"""
        html = self._render(is_demo=True, methodology="scrum")

        """THEN the expected behaviour holds: toolbar active scrum"""
        assert 'aria-pressed="true">🏃 Scrum</button>' in html
        assert "onclick=\"switchDemo('kanban')\" " in html
        assert 'aria-pressed="false">📊 Kanban</button>' in html

    """GIVEN demo toolbar and the scenario: toolbar active kanban"""
    def test_toolbar_active_kanban(self):
        """WHEN the code under test is exercised for: toolbar active kanban"""
        html = self._render(is_demo=True, methodology="kanban")

        """THEN the expected behaviour holds: toolbar active kanban"""
        assert 'aria-pressed="true">📊 Kanban</button>' in html
        assert "onclick=\"switchDemo('scrum')\" " in html
        assert 'aria-pressed="false">🏃 Scrum</button>' in html

    """GIVEN demo toolbar and the scenario: toolbar has back button"""
    def test_toolbar_has_back_button(self):
        """WHEN the code under test is exercised for: toolbar has back button"""
        html = self._render(is_demo=True)

        """THEN the expected behaviour holds: toolbar has back button"""
        assert "backToWizard" in html

    """GIVEN demo toolbar and the scenario: toolbar has demo badge"""
    def test_toolbar_has_demo_badge(self):
        """WHEN the code under test is exercised for: toolbar has demo badge"""
        html = self._render(is_demo=True)

        """THEN the expected behaviour holds: toolbar has demo badge"""
        assert "demo-toolbar-badge" in html

    """GIVEN demo toolbar and the scenario: toolbar has aria label"""
    def test_toolbar_has_aria_label(self):
        """WHEN the code under test is exercised for: toolbar has aria label"""
        html = self._render(is_demo=True)

        """THEN the expected behaviour holds: toolbar has aria label"""
        assert 'role="banner"' in html

    """GIVEN demo toolbar and the scenario: toolbar css present"""
    def test_toolbar_css_present(self):
        """WHEN the code under test is exercised for: toolbar css present"""
        html = self._render(is_demo=True)

        """THEN the expected behaviour holds: toolbar css present"""
        assert ".demo-toolbar" in html
        assert "demo-toolbar-btn" in html


class TestDemoToolbarI18n:
    """Tests for demo toolbar i18n."""

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

    """GIVEN demo toolbar i18n and the scenario: en has key"""

    @pytest.mark.parametrize("key", TOOLBAR_KEYS)
    def test_en_has_key(self, en_data, key):
        """THEN the expected behaviour holds: en has key"""
        assert key in en_data

    """GIVEN demo toolbar i18n and the scenario: pl has key"""

    @pytest.mark.parametrize("key", TOOLBAR_KEYS)
    def test_pl_has_key(self, pl_data, key):
        """THEN the expected behaviour holds: pl has key"""
        assert key in pl_data


class TestResetEndpoint:
    """Tests for reset endpoint."""

    @pytest.fixture()
    def client(self):
        from fastapi.testclient import TestClient

        from flowboard.web.server import create_app

        app = create_app(config_path=None, first_run=True)
        return TestClient(app, raise_server_exceptions=False)

    """GIVEN reset endpoint and the scenario: reset returns wizard"""
    def test_reset_returns_wizard(self, client):
        """WHEN the code under test is exercised for: reset returns wizard"""
        resp = client.get("/?reset=1")

        """THEN the expected behaviour holds: reset returns wizard"""
        assert resp.status_code == 200
        # Should show first-run wizard, not a dashboard
        assert (
            "wizard" in resp.text.lower() or "first-run" in resp.text.lower() or "wz-" in resp.text
        )
