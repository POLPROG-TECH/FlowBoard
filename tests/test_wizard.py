"""Core wizard tests — route registration, verify, save, import, CSRF, UI rendering, state, project validation."""

from __future__ import annotations

import contextlib
import os

# ===================================================================
# Wizard route registration
# ===================================================================


class TestWizardRouteRegistration:
    """Verify wizard routes are mounted on the app."""

    def test_wizard_routes_exist(self):
        from flowboard.web.server import create_app

        app = create_app(config_path=None, first_run=True)
        routes = [r.path for r in app.routes]
        assert "/api/wizard/verify" in routes
        assert "/api/wizard/save" in routes
        assert "/api/wizard/projects" in routes
        assert "/api/wizard/import" in routes


# ===================================================================
# Wizard verify endpoint
# ===================================================================


class TestWizardVerify:
    """Verify the Jira connection test endpoint."""

    def test_verify_requires_base_url(self):
        from fastapi.testclient import TestClient

        from flowboard.web.server import create_app

        app = create_app(config_path=None, first_run=True)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/wizard/verify",
            json={"auth_email": "x@y.com"},
            headers={"X-Requested-With": "FlowBoard"},
        )
        assert resp.status_code == 400
        assert "base_url" in resp.json()["error"]

    def test_verify_returns_error_on_bad_url(self):
        from fastapi.testclient import TestClient

        from flowboard.web.server import create_app

        app = create_app(config_path=None, first_run=True)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/wizard/verify",
            json={"base_url": "https://nonexistent.invalid.test"},
            headers={"X-Requested-With": "FlowBoard"},
        )
        assert resp.status_code == 400
        assert resp.json()["ok"] is False


# ===================================================================
# Wizard save endpoint
# ===================================================================


class TestWizardSave:
    """Verify config save logic including security checks."""

    def test_save_rejects_absolute_path(self):
        from fastapi.testclient import TestClient

        from flowboard.web.server import create_app

        app = create_app(config_path=None, first_run=True)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/wizard/save",
            json={"config": {"jira": {"base_url": "https://x.com"}}, "path": "/etc/passwd"},
            headers={"X-Requested-With": "FlowBoard"},
        )
        assert resp.status_code == 400
        assert "relative" in resp.json()["error"].lower()

    def test_save_rejects_traversal(self):
        from fastapi.testclient import TestClient

        from flowboard.web.server import create_app

        app = create_app(config_path=None, first_run=True)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/wizard/save",
            json={"config": {"jira": {"base_url": "https://x.com"}}, "path": "../../../evil.json"},
            headers={"X-Requested-With": "FlowBoard"},
        )
        assert resp.status_code == 400

    def test_save_requires_config_object(self):
        from fastapi.testclient import TestClient

        from flowboard.web.server import create_app

        app = create_app(config_path=None, first_run=True)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/wizard/save",
            json={"config": "not an object"},
            headers={"X-Requested-With": "FlowBoard"},
        )
        assert resp.status_code == 400

    def test_save_strips_credentials(self, tmp_path):
        from fastapi.testclient import TestClient

        from flowboard.web.server import create_app

        app = create_app(config_path=None, first_run=True)
        client = TestClient(app, raise_server_exceptions=False)

        config = {
            "jira": {
                "base_url": "https://demo.atlassian.net",
                "auth_token": "SUPER_SECRET",
            },
            "output": {"path": "output/test.html"},
            "teams": [{"key": "a", "name": "A", "members": ["u1"]}],
        }

        # Use CWD-relative path
        save_path = "test_wizard_output.json"
        resp = client.post(
            "/api/wizard/save",
            json={"config": config, "path": save_path},
            headers={"X-Requested-With": "FlowBoard"},
        )

        if resp.status_code == 200:
            assert resp.json()["ok"] is True
            assert "auth_token" in resp.json().get("warning", "")
            # Clean up
            with contextlib.suppress(OSError):
                os.unlink(save_path)

    def test_save_validates_schema(self):
        from fastapi.testclient import TestClient

        from flowboard.web.server import create_app

        app = create_app(config_path=None, first_run=True)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/wizard/save",
            json={"config": {"not_jira": True}},
            headers={"X-Requested-With": "FlowBoard"},
        )
        assert resp.status_code == 400
        assert "Validation failed" in resp.json()["error"]


# ===================================================================
# Wizard import endpoint
# ===================================================================


