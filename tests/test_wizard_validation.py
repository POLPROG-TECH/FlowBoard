"""Wizard validation and UI interaction tests - keyboard nav, ARIA, focus traps, inline validation, URL validation."""

from __future__ import annotations

import json

# ===================================================================
# Wizard route registration
# ===================================================================


class TestKeyboardNavigation:
    """Tests for keyboard navigation."""

    """GIVEN keyboard navigation and the scenario: cards have tabindex"""
    def test_cards_have_tabindex(self):
        """WHEN the code under test is exercised for: cards have tabindex"""
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()

        """THEN the expected behaviour holds: cards have tabindex"""
        assert "tabindex" in html

    """GIVEN keyboard navigation and the scenario: cards have keydown handlers"""
    def test_cards_have_keydown_handlers(self):
        """WHEN the code under test is exercised for: cards have keydown handlers"""
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()

        """THEN the expected behaviour holds: cards have keydown handlers"""
        assert "onkeydown" in html

    """GIVEN keyboard navigation and the scenario: chips keyboard accessible"""
    def test_chips_keyboard_accessible(self):
        """WHEN the code under test is exercised for: chips keyboard accessible"""
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()
        # Chips should have role=checkbox and aria-checked

        """THEN the expected behaviour holds: chips keyboard accessible"""
        assert "role" in html
        assert "checkbox" in html


# ===================================================================
# ARIA labels
# ===================================================================


class TestARIALabels:
    """Tests for a r i a labels."""

    """GIVEN a r i a labels and the scenario: stepper has nav role"""
    def test_stepper_has_nav_role(self):
        """WHEN the code under test is exercised for: stepper has nav role"""
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()

        """THEN the expected behaviour holds: stepper has nav role"""
        assert "role" in html
        assert "navigation" in html or "aria-label" in html

    """GIVEN a r i a labels and the scenario: status areas have aria live"""
    def test_status_areas_have_aria_live(self):
        """WHEN the code under test is exercised for: status areas have aria live"""
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()

        """THEN the expected behaviour holds: status areas have aria live"""
        assert "aria-live" in html

    """GIVEN a r i a labels and the scenario: buttons have aria labels"""
    def test_buttons_have_aria_labels(self):
        """WHEN the code under test is exercised for: buttons have aria labels"""
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()

        """THEN the expected behaviour holds: buttons have aria labels"""
        assert "aria-label" in html


# ===================================================================
# Focus trap in import modal
# ===================================================================


class TestFocusTrap:
    """Tests for focus trap."""

    """GIVEN focus trap and the scenario: overlay class exists"""
    def test_overlay_class_exists(self):
        """WHEN the code under test is exercised for: overlay class exists"""
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()

        """THEN the expected behaviour holds: overlay class exists"""
        assert "wz-overlay" in html

    """GIVEN focus trap and the scenario: trap focus function"""
    def test_trap_focus_function(self):
        """WHEN the code under test is exercised for: trap focus function"""
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()

        """THEN the expected behaviour holds: trap focus function"""
        assert "trapFocus" in html

    """GIVEN focus trap and the scenario: modal has dialog role"""
    def test_modal_has_dialog_role(self):
        """WHEN the code under test is exercised for: modal has dialog role"""
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()

        """THEN the expected behaviour holds: modal has dialog role"""
        assert "aria-modal" in html

    """GIVEN focus trap and the scenario: escape closes modal"""
    def test_escape_closes_modal(self):
        """WHEN the code under test is exercised for: escape closes modal"""
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()

        """THEN the expected behaviour holds: escape closes modal"""
        assert "Escape" in html
        assert "closeImportModal" in html


# ===================================================================
# Inline validation
# ===================================================================


class TestInlineValidation:
    """Tests for inline validation."""

    """GIVEN inline validation and the scenario: validate url function"""
    def test_validate_url_function(self):
        """WHEN the code under test is exercised for: validate url function"""
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()

        """THEN the expected behaviour holds: validate url function"""
        assert "validateUrl" in html

    """GIVEN inline validation and the scenario: validate email function"""
    def test_validate_email_function(self):
        """WHEN the code under test is exercised for: validate email function"""
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()

        """THEN the expected behaviour holds: validate email function"""
        assert "validateEmail" in html

    """GIVEN inline validation and the scenario: validate token function"""
    def test_validate_token_function(self):
        """WHEN the code under test is exercised for: validate token function"""
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()

        """THEN the expected behaviour holds: validate token function"""
        assert "validateToken" in html

    """GIVEN inline validation and the scenario: error div exists"""
    def test_error_div_exists(self):
        """WHEN the code under test is exercised for: error div exists"""
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()

        """THEN the expected behaviour holds: error div exists"""
        assert "wz-error" in html
        assert "has-error" in html


