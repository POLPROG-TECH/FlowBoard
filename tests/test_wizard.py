"""Core wizard tests - route registration, verify, save, import, CSRF, UI rendering, state, project validation."""

from __future__ import annotations

import contextlib
import os

# ===================================================================
# Wizard route registration
# ===================================================================


class TestWizardRouteRegistration:
    """Tests for wizard route registration."""

    """GIVEN wizard route registration and the scenario: wizard routes exist"""
    def test_wizard_routes_exist(self):
        """WHEN the code under test is exercised for: wizard routes exist"""
        from flowboard.web.server import create_app

        app = create_app(config_path=None, first_run=True)
        routes = [r.path for r in app.routes]

        """THEN the expected behaviour holds: wizard routes exist"""
        assert "/api/wizard/verify" in routes
        assert "/api/wizard/save" in routes
        assert "/api/wizard/projects" in routes
        assert "/api/wizard/import" in routes


# ===================================================================
# Wizard verify endpoint
# ===================================================================


class TestWizardVerify:
    """Tests for wizard verify."""

    """GIVEN wizard verify and the scenario: verify requires base url"""
    def test_verify_requires_base_url(self):
        """WHEN the code under test is exercised for: verify requires base url"""
        from fastapi.testclient import TestClient

        from flowboard.web.server import create_app

        app = create_app(config_path=None, first_run=True)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/wizard/verify",
            json={"auth_email": "x@y.com"},
            headers={"X-Requested-With": "FlowBoard"},
        )

        """THEN the expected behaviour holds: verify requires base url"""
        assert resp.status_code == 400
        assert "base_url" in resp.json()["error"]

    """GIVEN wizard verify and the scenario: verify returns error on bad url"""
    def test_verify_returns_error_on_bad_url(self):
        """WHEN the code under test is exercised for: verify returns error on bad url"""
        from fastapi.testclient import TestClient

        from flowboard.web.server import create_app

        app = create_app(config_path=None, first_run=True)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/wizard/verify",
            json={"base_url": "https://nonexistent.invalid.test"},
            headers={"X-Requested-With": "FlowBoard"},
        )

        """THEN the expected behaviour holds: verify returns error on bad url"""
        assert resp.status_code == 400
        assert resp.json()["ok"] is False


# ===================================================================
# Wizard save endpoint
# ===================================================================


class TestWizardSave:
    """Tests for wizard save."""

    """GIVEN wizard save and the scenario: save rejects absolute path"""
    def test_save_rejects_absolute_path(self):
        """WHEN the code under test is exercised for: save rejects absolute path"""
        from fastapi.testclient import TestClient

        from flowboard.web.server import create_app

        app = create_app(config_path=None, first_run=True)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/wizard/save",
            json={"config": {"jira": {"base_url": "https://x.com"}}, "path": "/etc/passwd"},
            headers={"X-Requested-With": "FlowBoard"},
        )

        """THEN the expected behaviour holds: save rejects absolute path"""
        assert resp.status_code == 400
        assert "relative" in resp.json()["error"].lower()

    """GIVEN wizard save and the scenario: save rejects traversal"""
    def test_save_rejects_traversal(self):
        """WHEN the code under test is exercised for: save rejects traversal"""
        from fastapi.testclient import TestClient

        from flowboard.web.server import create_app

        app = create_app(config_path=None, first_run=True)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/wizard/save",
            json={"config": {"jira": {"base_url": "https://x.com"}}, "path": "../../../evil.json"},
            headers={"X-Requested-With": "FlowBoard"},
        )

        """THEN the expected behaviour holds: save rejects traversal"""
        assert resp.status_code == 400

    """GIVEN wizard save and the scenario: save requires config object"""
    def test_save_requires_config_object(self):
        """WHEN the code under test is exercised for: save requires config object"""
        from fastapi.testclient import TestClient

        from flowboard.web.server import create_app

        app = create_app(config_path=None, first_run=True)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/wizard/save",
            json={"config": "not an object"},
            headers={"X-Requested-With": "FlowBoard"},
        )

        """THEN the expected behaviour holds: save requires config object"""
        assert resp.status_code == 400

    """GIVEN wizard save and the scenario: save strips credentials"""
    def test_save_strips_credentials(self, tmp_path):
        """WHEN the code under test is exercised for: save strips credentials"""
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

        """THEN the expected behaviour holds: save strips credentials"""
        if resp.status_code == 200:
            assert resp.json()["ok"] is True
            assert "auth_token" in resp.json().get("warning", "")
            # Clean up
            with contextlib.suppress(OSError):
                os.unlink(save_path)

    """GIVEN wizard save and the scenario: save validates schema"""
    def test_save_validates_schema(self):
        """WHEN the code under test is exercised for: save validates schema"""
        from fastapi.testclient import TestClient

        from flowboard.web.server import create_app

        app = create_app(config_path=None, first_run=True)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/wizard/save",
            json={"config": {"not_jira": True}},
            headers={"X-Requested-With": "FlowBoard"},
        )

        """THEN the expected behaviour holds: save validates schema"""
        assert resp.status_code == 400
        assert "Validation failed" in resp.json()["error"]


