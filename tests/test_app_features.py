"""Application feature tests - Docker, config reload, thresholds, OpenAPI, env vars, webhooks, data freshness."""

from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

_CSRF = {"X-Requested-With": "FlowBoard"}


# ===========================================================================
# Helpers
# ===========================================================================

_TEMPLATES_DIR = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "flowboard"
    / "presentation"
    / "html"
    / "templates"
)
_REPO_ROOT = Path(__file__).resolve().parent.parent


def _read_template(name: str) -> str:
    return (_TEMPLATES_DIR / name).read_text(encoding="utf-8")


# ===========================================================================
# Dockerfile
# ===========================================================================


class TestDockerfile:
    """Tests for dockerfile."""

    """GIVEN dockerfile and the scenario: dockerfile exists"""
    def test_dockerfile_exists(self):
        """THEN the expected behaviour holds: dockerfile exists"""
        assert (_REPO_ROOT / "Dockerfile").exists()

    """GIVEN dockerfile and the scenario: multi stage build"""
    def test_multi_stage_build(self):
        """WHEN the code under test is exercised for: multi stage build"""
        content = (_REPO_ROOT / "Dockerfile").read_text()

        """THEN the expected behaviour holds: multi stage build"""
        assert "AS builder" in content or "as builder" in content

    """GIVEN dockerfile and the scenario: non root user"""
    def test_non_root_user(self):
        """WHEN the code under test is exercised for: non root user"""
        content = (_REPO_ROOT / "Dockerfile").read_text()

        """THEN the expected behaviour holds: non root user"""
        assert "USER" in content

    """GIVEN dockerfile and the scenario: healthcheck"""
    def test_healthcheck(self):
        """WHEN the code under test is exercised for: healthcheck"""
        content = (_REPO_ROOT / "Dockerfile").read_text()

        """THEN the expected behaviour holds: healthcheck"""
        assert "HEALTHCHECK" in content

    """GIVEN dockerfile and the scenario: docker compose exists"""
    def test_docker_compose_exists(self):
        """THEN the expected behaviour holds: docker compose exists"""
        assert (_REPO_ROOT / "docker-compose.yml").exists()

    """GIVEN dockerfile and the scenario: docker compose valid yaml"""
    def test_docker_compose_valid_yaml(self):
        """WHEN the code under test is exercised for: docker compose valid yaml"""
        import yaml

        content = (_REPO_ROOT / "docker-compose.yml").read_text()
        data = yaml.safe_load(content)

        """THEN the expected behaviour holds: docker compose valid yaml"""
        assert "services" in data
        assert "flowboard" in data["services"]


# ===========================================================================
# Hot Config Reload
# ===========================================================================


class TestHotConfigReload:
    """Tests for hot config reload."""

    """GIVEN hot config reload and the scenario: reload no config"""
    def test_reload_no_config(self):
        """WHEN the code under test is exercised for: reload no config"""
        import asyncio

        from httpx import ASGITransport, AsyncClient

        from flowboard.web.server import create_app

        app = create_app()
        app.state._flowboard_state.config_path = None

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                r = await ac.post("/api/config/reload", headers=_CSRF)
                return r

        resp = asyncio.get_event_loop().run_until_complete(_run())

        """THEN the expected behaviour holds: reload no config"""
        assert resp.status_code == 400
        assert "No configuration" in resp.json()["error"]


# ===========================================================================
# Per-team Thresholds
# ===========================================================================


class TestPerTeamThresholds:
    """Tests for per team thresholds."""

    """GIVEN per team thresholds and the scenario: team thresholds parsed"""
    def test_team_thresholds_parsed(self):
        """WHEN the code under test is exercised for: team thresholds parsed"""
        from flowboard.infrastructure.config.loader import _build_teams

        raw = {
            "teams": [
                {
                    "key": "alpha",
                    "name": "Alpha",
                    "members": ["alice"],
                    "thresholds": {"overload_points": 30},
                },
                {"key": "beta", "name": "Beta", "members": ["bob"]},
            ]
        }
        teams = _build_teams(raw)

        """THEN the expected behaviour holds: team thresholds parsed"""
        assert teams[0].thresholds == {"overload_points": 30}
        assert teams[1].thresholds is None

    """GIVEN per team thresholds and the scenario: empty thresholds becomes none"""
    def test_empty_thresholds_becomes_none(self):
        """WHEN the code under test is exercised for: empty thresholds becomes none"""
        from flowboard.infrastructure.config.loader import _build_teams

        raw = {"teams": [{"key": "t", "name": "T", "members": [], "thresholds": {}}]}
        teams = _build_teams(raw)

        """THEN the expected behaviour holds: empty thresholds becomes none"""
        assert teams[0].thresholds is None

    """GIVEN per team thresholds and the scenario: schema allows team thresholds"""
    def test_schema_allows_team_thresholds(self):
        """WHEN the code under test is exercised for: schema allows team thresholds"""
        schema = json.loads((_REPO_ROOT / "config.schema.json").read_text())
        team_props = schema["properties"]["teams"]["items"]["properties"]

        """THEN the expected behaviour holds: schema allows team thresholds"""
        assert "thresholds" in team_props