# ===================================================================
# Error toast longer timeout
# ===================================================================


class TestErrorToastTimeout:
    """Tests for error toast timeout."""

    """GIVEN error toast timeout and the scenario: different timeout for errors"""
    def test_different_timeout_for_errors(self):
        """WHEN the code under test is exercised for: different timeout for errors"""
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()

        """THEN the expected behaviour holds: different timeout for errors"""
        assert "5500" in html  # error timeout
        assert "3500" in html  # success timeout


# ===================================================================
# Retry button on connection errors
# ===================================================================


class TestRetryButton:
    """Tests for retry button."""

    """GIVEN retry button and the scenario: retry in show conn status"""
    def test_retry_in_show_conn_status(self):
        """WHEN the code under test is exercised for: retry in show conn status"""
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()

        """THEN the expected behaviour holds: retry in show conn status"""
        assert "retry" in html.lower()

    """GIVEN retry button and the scenario: retry i18n key"""
    def test_retry_i18n_key(self):
        """WHEN the code under test is exercised for: retry i18n key"""
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()

        """THEN the expected behaviour holds: retry i18n key"""
        assert "T.retry" in html


# ===================================================================
# GET /api/wizard/config endpoint
# ===================================================================


class TestGetConfigEndpoint:
    """Tests for get config endpoint."""

    """GIVEN get config endpoint and the scenario: config route registered"""
    def test_config_route_registered(self):
        """WHEN the code under test is exercised for: config route registered"""
        from flowboard.web.server import create_app

        app = create_app(config_path=None, first_run=True)
        routes = [r.path for r in app.routes]

        """THEN the expected behaviour holds: config route registered"""
        assert "/api/wizard/config" in routes

    """GIVEN get config endpoint and the scenario: config returns null when no config"""
    def test_config_returns_null_when_no_config(self):
        """WHEN the code under test is exercised for: config returns null when no config"""
        from fastapi.testclient import TestClient

        from flowboard.web.server import create_app

        app = create_app(config_path=None, first_run=True)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            "/api/wizard/config",
            headers={"X-Requested-With": "FlowBoard"},
        )
        data = resp.json()

        """THEN the expected behaviour holds: config returns null when no config"""
        assert data["ok"] is True
        assert data["exists"] is False or data["config"] is None


# ===================================================================
# Standardized error responses
# ===================================================================


class TestStandardizedErrors:
    """Tests for standardized errors."""

    """GIVEN standardized errors and the scenario: error response has error type"""
    def test_error_response_has_error_type(self):
        """WHEN the code under test is exercised for: error response has error type"""
        from flowboard.web.routes_wizard import _error_response

        resp = _error_response("test error", error_type="test_type")
        body = json.loads(resp.body)

        """THEN the expected behaviour holds: error response has error type"""
        assert body["ok"] is False
        assert body["error"] == "test error"
        assert body["error_type"] == "test_type"

    """GIVEN standardized errors and the scenario: verify returns error type on failure"""
    def test_verify_returns_error_type_on_failure(self):
        """WHEN the code under test is exercised for: verify returns error type on failure"""
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

        """THEN the expected behaviour holds: verify returns error type on failure"""
        assert "error_type" in data


# ===================================================================
# Content-Type validation
# ===================================================================


class TestContentTypeValidation:
    """Tests for content type validation."""

    """GIVEN content type validation and the scenario: verify rejects non json"""
    def test_verify_rejects_non_json(self):
        """WHEN the code under test is exercised for: verify rejects non json"""
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

        """THEN the expected behaviour holds: verify rejects non json"""
        assert data["ok"] is False
        assert "Content-Type" in data["error"] or "content" in data["error"].lower()

    """GIVEN content type validation and the scenario: validate content type function"""
    def test_validate_content_type_function(self):
        """WHEN the code under test is exercised for: validate content type function"""
        from flowboard.web.routes_wizard import _validate_content_type

        """THEN the expected behaviour holds: validate content type function"""
        assert callable(_validate_content_type)