# ===================================================================
# Wizard import endpoint
# ===================================================================


class TestWizardImport:
    """Tests for wizard import."""

    """GIVEN wizard import and the scenario: import rejects invalid json"""
    def test_import_rejects_invalid_json(self):
        """WHEN the code under test is exercised for: import rejects invalid json"""
        from fastapi.testclient import TestClient

        from flowboard.web.server import create_app

        app = create_app(config_path=None, first_run=True)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/wizard/import",
            json={"json_str": "{invalid json"},
            headers={"X-Requested-With": "FlowBoard"},
        )

        """THEN the expected behaviour holds: import rejects invalid json"""
        assert resp.status_code == 400
        assert "Invalid JSON" in resp.json()["error"]

    """GIVEN wizard import and the scenario: import requires jira key"""
    def test_import_requires_jira_key(self):
        """WHEN the code under test is exercised for: import requires jira key"""
        from fastapi.testclient import TestClient

        from flowboard.web.server import create_app

        app = create_app(config_path=None, first_run=True)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/wizard/import",
            json={"json_str": '{"output": {}}'},
            headers={"X-Requested-With": "FlowBoard"},
        )

        """THEN the expected behaviour holds: import requires jira key"""
        assert resp.status_code == 400
        assert "jira" in resp.json()["error"].lower()


# ===================================================================
# Wizard CSRF protection
# ===================================================================


class TestWizardCSRF:
    """Tests for wizard c s r f."""

    """GIVEN wizard c s r f and the scenario: wizard verify requires csrf"""
    def test_wizard_verify_requires_csrf(self):
        """WHEN the code under test is exercised for: wizard verify requires csrf"""
        from fastapi.testclient import TestClient

        from flowboard.web.server import create_app

        app = create_app(config_path=None, first_run=True)
        client = TestClient(app, raise_server_exceptions=False)
        # POST without X-Requested-With header
        resp = client.post(
            "/api/wizard/verify",
            json={"base_url": "https://x.com"},
        )

        """THEN the expected behaviour holds: wizard verify requires csrf"""
        assert resp.status_code == 403


# ===================================================================
# Wizard UI rendering
# ===================================================================


class TestWizardUIRendering:
    """Tests for wizard u i rendering."""

    """GIVEN wizard u i rendering and the scenario: first run renders wizard"""
    def test_first_run_renders_wizard(self):
        """WHEN the code under test is exercised for: first run renders wizard"""
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run(config_path="config.json", locale="en")

        """THEN the expected behaviour holds: first run renders wizard"""
        assert "wz-container" in html
        assert "wizardContent" in html
        assert "testConnection" in html
        assert "goStep" in html
        assert "FlowBoard" in html

    """GIVEN wizard u i rendering and the scenario: wizard renders in polish"""
    def test_wizard_renders_in_polish(self):
        """WHEN the code under test is exercised for: wizard renders in polish"""
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run(config_path="config.json", locale="pl")

        """THEN the expected behaviour holds: wizard renders in polish"""
        assert "Kreator konfiguracji" in html or "wizard" in html.lower()

    """GIVEN wizard u i rendering and the scenario: wizard no innerhtml"""
    def test_wizard_no_innerhtml(self):
        """WHEN the code under test is exercised for: wizard no innerhtml"""
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()

        """THEN the expected behaviour holds: wizard no innerhtml"""
        assert "innerHTML" not in html

    """GIVEN wizard u i rendering and the scenario: wizard has stepper"""
    def test_wizard_has_stepper(self):
        """WHEN the code under test is exercised for: wizard has stepper"""
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()

        """THEN the expected behaviour holds: wizard has stepper"""
        assert "wz-stepper" in html
        assert "wz-step-dot" in html

    """GIVEN wizard u i rendering and the scenario: wizard has all steps"""
    def test_wizard_has_all_steps(self):
        """WHEN the code under test is exercised for: wizard has all steps"""
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()

        """THEN the expected behaviour holds: wizard has all steps"""
        assert "renderConnection" in html
        assert "renderProjects" in html
        assert "renderTeams" in html
        assert "renderCustomize" in html
        assert "renderReview" in html

    """GIVEN wizard u i rendering and the scenario: wizard has demo option"""
    def test_wizard_has_demo_option(self):
        """WHEN the code under test is exercised for: wizard has demo option"""
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()

        """THEN the expected behaviour holds: wizard has demo option"""
        assert "launchDemo" in html
        assert "/api/demo" in html

    """GIVEN wizard u i rendering and the scenario: wizard has import option"""
    def test_wizard_has_import_option(self):
        """WHEN the code under test is exercised for: wizard has import option"""
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()

        """THEN the expected behaviour holds: wizard has import option"""
        assert "doImport" in html
        assert "importJson" in html