# ===========================================================================
# OpenAPI /docs
# ===========================================================================


class TestOpenAPIDocs:
    """Tests for open a p i docs."""

    """GIVEN open a p i docs and the scenario: docs endpoint"""
    def test_docs_endpoint(self):
        """WHEN the code under test is exercised for: docs endpoint"""
        import asyncio

        from httpx import ASGITransport, AsyncClient

        from flowboard.web.server import create_app

        app = create_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                r = await ac.get("/docs")
                return r

        resp = asyncio.get_event_loop().run_until_complete(_run())

        """THEN the expected behaviour holds: docs endpoint"""
        assert resp.status_code == 200
        assert "swagger" in resp.text.lower() or "openapi" in resp.text.lower()


# ===========================================================================
# Environment Variable Expansion
# ===========================================================================


class TestEnvVarExpansion:
    """Tests for env var expansion."""

    """GIVEN env var expansion and the scenario: expand simple string"""
    def test_expand_simple_string(self):
        """WHEN the code under test is exercised for: expand simple string"""
        from flowboard.infrastructure.config.loader import _expand_env_vars

        """THEN the expected behaviour holds: expand simple string"""
        with patch.dict(os.environ, {"MY_TOKEN": "secret123"}):
            result = _expand_env_vars("Bearer ${MY_TOKEN}", _key="auth_token")
            assert result == "Bearer secret123"

    """GIVEN env var expansion and the scenario: expand nested dict"""
    def test_expand_nested_dict(self):
        """WHEN the code under test is exercised for: expand nested dict"""
        from flowboard.infrastructure.config.loader import _expand_env_vars

        """THEN the expected behaviour holds: expand nested dict"""
        with patch.dict(os.environ, {"DB_HOST": "localhost"}):
            result = _expand_env_vars({"base_url": "${DB_HOST}", "port": 5432})
            assert result == {"base_url": "localhost", "port": 5432}

    """GIVEN env var expansion and the scenario: expand list"""
    def test_expand_list(self):
        """WHEN the code under test is exercised for: expand list"""
        from flowboard.infrastructure.config.loader import _expand_env_vars

        """THEN the expected behaviour holds: expand list"""
        with patch.dict(os.environ, {"A": "1", "B": "2"}):
            result = _expand_env_vars(["${A}", "${B}", "plain"], _key="path")
            assert result == ["1", "2", "plain"]

    """GIVEN env var expansion and the scenario: missing env var preserved"""
    def test_missing_env_var_preserved(self):
        """WHEN the code under test is exercised for: missing env var preserved"""
        from flowboard.infrastructure.config.loader import _expand_env_vars

        result = _expand_env_vars("${NONEXISTENT_VAR_12345}", _key="base_url")

        """THEN the expected behaviour holds: missing env var preserved"""
        assert result == "${NONEXISTENT_VAR_12345}"

    """GIVEN env var expansion and the scenario: non string passthrough"""
    def test_non_string_passthrough(self):
        """WHEN the code under test is exercised for: non string passthrough"""
        from flowboard.infrastructure.config.loader import _expand_env_vars

        """THEN the expected behaviour holds: non string passthrough"""
        assert _expand_env_vars(42) == 42
        assert _expand_env_vars(None) is None
        assert _expand_env_vars(True) is True

    """GIVEN env var expansion and the scenario: unsafe key not expanded"""
    def test_unsafe_key_not_expanded(self):
        """WHEN the code under test is exercised for: unsafe key not expanded"""
        from flowboard.infrastructure.config.loader import _expand_env_vars

        """THEN the expected behaviour holds: unsafe key not expanded"""
        with patch.dict(os.environ, {"SECRET": "leaked"}):
            result = _expand_env_vars("${SECRET}", _key="arbitrary_field")
            assert result == "${SECRET}"