# ===================================================================
# noscript fallback
# ===================================================================


class TestNoscript:
    """Tests for noscript."""

    """GIVEN noscript and the scenario: noscript tag exists"""
    def test_noscript_tag_exists(self):
        """WHEN the code under test is exercised for: noscript tag exists"""
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()

        """THEN the expected behaviour holds: noscript tag exists"""
        assert "<noscript>" in html
        assert "JavaScript" in html


# ===================================================================
# Review shows field mappings
# ===================================================================


class TestReviewFieldMappings:
    """Tests for review field mappings."""

    """GIVEN review field mappings and the scenario: review fields label"""
    def test_review_fields_label(self):
        """WHEN the code under test is exercised for: review fields label"""
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()

        """THEN the expected behaviour holds: review fields label"""
        assert "review_fields" in html

    """GIVEN review field mappings and the scenario: review fields i18n key"""
    def test_review_fields_i18n_key(self):
        """WHEN the code under test is exercised for: review fields i18n key"""
        with open("src/flowboard/i18n/en.json") as f:
            keys = json.load(f)

        """THEN the expected behaviour holds: review fields i18n key"""
        assert "wizard.review_fields" in keys


# ===================================================================
# Slider help text
# ===================================================================


class TestSliderHelpText:
    """Tests for slider help text."""

    """GIVEN slider help text and the scenario: slider help class"""
    def test_slider_help_class(self):
        """WHEN the code under test is exercised for: slider help class"""
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()

        """THEN the expected behaviour holds: slider help class"""
        assert "wz-slider-help" in html

    """GIVEN slider help text and the scenario: hint i18n keys exist"""
    def test_hint_i18n_keys_exist(self):
        """WHEN the code under test is exercised for: hint i18n keys exist"""
        with open("src/flowboard/i18n/en.json") as f:
            keys = json.load(f)

        """THEN the expected behaviour holds: hint i18n keys exist"""
        assert "wizard.overload_hint" in keys
        assert "wizard.wip_hint" in keys
        assert "wizard.aging_hint" in keys


# ===================================================================
# Hex color normalization
# ===================================================================


class TestHexColorNormalization:
    """Tests for hex color normalization."""

    """GIVEN hex color normalization and the scenario: hex input exists"""
    def test_hex_input_exists(self):
        """WHEN the code under test is exercised for: hex input exists"""
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()

        """THEN the expected behaviour holds: hex input exists"""
        assert "wz-color-hex" in html

    """GIVEN hex color normalization and the scenario: lowercase normalization"""
    def test_lowercase_normalization(self):
        """WHEN the code under test is exercised for: lowercase normalization"""
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()

        """THEN the expected behaviour holds: lowercase normalization"""
        assert "toLowerCase()" in html


# ===================================================================
# Pagination on /projects endpoint
# ===================================================================


class TestProjectsPagination:
    """Tests for projects pagination."""

    """GIVEN projects pagination and the scenario: offset in response"""
    def test_offset_in_response(self):
        """WHEN the code under test is exercised for: offset in response"""
        import inspect

        from flowboard.web.routes_wizard import wizard_projects

        src = inspect.getsource(wizard_projects)

        """THEN the expected behaviour holds: offset in response"""
        assert "offset" in src
        assert "limit" in src

    """GIVEN projects pagination and the scenario: has more flag in response"""
    def test_has_more_flag_in_response(self):
        """WHEN the code under test is exercised for: has more flag in response"""
        import inspect

        from flowboard.web.routes_wizard import wizard_projects

        src = inspect.getsource(wizard_projects)

        """THEN the expected behaviour holds: has more flag in response"""
        assert "has_more" in src


# ===================================================================
# Inline help Cloud vs Server
# ===================================================================


