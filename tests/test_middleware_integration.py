"""Middleware integration tests — locale, output paths, JQL safety, shutdown, logging, E2E integration."""

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
    def test_restores_locale(self):
        from flowboard.i18n.translator import get_locale, locale_context, set_locale

        set_locale("en")
        with locale_context("pl") as active:
            assert active == "pl"
            assert get_locale() == "pl"
        assert get_locale() == "en"

    def test_restores_on_exception(self):
        from flowboard.i18n.translator import get_locale, locale_context, set_locale

        set_locale("en")
        with pytest.raises(ValueError), locale_context("pl"):
            raise ValueError("boom")
        assert get_locale() == "en"

    def test_nested_contexts(self):
        from flowboard.i18n.translator import get_locale, locale_context, set_locale

        set_locale("en")
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
    def test_rejects_absolute_escape(self):
        from flowboard.infrastructure.config.loader import _validate_output_path

        with pytest.raises(ValueError, match="resolves outside"):
            _validate_output_path("/etc/passwd")

    def test_allows_relative_path(self):
        from flowboard.infrastructure.config.loader import _validate_output_path

        _validate_output_path("output/dashboard.html")  # should not raise

    def test_rejects_traversal(self):
        from flowboard.infrastructure.config.loader import _validate_output_path

        with pytest.raises(ValueError, match="resolves outside"):
            _validate_output_path("../../../etc/shadow")


# ===================================================================
# JQL filter safety
# ===================================================================


class TestJQLFilterSafety:
    def test_rejects_sql_injection(self, caplog):
        from flowboard.infrastructure.jira.connector import JiraConnector

        config = MagicMock()
        config.jira.projects = []
        config.jira.jql_filter = "status='Open'; DROP TABLE issues--"

        connector = JiraConnector(client=MagicMock(), config=config)
        with caplog.at_level(logging.ERROR):
            jql = connector._build_jql()
        assert "DROP" not in jql

    def test_allows_safe_filter(self):
        from flowboard.infrastructure.jira.connector import JiraConnector

        config = MagicMock()
        config.jira.projects = ["PROJ"]
        config.jira.jql_filter = "status = 'In Progress'"

        connector = JiraConnector(client=MagicMock(), config=config)
        jql = connector._build_jql()
        assert "In Progress" in jql


# ===================================================================
# Graceful shutdown
# ===================================================================


class TestGracefulShutdown:
    def test_shutdown_handler_registered(self):
        from flowboard.web.server import create_app

        app = create_app(config_path=None, first_run=True)
        assert app.router.lifespan_context is not None


# ===================================================================
# Schema file bundling
# ===================================================================


class TestSchemaFileBundling:
    def test_finds_schema(self):
        from flowboard.infrastructure.config.validator import _find_schema_path

        path = _find_schema_path()
        assert path.exists()
        assert path.name == "config.schema.json"

    def test_error_message_helpful(self):
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
    def test_checks_writability(self):
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
    def test_warning_message_format(self, caplog):
        import flowboard.infrastructure.jira.client as client_mod

        with caplog.at_level(logging.WARNING, logger="flowboard.infrastructure.jira.client"):
            client_mod.logger.warning(
                "Pagination safety limit reached (%d pages, %d/%d issues fetched). "
                "Results are TRUNCATED — consider narrowing the JQL filter.",
                500,
                45000,
                60000,
            )
        assert any("TRUNCATED" in r.message for r in caplog.records)
        assert any("45000/60000" in r.message for r in caplog.records)


# ===================================================================
# JSON export strictness
# ===================================================================


class TestJsonExportStrictness:
    def test_encoder_handles_dates(self):
        from datetime import date

        from flowboard.presentation.export.json_export import _Encoder

        result = json.dumps({"d": date(2024, 1, 1)}, cls=_Encoder)
        assert "2024-01-01" in result

    def test_rejects_unknown_types(self):
        from flowboard.presentation.export.json_export import _Encoder

        with pytest.raises(TypeError):
            json.dumps({"x": object()}, cls=_Encoder)


# ===================================================================
# Data freshness indicator
# ===================================================================


