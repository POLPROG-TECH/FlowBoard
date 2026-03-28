"""Wizard validation and UI interaction tests — keyboard nav, ARIA, focus traps, inline validation, URL validation."""

from __future__ import annotations

import json

# ===================================================================
# Wizard route registration
# ===================================================================


class TestKeyboardNavigation:
    """Verify keyboard-accessible cards and chips."""

    def test_cards_have_tabindex(self):
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()
        assert "tabindex" in html

    def test_cards_have_keydown_handlers(self):
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()
        assert "onkeydown" in html

    def test_chips_keyboard_accessible(self):
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()
        # Chips should have role=checkbox and aria-checked
        assert "role" in html
        assert "checkbox" in html


# ===================================================================
# ARIA labels
# ===================================================================


class TestARIALabels:
    """Verify proper ARIA attributes on wizard elements."""

    def test_stepper_has_nav_role(self):
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()
        assert "role" in html
        assert "navigation" in html or "aria-label" in html

    def test_status_areas_have_aria_live(self):
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()
        assert "aria-live" in html

    def test_buttons_have_aria_labels(self):
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()
        assert "aria-label" in html


# ===================================================================
# Focus trap in import modal
# ===================================================================


class TestFocusTrap:
    """Verify import modal has focus trap behavior."""

    def test_overlay_class_exists(self):
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()
        assert "wz-overlay" in html

    def test_trap_focus_function(self):
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()
        assert "trapFocus" in html

    def test_modal_has_dialog_role(self):
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()
        assert "aria-modal" in html

    def test_escape_closes_modal(self):
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()
        assert "Escape" in html
        assert "closeImportModal" in html


# ===================================================================
# Inline validation
# ===================================================================


class TestInlineValidation:
    """Verify real-time field validation functions exist."""

    def test_validate_url_function(self):
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()
        assert "validateUrl" in html

    def test_validate_email_function(self):
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()
        assert "validateEmail" in html

    def test_validate_token_function(self):
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()
        assert "validateToken" in html

    def test_error_div_exists(self):
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()
        assert "wz-error" in html
        assert "has-error" in html


# ===================================================================
# Error toast longer timeout
# ===================================================================


class TestErrorToastTimeout:
    """Verify error toasts display longer than success toasts."""

    def test_different_timeout_for_errors(self):
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()
        assert "5500" in html  # error timeout
        assert "3500" in html  # success timeout


# ===================================================================
# Retry button on connection errors
# ===================================================================


class TestRetryButton:
    """Verify retry button appears on connection failure."""

    def test_retry_in_show_conn_status(self):
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()
        assert "retry" in html.lower()

    def test_retry_i18n_key(self):
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()
        assert "T.retry" in html


# ===================================================================
# GET /api/wizard/config endpoint
# ===================================================================


class TestGetConfigEndpoint:
    """Verify GET /api/wizard/config endpoint exists and works."""

    def test_config_route_registered(self):
        from flowboard.web.server import create_app

        app = create_app(config_path=None, first_run=True)
        routes = [r.path for r in app.routes]
        assert "/api/wizard/config" in routes

    def test_config_returns_null_when_no_config(self):
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
        assert data["exists"] is False or data["config"] is None


# ===================================================================
# Standardized error responses
# ===================================================================


class TestStandardizedErrors:
    """Verify all error responses include error_type field."""

    def test_error_response_has_error_type(self):
        from flowboard.web.routes_wizard import _error_response

        resp = _error_response("test error", error_type="test_type")
        body = json.loads(resp.body)
        assert body["ok"] is False
        assert body["error"] == "test error"
        assert body["error_type"] == "test_type"

    def test_verify_returns_error_type_on_failure(self):
        from fastapi.testclient import TestClient

        from flowboard.web.server import create_app

        app = create_app(config_path=None, first_run=True)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/wizard/verify",
            json={},
            headers={"X-Requested-With": "FlowBoard"},
        )
        data = resp.json()
        assert "error_type" in data


# ===================================================================
# Content-Type validation
# ===================================================================


class TestContentTypeValidation:
    """Verify endpoints reject non-JSON content types."""

    def test_verify_rejects_non_json(self):
        from fastapi.testclient import TestClient

        from flowboard.web.server import create_app

        app = create_app(config_path=None, first_run=True)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/wizard/verify",
            content="not json",
            headers={"X-Requested-With": "FlowBoard", "Content-Type": "text/plain"},
        )
        data = resp.json()
        assert data["ok"] is False
        assert "Content-Type" in data["error"] or "content" in data["error"].lower()

    def test_validate_content_type_function(self):
        from flowboard.web.routes_wizard import _validate_content_type

        assert callable(_validate_content_type)