class TestAuthMethodHelp:
    """Tests for auth method help."""

    """GIVEN auth method help and the scenario: auth hints in template"""
    def test_auth_hints_in_template(self):
        """WHEN the code under test is exercised for: auth hints in template"""
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()

        """THEN the expected behaviour holds: auth hints in template"""
        assert "auth_basic_hint" in html
        assert "auth_pat_hint" in html

    """GIVEN auth method help and the scenario: auth hint i18n keys"""
    def test_auth_hint_i18n_keys(self):
        """WHEN the code under test is exercised for: auth hint i18n keys"""
        with open("src/flowboard/i18n/en.json") as f:
            keys = json.load(f)

        """THEN the expected behaviour holds: auth hint i18n keys"""
        assert "wizard.auth_basic_hint" in keys
        assert "wizard.auth_pat_hint" in keys

    """GIVEN auth method help and the scenario: auth hints in polish"""
    def test_auth_hints_in_polish(self):
        """WHEN the code under test is exercised for: auth hints in polish"""
        with open("src/flowboard/i18n/pl.json") as f:
            keys = json.load(f)

        """THEN the expected behaviour holds: auth hints in polish"""
        assert "wizard.auth_basic_hint" in keys
        assert "wizard.auth_pat_hint" in keys


# ===================================================================
# URL validation helper
# ===================================================================


class TestURLValidation:
    """Tests for u r l validation."""

    """GIVEN u r l validation and the scenario: rejects ftp"""
    def test_rejects_ftp(self):
        """WHEN the code under test is exercised for: rejects ftp"""
        from flowboard.web.routes_wizard import _validate_url

        """THEN the expected behaviour holds: rejects ftp"""
        assert _validate_url("ftp://example.com") is not None

    """GIVEN u r l validation and the scenario: accepts https"""
    def test_accepts_https(self):
        """WHEN the code under test is exercised for: accepts https"""
        from flowboard.web.routes_wizard import _validate_url

        """THEN the expected behaviour holds: accepts https"""
        assert _validate_url("https://example.com") is None

    """GIVEN u r l validation and the scenario: accepts http"""
    def test_accepts_http(self):
        """WHEN the code under test is exercised for: accepts http"""
        from flowboard.web.routes_wizard import _validate_url

        """THEN the expected behaviour holds: accepts http"""
        assert _validate_url("http://example.com") is None

    """GIVEN u r l validation and the scenario: rejects no hostname"""
    def test_rejects_no_hostname(self):
        """WHEN the code under test is exercised for: rejects no hostname"""
        from flowboard.web.routes_wizard import _validate_url

        """THEN the expected behaviour holds: rejects no hostname"""
        assert _validate_url("https://") is not None

    """GIVEN u r l validation and the scenario: rejects garbage"""
    def test_rejects_garbage(self):
        """WHEN the code under test is exercised for: rejects garbage"""
        from flowboard.web.routes_wizard import _validate_url

        """THEN the expected behaviour holds: rejects garbage"""
        assert _validate_url("not a url") is not None


# ===================================================================
# make_jira_config helper
# ===================================================================


class TestMakeJiraConfig:
    """Tests for make jira config."""

    """GIVEN make jira config and the scenario: creates valid config"""
    def test_creates_valid_config(self):
        """WHEN the code under test is exercised for: creates valid config"""
        from flowboard.web.routes_wizard import _make_jira_config

        cfg = _make_jira_config("https://x.com", "a@b.com", "token123")

        """THEN the expected behaviour holds: creates valid config"""
        assert cfg.base_url == "https://x.com"
        assert cfg.auth_method == "basic"

    """GIVEN make jira config and the scenario: pat when no email"""
    def test_pat_when_no_email(self):
        """WHEN the code under test is exercised for: pat when no email"""
        from flowboard.web.routes_wizard import _make_jira_config

        cfg = _make_jira_config("https://x.com", "", "token123")

        """THEN the expected behaviour holds: pat when no email"""
        assert cfg.auth_method == "pat"


# ===================================================================
# No innerHTML in updated template
# ===================================================================


class TestNoInnerHTML:
    """Tests for no inner h t m l."""

    """GIVEN no inner h t m l and the scenario: wizard still no innerhtml"""
    def test_wizard_still_no_innerhtml(self):
        """WHEN the code under test is exercised for: wizard still no innerhtml"""
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()

        """THEN the expected behaviour holds: wizard still no innerhtml"""
        assert "innerHTML" not in html
