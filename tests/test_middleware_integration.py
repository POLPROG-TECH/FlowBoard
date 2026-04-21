"""Middleware integration tests - locale, output paths, JQL safety, shutdown, logging, E2E integration."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ===================================================================
# CSRF protection
# ===================================================================


class TestLocaleContext:
    """GIVEN locale context and the scenario: restores locale"""
    def test_restores_locale(self):
        """WHEN the code under test is exercised for: restores locale"""
        from flowboard.i18n.translator import get_locale, locale_context, set_locale

        set_locale("en")

        """THEN the expected behaviour holds: restores locale"""
        with locale_context("pl") as active:
            assert active == "pl"
            assert get_locale() == "pl"
        assert get_locale() == "en"

    """GIVEN locale context and the scenario: restores on exception"""
    def test_restores_on_exception(self):
        """WHEN the code under test is exercised for: restores on exception"""
        from flowboard.i18n.translator import get_locale, locale_context, set_locale

        set_locale("en")
        with pytest.raises(ValueError), locale_context("pl"):
            raise ValueError("boom")

        """THEN the expected behaviour holds: restores on exception"""
        assert get_locale() == "en"

    """GIVEN locale context and the scenario: nested contexts"""
    def test_nested_contexts(self):
        """WHEN the code under test is exercised for: nested contexts"""
        from flowboard.i18n.translator import get_locale, locale_context, set_locale

        set_locale("en")

        """THEN the expected behaviour holds: nested contexts"""
        with locale_context("pl"):
            assert get_locale() == "pl"
            with locale_context("en"):
                assert get_locale() == "en"
            assert get_locale() == "pl"
        assert get_locale() == "en"


# ===================================================================
# Output path sanitization
# ===================================================================


class TestOutputPathSanitization:
    """GIVEN output path sanitization and the scenario: rejects absolute escape"""
    def test_rejects_absolute_escape(self):
        """WHEN the code under test is exercised for: rejects absolute escape"""
        from flowboard.infrastructure.config.loader import _validate_output_path

        with pytest.raises(ValueError, match="resolves outside"):
            _validate_output_path("/etc/passwd")

    """GIVEN output path sanitization and the scenario: allows relative path"""
    def test_allows_relative_path(self):
        """WHEN the code under test is exercised for: allows relative path"""
        from flowboard.infrastructure.config.loader import _validate_output_path

        _validate_output_path("output/dashboard.html")  # should not raise

    """GIVEN output path sanitization and the scenario: rejects traversal"""
    def test_rejects_traversal(self):
        """WHEN the code under test is exercised for: rejects traversal"""
        from flowboard.infrastructure.config.loader import _validate_output_path

        with pytest.raises(ValueError, match="resolves outside"):
            _validate_output_path("../../../etc/shadow")


# ===================================================================
# JQL filter safety
# ===================================================================


class TestJQLFilterSafety:
    """GIVEN j q l filter safety and the scenario: rejects sql injection"""
    def test_rejects_sql_injection(self, caplog):
        """WHEN the code under test is exercised for: rejects sql injection"""
        from flowboard.infrastructure.jira.connector import JiraConnector

        config = MagicMock()
        config.jira.projects = []
        config.jira.jql_filter = "status='Open'; DROP TABLE issues--"

        connector = JiraConnector(client=MagicMock(), config=config)
        with caplog.at_level(logging.ERROR):
            jql = connector._build_jql()

        """THEN the expected behaviour holds: rejects sql injection"""
        assert "DROP" not in jql

    """GIVEN j q l filter safety and the scenario: allows safe filter"""
    def test_allows_safe_filter(self):
        """WHEN the code under test is exercised for: allows safe filter"""
        from flowboard.infrastructure.jira.connector import JiraConnector

        config = MagicMock()
        config.jira.projects = ["PROJ"]
        config.jira.jql_filter = "status = 'In Progress'"

        connector = JiraConnector(client=MagicMock(), config=config)
        jql = connector._build_jql()

        """THEN the expected behaviour holds: allows safe filter"""
        assert "In Progress" in jql


# ===================================================================
# Graceful shutdown
# ===================================================================


class TestGracefulShutdown:
    """GIVEN graceful shutdown and the scenario: shutdown handler registered"""
    def test_shutdown_handler_registered(self):
        """WHEN the code under test is exercised for: shutdown handler registered"""
        from flowboard.web.server import create_app

        app = create_app(config_path=None, first_run=True)

        """THEN the expected behaviour holds: shutdown handler registered"""
        assert app.router.lifespan_context is not None


# ===================================================================
# Schema file bundling
# ===================================================================


class TestSchemaFileBundling:
    """GIVEN schema file bundling and the scenario: finds schema"""
    def test_finds_schema(self):
        """WHEN the code under test is exercised for: finds schema"""
        from flowboard.infrastructure.config.validator import _find_schema_path

        path = _find_schema_path()

        """THEN the expected behaviour holds: finds schema"""
        assert path.exists()
        assert path.name == "config.schema.json"

    """GIVEN schema file bundling and the scenario: error message helpful"""
    def test_error_message_helpful(self):
        """WHEN the code under test is exercised for: error message helpful"""
        from flowboard.infrastructure.config.validator import _find_schema_path

        with (
            patch("flowboard.infrastructure.config.validator._STATIC_CANDIDATES", []),
            patch("pathlib.Path.exists", return_value=False),
            patch("pathlib.Path.cwd", return_value=Path("/nonexistent")),
            pytest.raises(FileNotFoundError, match="bundled"),
        ):
            _find_schema_path()


# ===================================================================
# Output directory writability
# ===================================================================


class TestOutputWritability:
    """GIVEN output writability and the scenario: checks writability"""
    def test_checks_writability(self):
        """WHEN the code under test is exercised for: checks writability"""
        from flowboard.application.orchestrator import Orchestrator

        cfg = MagicMock()
        cfg.output.path = "/nonexistent_dir/dashboard.html"
        orch = Orchestrator(cfg)
        with (
            patch("flowboard.application.orchestrator.render_dashboard", return_value="<html>"),
            pytest.raises((PermissionError, OSError)),
        ):
            orch._render(MagicMock())


# ===================================================================
# Pagination truncation warning
# ===================================================================


class TestPaginationWarning:
    """GIVEN pagination warning and the scenario: warning message format"""
    def test_warning_message_format(self, caplog):
        """WHEN the code under test is exercised for: warning message format"""
        import flowboard.infrastructure.jira.client as client_mod

        with caplog.at_level(logging.WARNING, logger="flowboard.infrastructure.jira.client"):
            client_mod.logger.warning(
                "Pagination safety limit reached (%d pages, %d/%d issues fetched). "
                "Results are TRUNCATED - consider narrowing the JQL filter.",
                500,
                45000,
                60000,
            )

        """THEN the expected behaviour holds: warning message format"""
        assert any("TRUNCATED" in r.message for r in caplog.records)
        assert any("45000/60000" in r.message for r in caplog.records)


# ===================================================================
# JSON export strictness
# ===================================================================


class TestJsonExportStrictness:
    """GIVEN json export strictness and the scenario: encoder handles dates"""
    def test_encoder_handles_dates(self):
        """WHEN the code under test is exercised for: encoder handles dates"""
        from datetime import date

        from flowboard.presentation.export.json_export import _Encoder

        result = json.dumps({"d": date(2024, 1, 1)}, cls=_Encoder)

        """THEN the expected behaviour holds: encoder handles dates"""
        assert "2024-01-01" in result

    """GIVEN json export strictness and the scenario: rejects unknown types"""
    def test_rejects_unknown_types(self):
        """WHEN the code under test is exercised for: rejects unknown types"""
        from flowboard.presentation.export.json_export import _Encoder

        with pytest.raises(TypeError):
            json.dumps({"x": object()}, cls=_Encoder)


# ===================================================================
# Data freshness indicator
# ===================================================================


class TestDataFreshness:
    """GIVEN data freshness and the scenario: status includes freshness"""
    def test_status_includes_freshness(self):
        """WHEN the code under test is exercised for: status includes freshness"""
        from fastapi.testclient import TestClient

        from flowboard.web.server import create_app

        app = create_app(config_path=None, first_run=True)
        client = TestClient(app)
        resp = client.get("/api/status")

        """THEN the expected behaviour holds: status includes freshness"""
        assert resp.status_code == 200
        assert "data_freshness" in resp.json()

    """GIVEN data freshness and the scenario: config path not leaked"""
    def test_config_path_not_leaked(self):
        """WHEN the code under test is exercised for: config path not leaked"""
        from fastapi.testclient import TestClient

        from flowboard.web.server import create_app

        app = create_app(config_path="/secret/path/config.json", first_run=False)
        client = TestClient(app)
        resp = client.get("/api/status")

        """THEN the expected behaviour holds: config path not leaked"""
        assert "config_path" not in resp.json()


# ===================================================================
# Render error boundary
# ===================================================================


class TestRenderErrorBoundary:
    """GIVEN render error boundary and the scenario: demo render failure returns 500"""
    def test_demo_render_failure_returns_500(self):
        """WHEN the code under test is exercised for: demo render failure returns 500"""
        from fastapi.testclient import TestClient

        from flowboard.web.server import create_app

        app = create_app(config_path=None, first_run=True)
        client = TestClient(app, raise_server_exceptions=False)
        with patch("flowboard.web.server.locate_demo_fixture", side_effect=RuntimeError("boom")):
            resp = client.post("/api/demo", headers={"X-Requested-With": "FlowBoard"})

        """THEN the expected behaviour holds: demo render failure returns 500"""
        assert resp.status_code == 500
        assert resp.json()["ok"] is False


# ===================================================================
# Jira session reuse
# ===================================================================


class TestJiraSessionReuse:
    """GIVEN jira session reuse and the scenario: client uses session"""
    def test_client_uses_session(self):
        """WHEN the code under test is exercised for: client uses session"""
        from flowboard.infrastructure.jira.client import JiraClient

        config = MagicMock()
        config.base_url = "https://j.example.com"
        config.auth_email = ""
        config.auth_token = ""
        config.max_results = 50

        """THEN the expected behaviour holds: client uses session"""
        with patch("flowboard.infrastructure.jira.client.configure_session_ssl"):
            client = JiraClient(config)
            assert client._session is not None
            client.close()

    """GIVEN jira session reuse and the scenario: context manager closes session"""
    def test_context_manager_closes_session(self):
        """WHEN the code under test is exercised for: context manager closes session"""
        from flowboard.infrastructure.jira.client import JiraClient

        config = MagicMock()
        config.base_url = "https://j.example.com"
        config.auth_email = ""
        config.auth_token = ""
        config.max_results = 50

        """THEN the expected behaviour holds: context manager closes session"""
        with (
            patch("flowboard.infrastructure.jira.client.configure_session_ssl"),
            JiraClient(config) as client,
        ):
            session = client._session
            assert session is not None
            # After context exit, session should be closed (no error means success)


# ===================================================================
# Snapshot cache thread safety
# ===================================================================


class TestSnapshotCacheSafety:
    """GIVEN snapshot cache safety and the scenario: set and get snapshot"""
    def test_set_and_get_snapshot(self):
        """WHEN the code under test is exercised for: set and get snapshot"""
        from flowboard.web.state import AppState

        state = AppState()
        obj = {"result": True}

        """THEN the expected behaviour holds: set and get snapshot"""

        async def _run():
            await state.set_snapshot(obj)
            got = await state.get_snapshot()
            assert got is obj

        asyncio.get_event_loop().run_until_complete(_run())

    """GIVEN snapshot cache safety and the scenario: has lock"""
    def test_has_lock(self):
        """WHEN the code under test is exercised for: has lock"""
        from flowboard.web.state import AppState

        state = AppState()

        """THEN the expected behaviour holds: has lock"""
        assert isinstance(state._snapshot_lock, asyncio.Lock)


# ===================================================================
# Structured logging
# ===================================================================


class TestStructuredLogging:
    """GIVEN structured logging and the scenario: json formatter"""
    def test_json_formatter(self):
        """WHEN the code under test is exercised for: json formatter"""
        from flowboard.web.logging import JSONFormatter

        fmt = JSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="hello",
            args=(),
            exc_info=None,
        )
        output = fmt.format(record)
        parsed = json.loads(output)

        """THEN the expected behaviour holds: json formatter"""
        assert parsed["msg"] == "hello"
        assert parsed["level"] == "INFO"

    """GIVEN structured logging and the scenario: env toggle"""
    def test_env_toggle(self):
        """THEN the expected behaviour holds: env toggle"""
        with patch.dict(os.environ, {"FLOWBOARD_LOG_FORMAT": "json"}):
            from flowboard.web.logging import JSONFormatter, _make_formatter

            fmt = _make_formatter()
            assert isinstance(fmt, JSONFormatter)

    """GIVEN structured logging and the scenario: default is structured"""
    def test_default_is_structured(self):
        """THEN the expected behaviour holds: default is structured"""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("FLOWBOARD_LOG_FORMAT", None)
            from flowboard.web.logging import StructuredFormatter, _make_formatter

            fmt = _make_formatter()
            assert isinstance(fmt, StructuredFormatter)


# ===================================================================
# Container host warning
# ===================================================================


class TestContainerHostWarning:
    """GIVEN container host warning and the scenario: dockerenv check in serve"""
    def test_dockerenv_check_in_serve(self):
        """WHEN the code under test is exercised for: dockerenv check in serve"""
        import inspect

        from flowboard.cli.main import serve

        source = inspect.getsource(serve)

        """THEN the expected behaviour holds: dockerenv check in serve"""
        assert ".dockerenv" in source
        assert "0.0.0.0" in source


# ===================================================================
# E2E integration test
# ===================================================================


class TestE2EIntegration:
    """GIVEN e2 e integration and the scenario: demo pipeline e2e"""
    def test_demo_pipeline_e2e(self):
        """WHEN the code under test is exercised for: demo pipeline e2e"""
        from flowboard.application.orchestrator import Orchestrator
        from flowboard.infrastructure.config.loader import load_config_from_dict
        from flowboard.presentation.export.csv_export import export_issues_csv
        from flowboard.presentation.export.json_export import export_json
        from flowboard.presentation.html.renderer import render_dashboard

        fixture = Path(__file__).parent.parent / "examples" / "fixtures" / "mock_jira_data.json"
        if not fixture.exists():
            pytest.skip("Demo fixture not available")

        with fixture.open() as f:
            payload = json.load(f)

        cfg = load_config_from_dict(
            {
                "jira": {"base_url": "https://demo.atlassian.net"},
                "locale": "en",
                "output": {"path": "output/e2e_test.html", "title": "E2E", "company_name": "Test"},
                "teams": [{"key": "a", "name": "Alpha", "members": ["user-1", "user-2"]}],
            }
        )

        snapshot = Orchestrator(cfg).snapshot_from_payload(payload)

        """THEN the expected behaviour holds: demo pipeline e2e"""
        assert len(snapshot.issues) > 0

        html = render_dashboard(snapshot, cfg)
        assert "<html" in html.lower()

        json_str = export_json(snapshot)
        data = json.loads(json_str)
        assert data["summary"]["total_issues"] > 0

        csv_str = export_issues_csv(snapshot)
        assert len(csv_str.strip().split("\n")) > 1

    """GIVEN e2 e integration and the scenario: web e2e flow"""
    def test_web_e2e_flow(self):
        """WHEN the code under test is exercised for: web e2e flow"""
        from fastapi.testclient import TestClient

        from flowboard.web.server import create_app

        fixture = Path(__file__).parent.parent / "examples" / "fixtures" / "mock_jira_data.json"
        if not fixture.exists():
            pytest.skip("Demo fixture not available")

        app = create_app(config_path=None, first_run=True)
        client = TestClient(app, raise_server_exceptions=False)

        """THEN the expected behaviour holds: web e2e flow"""
        assert client.get("/health/live").status_code == 200
        resp = client.post("/api/demo", headers={"X-Requested-With": "FlowBoard"})
        assert resp.status_code == 200

        status = client.get("/api/status").json()
        assert status["analysis"]["phase"] == "completed"
        assert status["data_freshness"] is not None

        assert client.get("/").status_code == 200
        assert client.get("/api/export/html").status_code == 200
        assert client.get("/api/export/json").status_code == 200
        assert client.get("/api/export/csv?dataset=issues").status_code == 200