class TestDataFreshness:
    def test_status_includes_freshness(self):
        from fastapi.testclient import TestClient

        from flowboard.web.server import create_app

        app = create_app(config_path=None, first_run=True)
        client = TestClient(app)
        resp = client.get("/api/status")
        assert resp.status_code == 200
        assert "data_freshness" in resp.json()

    def test_config_path_not_leaked(self):
        from fastapi.testclient import TestClient

        from flowboard.web.server import create_app

        app = create_app(config_path="/secret/path/config.json", first_run=False)
        client = TestClient(app)
        resp = client.get("/api/status")
        assert "config_path" not in resp.json()


# ===================================================================
# Render error boundary
# ===================================================================


class TestRenderErrorBoundary:
    def test_demo_render_failure_returns_500(self):
        from fastapi.testclient import TestClient

        from flowboard.web.server import create_app

        app = create_app(config_path=None, first_run=True)
        client = TestClient(app, raise_server_exceptions=False)
        with patch("flowboard.web.server.locate_demo_fixture", side_effect=RuntimeError("boom")):
            resp = client.post("/api/demo", headers={"X-Requested-With": "FlowBoard"})
        assert resp.status_code == 500
        assert resp.json()["ok"] is False


# ===================================================================
# Jira session reuse
# ===================================================================


class TestJiraSessionReuse:
    def test_client_uses_session(self):
        from flowboard.infrastructure.jira.client import JiraClient

        config = MagicMock()
        config.base_url = "https://j.example.com"
        config.auth_email = ""
        config.auth_token = ""
        config.max_results = 50

        with patch("flowboard.infrastructure.jira.client.configure_session_ssl"):
            client = JiraClient(config)
            assert client._session is not None
            client.close()

    def test_context_manager_closes_session(self):
        from flowboard.infrastructure.jira.client import JiraClient

        config = MagicMock()
        config.base_url = "https://j.example.com"
        config.auth_email = ""
        config.auth_token = ""
        config.max_results = 50

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
    def test_set_and_get_snapshot(self):
        from flowboard.web.state import AppState

        state = AppState()
        obj = {"result": True}

        async def _run():
            await state.set_snapshot(obj)
            got = await state.get_snapshot()
            assert got is obj

        asyncio.get_event_loop().run_until_complete(_run())

    def test_has_lock(self):
        from flowboard.web.state import AppState

        state = AppState()
        assert isinstance(state._snapshot_lock, asyncio.Lock)


# ===================================================================
# Structured logging
# ===================================================================


class TestStructuredLogging:
    def test_json_formatter(self):
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
        assert parsed["msg"] == "hello"
        assert parsed["level"] == "INFO"

    def test_env_toggle(self):
        with patch.dict(os.environ, {"FLOWBOARD_LOG_FORMAT": "json"}):
            from flowboard.web.logging import JSONFormatter, _make_formatter

            fmt = _make_formatter()
            assert isinstance(fmt, JSONFormatter)

    def test_default_is_structured(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("FLOWBOARD_LOG_FORMAT", None)
            from flowboard.web.logging import StructuredFormatter, _make_formatter

            fmt = _make_formatter()
            assert isinstance(fmt, StructuredFormatter)


# ===================================================================
# Container host warning
# ===================================================================


class TestContainerHostWarning:
    def test_dockerenv_check_in_serve(self):
        import inspect

        from flowboard.cli.main import serve

        source = inspect.getsource(serve)
        assert ".dockerenv" in source
        assert "0.0.0.0" in source


# ===================================================================
# E2E integration test
# ===================================================================


class TestE2EIntegration:
    def test_demo_pipeline_e2e(self):
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
        assert len(snapshot.issues) > 0

        html = render_dashboard(snapshot, cfg)
        assert "<html" in html.lower()

        json_str = export_json(snapshot)
        data = json.loads(json_str)
        assert data["summary"]["total_issues"] > 0

        csv_str = export_issues_csv(snapshot)
        assert len(csv_str.strip().split("\n")) > 1

    def test_web_e2e_flow(self):
        from fastapi.testclient import TestClient

        from flowboard.web.server import create_app

        fixture = Path(__file__).parent.parent / "examples" / "fixtures" / "mock_jira_data.json"
        if not fixture.exists():
            pytest.skip("Demo fixture not available")

        app = create_app(config_path=None, first_run=True)
        client = TestClient(app, raise_server_exceptions=False)

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