# ===================================================================
# noscript fallback
# ===================================================================


class TestNoscript:
    """Verify noscript message is present."""

    def test_noscript_tag_exists(self):
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()
        assert "<noscript>" in html
        assert "JavaScript" in html


# ===================================================================
# Review shows field mappings
# ===================================================================


class TestReviewFieldMappings:
    """Verify review screen displays field mapping info."""

    def test_review_fields_label(self):
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()
        assert "review_fields" in html

    def test_review_fields_i18n_key(self):
        with open("src/flowboard/i18n/en.json") as f:
            keys = json.load(f)
        assert "wizard.review_fields" in keys


# ===================================================================
# Slider help text
# ===================================================================


class TestSliderHelpText:
    """Verify sliders have descriptive help text."""

    def test_slider_help_class(self):
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()
        assert "wz-slider-help" in html

    def test_hint_i18n_keys_exist(self):
        with open("src/flowboard/i18n/en.json") as f:
            keys = json.load(f)
        assert "wizard.overload_hint" in keys
        assert "wizard.wip_hint" in keys
        assert "wizard.aging_hint" in keys


# ===================================================================
# Hex color normalization
# ===================================================================


class TestHexColorNormalization:
    """Verify color picker normalizes to lowercase hex."""

    def test_hex_input_exists(self):
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()
        assert "wz-color-hex" in html

    def test_lowercase_normalization(self):
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()
        assert "toLowerCase()" in html


# ===================================================================
# Pagination on /projects endpoint
# ===================================================================


class TestProjectsPagination:
    """Verify /projects endpoint supports pagination params."""

    def test_offset_in_response(self):
        """Verify endpoint code parses offset/limit."""
        import inspect

        from flowboard.web.routes_wizard import wizard_projects

        src = inspect.getsource(wizard_projects)
        assert "offset" in src
        assert "limit" in src

    def test_has_more_flag_in_response(self):
        import inspect

        from flowboard.web.routes_wizard import wizard_projects

        src = inspect.getsource(wizard_projects)
        assert "has_more" in src


# ===================================================================
# Inline help Cloud vs Server
# ===================================================================


class TestAuthMethodHelp:
    """Verify auth method selection shows explanatory hints."""

    def test_auth_hints_in_template(self):
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()
        assert "auth_basic_hint" in html
        assert "auth_pat_hint" in html

    def test_auth_hint_i18n_keys(self):
        with open("src/flowboard/i18n/en.json") as f:
            keys = json.load(f)
        assert "wizard.auth_basic_hint" in keys
        assert "wizard.auth_pat_hint" in keys

    def test_auth_hints_in_polish(self):
        with open("src/flowboard/i18n/pl.json") as f:
            keys = json.load(f)
        assert "wizard.auth_basic_hint" in keys
        assert "wizard.auth_pat_hint" in keys


# ===================================================================
# URL validation helper
# ===================================================================


class TestURLValidation:
    """Verify URL validation rejects invalid schemes."""

    def test_rejects_ftp(self):
        from flowboard.web.routes_wizard import _validate_url

        assert _validate_url("ftp://example.com") is not None

    def test_accepts_https(self):
        from flowboard.web.routes_wizard import _validate_url

        assert _validate_url("https://example.com") is None

    def test_accepts_http(self):
        from flowboard.web.routes_wizard import _validate_url

        assert _validate_url("http://example.com") is None

    def test_rejects_no_hostname(self):
        from flowboard.web.routes_wizard import _validate_url

        assert _validate_url("https://") is not None

    def test_rejects_garbage(self):
        from flowboard.web.routes_wizard import _validate_url

        assert _validate_url("not a url") is not None


# ===================================================================
# make_jira_config helper
# ===================================================================


class TestMakeJiraConfig:
    """Verify the shared JiraConfig builder."""

    def test_creates_valid_config(self):
        from flowboard.web.routes_wizard import _make_jira_config

        cfg = _make_jira_config("https://x.com", "a@b.com", "token123")
        assert cfg.base_url == "https://x.com"
        assert cfg.auth_method == "basic"

    def test_pat_when_no_email(self):
        from flowboard.web.routes_wizard import _make_jira_config

        cfg = _make_jira_config("https://x.com", "", "token123")
        assert cfg.auth_method == "pat"


# ===================================================================
# No innerHTML in updated template
# ===================================================================


class TestNoInnerHTML:
    """Ensure no innerHTML patterns crept back in."""

    def test_wizard_still_no_innerhtml(self):
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()
        assert "innerHTML" not in html