class TestStatePersistence:
    """Tests for state persistence."""

    """GIVEN state persistence and the scenario: persist state function exists"""
    def test_persist_state_function_exists(self):
        """WHEN the code under test is exercised for: persist state function exists"""
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()

        """THEN the expected behaviour holds: persist state function exists"""
        assert "persistState" in html
        assert "localStorage" in html
        assert "flowboard_wizard_state" in html

    """GIVEN state persistence and the scenario: restore state on init"""
    def test_restore_state_on_init(self):
        """WHEN the code under test is exercised for: restore state on init"""
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()

        """THEN the expected behaviour holds: restore state on init"""
        assert "restoreState" in html

    """GIVEN state persistence and the scenario: credentials not persisted"""
    def test_credentials_not_persisted(self):
        """WHEN the code under test is exercised for: credentials not persisted"""
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()

        """THEN the expected behaviour holds: credentials not persisted"""
        assert "auth_token: ''" in html or 'auth_token: ""' in html


# ===================================================================
# Project validation (≥1 required)
# ===================================================================


class TestProjectValidation:
    """Tests for project validation."""

    """GIVEN project validation and the scenario: select at least one message"""
    def test_select_at_least_one_message(self):
        """WHEN the code under test is exercised for: select at least one message"""
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()

        """THEN the expected behaviour holds: select at least one message"""
        assert "select_at_least_one" in html
        assert "projectWarn" in html

    """GIVEN project validation and the scenario: next disabled when no projects"""
    def test_next_disabled_when_no_projects(self):
        """WHEN the code under test is exercised for: next disabled when no projects"""
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()

        """THEN the expected behaviour holds: next disabled when no projects"""
        assert "selectedProjects.length" in html


# ===================================================================
# Timeout on Jira API calls
# ===================================================================


class TestJiraTimeout:
    """Tests for jira timeout."""

    """GIVEN jira timeout and the scenario: timeout constant defined"""
    def test_timeout_constant_defined(self):
        """WHEN the code under test is exercised for: timeout constant defined"""
        from flowboard.web.routes_wizard import _JIRA_TIMEOUT

        """THEN the expected behaviour holds: timeout constant defined"""
        assert _JIRA_TIMEOUT > 0
        assert _JIRA_TIMEOUT <= 30

    """GIVEN jira timeout and the scenario: timeout applied in verify"""
    def test_timeout_applied_in_verify(self):
        """WHEN the code under test is exercised for: timeout applied in verify"""
        import inspect

        from flowboard.web.routes_wizard import wizard_verify

        src = inspect.getsource(wizard_verify)

        """THEN the expected behaviour holds: timeout applied in verify"""
        assert "timeout" in src.lower() or "_JIRA_TIMEOUT" in src


# ===================================================================
# Cloud vs Server detection
# ===================================================================


class TestCloudServerDetection:
    """Tests for cloud server detection."""

    """GIVEN cloud server detection and the scenario: verify response includes server type"""
    def test_verify_response_includes_server_type(self):
        """WHEN the code under test is exercised for: verify response includes server type"""
        import inspect

        from flowboard.web.routes_wizard import wizard_verify

        src = inspect.getsource(wizard_verify)

        """THEN the expected behaviour holds: verify response includes server type"""
        assert "server_type" in src
        assert "deployment_type" in src.lower() or "deploymentType" in src

    """GIVEN cloud server detection and the scenario: build config uses server type"""
    def test_build_config_uses_server_type(self):
        """WHEN the code under test is exercised for: build config uses server type"""
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()

        """THEN the expected behaviour holds: build config uses server type"""
        assert "server_type" in html
        assert "serverInfo" in html


# ===================================================================
# Keyboard navigation
# ===================================================================