# ===========================================================================
# Correlation ID Middleware
# ===========================================================================


class TestCorrelationIdMiddleware:
    """Tests for correlation id middleware."""

    """GIVEN correlation id middleware and the scenario: generates request id"""
    def test_generates_request_id(self):
        """WHEN the code under test is exercised for: generates request id"""
        import asyncio

        from httpx import ASGITransport, AsyncClient

        from flowboard.web.server import create_app

        app = create_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                r = await ac.get("/api/health")
                return r

        resp = asyncio.get_event_loop().run_until_complete(_run())

        """THEN the expected behaviour holds: generates request id"""
        assert "x-request-id" in resp.headers
        assert len(resp.headers["x-request-id"]) >= 8

    """GIVEN correlation id middleware and the scenario: propagates provided id"""
    def test_propagates_provided_id(self):
        """WHEN the code under test is exercised for: propagates provided id"""
        import asyncio

        from httpx import ASGITransport, AsyncClient

        from flowboard.web.server import create_app

        app = create_app()
        custom_id = "test-trace-id-123"

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                r = await ac.get("/api/health", headers={"X-Request-ID": custom_id})
                return r

        resp = asyncio.get_event_loop().run_until_complete(_run())

        """THEN the expected behaviour holds: propagates provided id"""
        assert resp.headers["x-request-id"] == custom_id


# ===========================================================================
# Duplicate Sprint Detection
# ===========================================================================


class TestDuplicateSprintDetection:
    """Tests for duplicate sprint detection."""

    """GIVEN duplicate sprint detection and the scenario: no duplicates"""
    def test_no_duplicates(self):
        """WHEN the code under test is exercised for: no duplicates"""
        from flowboard.application.data_quality import check_duplicate_sprints

        sprints = [
            {"name": "Sprint 1", "originBoardId": 1},
            {"name": "Sprint 2", "originBoardId": 1},
        ]
        warnings = check_duplicate_sprints(sprints)

        """THEN the expected behaviour holds: no duplicates"""
        assert warnings == []

    """GIVEN duplicate sprint detection and the scenario: detects duplicates"""
    def test_detects_duplicates(self):
        """WHEN the code under test is exercised for: detects duplicates"""
        from flowboard.application.data_quality import check_duplicate_sprints

        sprints = [
            {"name": "Sprint 1", "originBoardId": 1},
            {"name": "Sprint 1", "originBoardId": 2},
        ]
        warnings = check_duplicate_sprints(sprints)

        """THEN the expected behaviour holds: detects duplicates"""
        assert len(warnings) == 1
        assert "Sprint 1" in warnings[0]
        assert "2 boards" in warnings[0]

    """GIVEN duplicate sprint detection and the scenario: empty sprints"""
    def test_empty_sprints(self):
        """WHEN the code under test is exercised for: empty sprints"""
        from flowboard.application.data_quality import check_duplicate_sprints

        """THEN the expected behaviour holds: empty sprints"""
        assert check_duplicate_sprints([]) == []


# ===========================================================================
# Team Member Presence Check
# ===========================================================================


class TestTeamMemberPresence:
    """Tests for team member presence."""

    """GIVEN team member presence and the scenario: all members found"""
    def test_all_members_found(self):
        """WHEN the code under test is exercised for: all members found"""
        from flowboard.application.data_quality import check_team_member_presence

        config = MagicMock()
        config.teams = [MagicMock(name="Alpha", members=["alice"])]
        config.teams[0].name = "Alpha"
        config.teams[0].members = ["alice"]

        issues = [MagicMock(assignee="alice"), MagicMock(assignee="bob")]
        warnings = check_team_member_presence(config, issues)

        """THEN the expected behaviour holds: all members found"""
        assert warnings == []

    """GIVEN team member presence and the scenario: missing member"""
    def test_missing_member(self):
        """WHEN the code under test is exercised for: missing member"""
        from flowboard.application.data_quality import check_team_member_presence

        config = MagicMock()
        config.teams = [MagicMock()]
        config.teams[0].name = "Alpha"
        config.teams[0].members = ["alice", "charlie"]

        issues = [MagicMock(assignee="alice"), MagicMock(assignee="bob")]
        warnings = check_team_member_presence(config, issues)

        """THEN the expected behaviour holds: missing member"""
        assert len(warnings) == 1
        assert "charlie" in warnings[0]

    """GIVEN team member presence and the scenario: no teams"""
    def test_no_teams(self):
        """WHEN the code under test is exercised for: no teams"""
        from flowboard.application.data_quality import check_team_member_presence

        config = MagicMock()
        config.teams = []
        warnings = check_team_member_presence(config, [])

        """THEN the expected behaviour holds: no teams"""
        assert warnings == []