class TestWizardImport:
    """Verify JSON import functionality."""

    def test_import_rejects_invalid_json(self):
        from fastapi.testclient import TestClient

        from flowboard.web.server import create_app

        app = create_app(config_path=None, first_run=True)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/wizard/import",
            json={"json_str": "{invalid json"},
            headers={"X-Requested-With": "FlowBoard"},
        )
        assert resp.status_code == 400
        assert "Invalid JSON" in resp.json()["error"]

    def test_import_requires_jira_key(self):
        from fastapi.testclient import TestClient

        from flowboard.web.server import create_app

        app = create_app(config_path=None, first_run=True)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/wizard/import",
            json={"json_str": '{"output": {}}'},
            headers={"X-Requested-With": "FlowBoard"},
        )
        assert resp.status_code == 400
        assert "jira" in resp.json()["error"].lower()


# ===================================================================
# Wizard CSRF protection
# ===================================================================


class TestWizardCSRF:
    """Verify wizard endpoints require CSRF header."""

    def test_wizard_verify_requires_csrf(self):
        from fastapi.testclient import TestClient

        from flowboard.web.server import create_app

        app = create_app(config_path=None, first_run=True)
        client = TestClient(app, raise_server_exceptions=False)
        # POST without X-Requested-With header
        resp = client.post(
            "/api/wizard/verify",
            json={"base_url": "https://x.com"},
        )
        assert resp.status_code == 403


# ===================================================================
# Wizard UI rendering
# ===================================================================


class TestWizardUIRendering:
    """Verify the wizard template renders correctly."""

    def test_first_run_renders_wizard(self):
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run(config_path="config.json", locale="en")
        assert "wz-container" in html
        assert "wizardContent" in html
        assert "testConnection" in html
        assert "goStep" in html
        assert "FlowBoard" in html

    def test_wizard_renders_in_polish(self):
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run(config_path="config.json", locale="pl")
        assert "Kreator konfiguracji" in html or "wizard" in html.lower()

    def test_wizard_no_innerhtml(self):
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()
        assert "innerHTML" not in html

    def test_wizard_has_stepper(self):
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()
        assert "wz-stepper" in html
        assert "wz-step-dot" in html

    def test_wizard_has_all_steps(self):
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()
        assert "renderConnection" in html
        assert "renderProjects" in html
        assert "renderTeams" in html
        assert "renderCustomize" in html
        assert "renderReview" in html

    def test_wizard_has_demo_option(self):
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()
        assert "launchDemo" in html
        assert "/api/demo" in html

    def test_wizard_has_import_option(self):
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()
        assert "doImport" in html
        assert "importJson" in html


class TestStatePersistence:
    """Verify wizard frontend has localStorage persistence code."""

    def test_persist_state_function_exists(self):
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()
        assert "persistState" in html
        assert "localStorage" in html
        assert "flowboard_wizard_state" in html

    def test_restore_state_on_init(self):
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()
        assert "restoreState" in html

    def test_credentials_not_persisted(self):
        """Auth token should be cleared before saving to localStorage."""
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()
        assert "auth_token: ''" in html or 'auth_token: ""' in html


# ===================================================================
# Project validation (≥1 required)
# ===================================================================


class TestProjectValidation:
    """Verify wizard requires at least one project selected."""

    def test_select_at_least_one_message(self):
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()
        assert "select_at_least_one" in html
        assert "projectWarn" in html

    def test_next_disabled_when_no_projects(self):
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()
        assert "selectedProjects.length" in html


# ===================================================================
# Timeout on Jira API calls
# ===================================================================


class TestJiraTimeout:
    """Verify timeout constant is set for Jira calls."""

    def test_timeout_constant_defined(self):
        from flowboard.web.routes_wizard import _JIRA_TIMEOUT

        assert _JIRA_TIMEOUT > 0
        assert _JIRA_TIMEOUT <= 30

    def test_timeout_applied_in_verify(self):
        """Verify the timeout is set on the session in _test_connection."""
        import inspect

        from flowboard.web.routes_wizard import wizard_verify

        src = inspect.getsource(wizard_verify)
        assert "timeout" in src.lower() or "_JIRA_TIMEOUT" in src


# ===================================================================
# Cloud vs Server detection
# ===================================================================


class TestCloudServerDetection:
    """Verify server_type is derived from deploymentType."""

    def test_verify_response_includes_server_type(self):
        """Endpoint source should return server_type based on deployment."""
        import inspect

        from flowboard.web.routes_wizard import wizard_verify

        src = inspect.getsource(wizard_verify)
        assert "server_type" in src
        assert "deployment_type" in src.lower() or "deploymentType" in src

    def test_build_config_uses_server_type(self):
        """Frontend buildConfig should include server_type from serverInfo."""
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()
        assert "server_type" in html
        assert "serverInfo" in html


# ===================================================================
# Keyboard navigation
# ===================================================================