# ===========================================================================
# Data Freshness Check
# ===========================================================================


class TestDataFreshness:
    """Tests for data freshness."""

    """GIVEN data freshness and the scenario: fresh data"""
    def test_fresh_data(self):
        """WHEN the code under test is exercised for: fresh data"""
        from flowboard.application.data_quality import check_data_freshness

        issue = MagicMock()
        issue.updated = date.today()
        warnings = check_data_freshness([issue])

        """THEN the expected behaviour holds: fresh data"""
        assert warnings == []

    """GIVEN data freshness and the scenario: stale data"""
    def test_stale_data(self):
        """WHEN the code under test is exercised for: stale data"""
        from flowboard.application.data_quality import check_data_freshness

        issue = MagicMock()
        issue.updated = date.today() - timedelta(days=30)
        warnings = check_data_freshness([issue], max_age_days=7)

        """THEN the expected behaviour holds: stale data"""
        assert len(warnings) == 1
        assert "stale" in warnings[0].lower() or "ago" in warnings[0].lower()

    """GIVEN data freshness and the scenario: no issues"""
    def test_no_issues(self):
        """WHEN the code under test is exercised for: no issues"""
        from flowboard.application.data_quality import check_data_freshness

        warnings = check_data_freshness([])

        """THEN the expected behaviour holds: no issues"""
        assert len(warnings) == 1
        assert "empty" in warnings[0].lower() or "no issues" in warnings[0].lower()


# ===========================================================================
# Jira Webhook Listener
# ===========================================================================


class TestJiraWebhook:
    """Tests for jira webhook."""

    """GIVEN jira webhook and the scenario: webhook stores event"""
    def test_webhook_stores_event(self):
        """WHEN the code under test is exercised for: webhook stores event"""
        import asyncio

        from httpx import ASGITransport, AsyncClient

        from flowboard.web.server import create_app

        app = create_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                r = await ac.post(
                    "/api/webhooks/jira",
                    json={
                        "webhookEvent": "jira:issue_updated",
                        "issue": {"key": "PROJ-123"},
                    },
                    headers=_CSRF,
                )
                return r

        resp = asyncio.get_event_loop().run_until_complete(_run())

        """THEN the expected behaviour holds: webhook stores event"""
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["event"] == "jira:issue_updated"

    """GIVEN jira webhook and the scenario: webhook invalid json"""
    def test_webhook_invalid_json(self):
        """WHEN the code under test is exercised for: webhook invalid json"""
        import asyncio

        from httpx import ASGITransport, AsyncClient

        from flowboard.web.server import create_app

        app = create_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                r = await ac.post(
                    "/api/webhooks/jira",
                    content=b"not json",
                    headers={**_CSRF, "content-type": "application/json"},
                )
                return r

        resp = asyncio.get_event_loop().run_until_complete(_run())

        """THEN the expected behaviour holds: webhook invalid json"""
        assert resp.status_code == 400

    """GIVEN jira webhook and the scenario: webhook events endpoint"""
    def test_webhook_events_endpoint(self):
        """WHEN the code under test is exercised for: webhook events endpoint"""
        import asyncio

        from httpx import ASGITransport, AsyncClient

        from flowboard.web.server import create_app

        app = create_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                r = await ac.get("/api/webhooks/jira/events")
                return r

        resp = asyncio.get_event_loop().run_until_complete(_run())

        """THEN the expected behaviour holds: webhook events endpoint"""
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    """GIVEN jira webhook and the scenario: webhook sprint triggers refresh"""
    def test_webhook_sprint_triggers_refresh(self):
        """WHEN the code under test is exercised for: webhook sprint triggers refresh"""
        import asyncio

        from httpx import ASGITransport, AsyncClient

        from flowboard.web.server import create_app

        app = create_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                r = await ac.post(
                    "/api/webhooks/jira",
                    json={
                        "webhookEvent": "sprint_started",
                    },
                    headers=_CSRF,
                )
                return r

        resp = asyncio.get_event_loop().run_until_complete(_run())

        """THEN the expected behaviour holds: webhook sprint triggers refresh"""
        assert resp.json()["refresh_triggered"] is True


# ===========================================================================
# Snapshot History
# ===========================================================================


class TestSnapshotHistory:
    """Tests for snapshot history."""

    """GIVEN snapshot history and the scenario: save no dashboard"""
    def test_save_no_dashboard(self):
        """WHEN the code under test is exercised for: save no dashboard"""
        import asyncio

        from httpx import ASGITransport, AsyncClient

        from flowboard.web.server import create_app

        app = create_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                r = await ac.post("/api/snapshots/save", headers=_CSRF)
                return r

        resp = asyncio.get_event_loop().run_until_complete(_run())

        """THEN the expected behaviour holds: save no dashboard"""
        assert resp.status_code == 400

    """GIVEN snapshot history and the scenario: list snapshots empty"""
    def test_list_snapshots_empty(self):
        """WHEN the code under test is exercised for: list snapshots empty"""
        import asyncio

        from httpx import ASGITransport, AsyncClient

        from flowboard.web.server import create_app

        app = create_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                r = await ac.get("/api/snapshots")
                return r

        resp = asyncio.get_event_loop().run_until_complete(_run())

        """THEN the expected behaviour holds: list snapshots empty"""
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    """GIVEN snapshot history and the scenario: get snapshot invalid format"""
    def test_get_snapshot_invalid_format(self):
        """WHEN the code under test is exercised for: get snapshot invalid format"""
        import asyncio

        from httpx import ASGITransport, AsyncClient

        from flowboard.web.server import create_app

        app = create_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                r = await ac.get("/api/snapshots/invalid")
                return r

        resp = asyncio.get_event_loop().run_until_complete(_run())

        """THEN the expected behaviour holds: get snapshot invalid format"""
        assert resp.status_code == 400

    """GIVEN snapshot history and the scenario: get snapshot not found"""
    def test_get_snapshot_not_found(self):
        """WHEN the code under test is exercised for: get snapshot not found"""
        import asyncio

        from httpx import ASGITransport, AsyncClient

        from flowboard.web.server import create_app

        app = create_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                r = await ac.get("/api/snapshots/20991231_235959")
                return r

        resp = asyncio.get_event_loop().run_until_complete(_run())

        """THEN the expected behaviour holds: get snapshot not found"""
        assert resp.status_code == 404


# ===========================================================================
# Multi-Dashboard Management
# ===========================================================================


class TestMultiDashboard:
    """Tests for multi dashboard."""

    """GIVEN multi dashboard and the scenario: list dashboards"""
    def test_list_dashboards(self):
        """WHEN the code under test is exercised for: list dashboards"""
        import asyncio

        from httpx import ASGITransport, AsyncClient

        from flowboard.web.server import create_app

        app = create_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                r = await ac.get("/api/dashboards")
                return r

        resp = asyncio.get_event_loop().run_until_complete(_run())

        """THEN the expected behaviour holds: list dashboards"""
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert isinstance(resp.json()["dashboards"], list)

    """GIVEN multi dashboard and the scenario: generate invalid id"""
    def test_generate_invalid_id(self):
        """WHEN the code under test is exercised for: generate invalid id"""
        import asyncio

        from httpx import ASGITransport, AsyncClient

        from flowboard.web.server import create_app

        app = create_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                r = await ac.post("/api/dashboards/evil-id/generate", headers=_CSRF)
                return r

        resp = asyncio.get_event_loop().run_until_complete(_run())
        # Should be 404 (config not found) since path traversal won't work with valid ID chars

        """THEN the expected behaviour holds: generate invalid id"""
        assert resp.status_code in (400, 404)

    """GIVEN multi dashboard and the scenario: generate nonexistent config"""
    def test_generate_nonexistent_config(self):
        """WHEN the code under test is exercised for: generate nonexistent config"""
        import asyncio

        from httpx import ASGITransport, AsyncClient

        from flowboard.web.server import create_app

        app = create_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                r = await ac.post("/api/dashboards/nonexistent/generate", headers=_CSRF)
                return r

        resp = asyncio.get_event_loop().run_until_complete(_run())

        """THEN the expected behaviour holds: generate nonexistent config"""
        assert resp.status_code == 404


# ===========================================================================
# XLSX/CSV Export
# ===========================================================================
