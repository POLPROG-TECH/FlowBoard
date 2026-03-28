"""Application feature tests — Docker, config reload, thresholds, OpenAPI, env vars, webhooks, data freshness."""

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
    """Verify Dockerfile follows best practices."""

    def test_dockerfile_exists(self):
        assert (_REPO_ROOT / "Dockerfile").exists()

    def test_multi_stage_build(self):
        content = (_REPO_ROOT / "Dockerfile").read_text()
        assert "AS builder" in content or "as builder" in content

    def test_non_root_user(self):
        content = (_REPO_ROOT / "Dockerfile").read_text()
        assert "USER" in content

    def test_healthcheck(self):
        content = (_REPO_ROOT / "Dockerfile").read_text()
        assert "HEALTHCHECK" in content

    def test_docker_compose_exists(self):
        assert (_REPO_ROOT / "docker-compose.yml").exists()

    def test_docker_compose_valid_yaml(self):
        import yaml

        content = (_REPO_ROOT / "docker-compose.yml").read_text()
        data = yaml.safe_load(content)
        assert "services" in data
        assert "flowboard" in data["services"]


# ===========================================================================
# Hot Config Reload
# ===========================================================================


class TestHotConfigReload:
    """Test POST /api/config/reload endpoint."""

    def test_reload_no_config(self):
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
        assert resp.status_code == 400
        assert "No configuration" in resp.json()["error"]


# ===========================================================================
# Per-team Thresholds
# ===========================================================================


class TestPerTeamThresholds:
    """Test per-team threshold overrides in config loader."""

    def test_team_thresholds_parsed(self):
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
        assert teams[0].thresholds == {"overload_points": 30}
        assert teams[1].thresholds is None

    def test_empty_thresholds_becomes_none(self):
        from flowboard.infrastructure.config.loader import _build_teams

        raw = {"teams": [{"key": "t", "name": "T", "members": [], "thresholds": {}}]}
        teams = _build_teams(raw)
        assert teams[0].thresholds is None

    def test_schema_allows_team_thresholds(self):
        schema = json.loads((_REPO_ROOT / "config.schema.json").read_text())
        team_props = schema["properties"]["teams"]["items"]["properties"]
        assert "thresholds" in team_props


# ===========================================================================
# OpenAPI /docs
# ===========================================================================


class TestOpenAPIDocs:
    """Test that OpenAPI docs are enabled."""

    def test_docs_endpoint(self):
        import asyncio

        from httpx import ASGITransport, AsyncClient

        from flowboard.web.server import create_app

        app = create_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                r = await ac.get("/docs")
                return r

        resp = asyncio.get_event_loop().run_until_complete(_run())
        assert resp.status_code == 200
        assert "swagger" in resp.text.lower() or "openapi" in resp.text.lower()


# ===========================================================================
# Environment Variable Expansion
# ===========================================================================


class TestEnvVarExpansion:
    """Test ${VAR} expansion in config strings (restricted to safe keys)."""

    def test_expand_simple_string(self):
        from flowboard.infrastructure.config.loader import _expand_env_vars

        with patch.dict(os.environ, {"MY_TOKEN": "secret123"}):
            result = _expand_env_vars("Bearer ${MY_TOKEN}", _key="auth_token")
            assert result == "Bearer secret123"

    def test_expand_nested_dict(self):
        from flowboard.infrastructure.config.loader import _expand_env_vars

        with patch.dict(os.environ, {"DB_HOST": "localhost"}):
            result = _expand_env_vars({"base_url": "${DB_HOST}", "port": 5432})
            assert result == {"base_url": "localhost", "port": 5432}

    def test_expand_list(self):
        from flowboard.infrastructure.config.loader import _expand_env_vars

        with patch.dict(os.environ, {"A": "1", "B": "2"}):
            result = _expand_env_vars(["${A}", "${B}", "plain"], _key="path")
            assert result == ["1", "2", "plain"]

    def test_missing_env_var_preserved(self):
        from flowboard.infrastructure.config.loader import _expand_env_vars

        result = _expand_env_vars("${NONEXISTENT_VAR_12345}", _key="base_url")
        assert result == "${NONEXISTENT_VAR_12345}"

    def test_non_string_passthrough(self):
        from flowboard.infrastructure.config.loader import _expand_env_vars

        assert _expand_env_vars(42) == 42
        assert _expand_env_vars(None) is None
        assert _expand_env_vars(True) is True

    def test_unsafe_key_not_expanded(self):
        from flowboard.infrastructure.config.loader import _expand_env_vars

        with patch.dict(os.environ, {"SECRET": "leaked"}):
            result = _expand_env_vars("${SECRET}", _key="arbitrary_field")
            assert result == "${SECRET}"


# ===========================================================================
# Correlation ID Middleware
# ===========================================================================


class TestCorrelationIdMiddleware:
    """Test X-Request-ID header propagation."""

    def test_generates_request_id(self):
        import asyncio

        from httpx import ASGITransport, AsyncClient

        from flowboard.web.server import create_app

        app = create_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                r = await ac.get("/api/health")
                return r

        resp = asyncio.get_event_loop().run_until_complete(_run())
        assert "x-request-id" in resp.headers
        assert len(resp.headers["x-request-id"]) >= 8

    def test_propagates_provided_id(self):
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
        assert resp.headers["x-request-id"] == custom_id


# ===========================================================================
# Duplicate Sprint Detection
# ===========================================================================


class TestDuplicateSprintDetection:
    """Test data quality check for sprints on multiple boards."""

    def test_no_duplicates(self):
        from flowboard.application.data_quality import check_duplicate_sprints

        sprints = [
            {"name": "Sprint 1", "originBoardId": 1},
            {"name": "Sprint 2", "originBoardId": 1},
        ]
        warnings = check_duplicate_sprints(sprints)
        assert warnings == []

    def test_detects_duplicates(self):
        from flowboard.application.data_quality import check_duplicate_sprints

        sprints = [
            {"name": "Sprint 1", "originBoardId": 1},
            {"name": "Sprint 1", "originBoardId": 2},
        ]
        warnings = check_duplicate_sprints(sprints)
        assert len(warnings) == 1
        assert "Sprint 1" in warnings[0]
        assert "2 boards" in warnings[0]

    def test_empty_sprints(self):
        from flowboard.application.data_quality import check_duplicate_sprints

        assert check_duplicate_sprints([]) == []


# ===========================================================================
# Team Member Presence Check
# ===========================================================================


class TestTeamMemberPresence:
    """Test data quality check for team member existence in issues."""

    def test_all_members_found(self):
        from flowboard.application.data_quality import check_team_member_presence

        config = MagicMock()
        config.teams = [MagicMock(name="Alpha", members=["alice"])]
        config.teams[0].name = "Alpha"
        config.teams[0].members = ["alice"]

        issues = [MagicMock(assignee="alice"), MagicMock(assignee="bob")]
        warnings = check_team_member_presence(config, issues)
        assert warnings == []

    def test_missing_member(self):
        from flowboard.application.data_quality import check_team_member_presence

        config = MagicMock()
        config.teams = [MagicMock()]
        config.teams[0].name = "Alpha"
        config.teams[0].members = ["alice", "charlie"]

        issues = [MagicMock(assignee="alice"), MagicMock(assignee="bob")]
        warnings = check_team_member_presence(config, issues)
        assert len(warnings) == 1
        assert "charlie" in warnings[0]

    def test_no_teams(self):
        from flowboard.application.data_quality import check_team_member_presence

        config = MagicMock()
        config.teams = []
        warnings = check_team_member_presence(config, [])
        assert warnings == []


# ===========================================================================
# Data Freshness Check
# ===========================================================================


class TestDataFreshness:
    """Test stale data detection."""

    def test_fresh_data(self):
        from flowboard.application.data_quality import check_data_freshness

        issue = MagicMock()
        issue.updated = date.today()
        warnings = check_data_freshness([issue])
        assert warnings == []

    def test_stale_data(self):
        from flowboard.application.data_quality import check_data_freshness

        issue = MagicMock()
        issue.updated = date.today() - timedelta(days=30)
        warnings = check_data_freshness([issue], max_age_days=7)
        assert len(warnings) == 1
        assert "stale" in warnings[0].lower() or "ago" in warnings[0].lower()

    def test_no_issues(self):
        from flowboard.application.data_quality import check_data_freshness

        warnings = check_data_freshness([])
        assert len(warnings) == 1
        assert "empty" in warnings[0].lower() or "no issues" in warnings[0].lower()


# ===========================================================================
# Jira Webhook Listener
# ===========================================================================


class TestJiraWebhook:
    """Test Jira webhook endpoint."""

    def test_webhook_stores_event(self):
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
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["event"] == "jira:issue_updated"

    def test_webhook_invalid_json(self):
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
        assert resp.status_code == 400

    def test_webhook_events_endpoint(self):
        import asyncio

        from httpx import ASGITransport, AsyncClient

        from flowboard.web.server import create_app

        app = create_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                r = await ac.get("/api/webhooks/jira/events")
                return r

        resp = asyncio.get_event_loop().run_until_complete(_run())
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_webhook_sprint_triggers_refresh(self):
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
        assert resp.json()["refresh_triggered"] is True


# ===========================================================================
# Snapshot History
# ===========================================================================


class TestSnapshotHistory:
    """Test snapshot save/list/get endpoints."""

    def test_save_no_dashboard(self):
        import asyncio

        from httpx import ASGITransport, AsyncClient

        from flowboard.web.server import create_app

        app = create_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                r = await ac.post("/api/snapshots/save", headers=_CSRF)
                return r

        resp = asyncio.get_event_loop().run_until_complete(_run())
        assert resp.status_code == 400

    def test_list_snapshots_empty(self):
        import asyncio

        from httpx import ASGITransport, AsyncClient

        from flowboard.web.server import create_app

        app = create_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                r = await ac.get("/api/snapshots")
                return r

        resp = asyncio.get_event_loop().run_until_complete(_run())
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_get_snapshot_invalid_format(self):
        import asyncio

        from httpx import ASGITransport, AsyncClient

        from flowboard.web.server import create_app

        app = create_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                r = await ac.get("/api/snapshots/invalid")
                return r

        resp = asyncio.get_event_loop().run_until_complete(_run())
        assert resp.status_code == 400

    def test_get_snapshot_not_found(self):
        import asyncio

        from httpx import ASGITransport, AsyncClient

        from flowboard.web.server import create_app

        app = create_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                r = await ac.get("/api/snapshots/20991231_235959")
                return r

        resp = asyncio.get_event_loop().run_until_complete(_run())
        assert resp.status_code == 404


# ===========================================================================
# Multi-Dashboard Management
# ===========================================================================


class TestMultiDashboard:
    """Test dashboard listing and generation endpoints."""

    def test_list_dashboards(self):
        import asyncio

        from httpx import ASGITransport, AsyncClient

        from flowboard.web.server import create_app

        app = create_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                r = await ac.get("/api/dashboards")
                return r

        resp = asyncio.get_event_loop().run_until_complete(_run())
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert isinstance(resp.json()["dashboards"], list)

    def test_generate_invalid_id(self):
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
        assert resp.status_code in (400, 404)

    def test_generate_nonexistent_config(self):
        import asyncio

        from httpx import ASGITransport, AsyncClient

        from flowboard.web.server import create_app

        app = create_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                r = await ac.post("/api/dashboards/nonexistent/generate", headers=_CSRF)
                return r

        resp = asyncio.get_event_loop().run_until_complete(_run())
        assert resp.status_code == 404


# ===========================================================================
# XLSX/CSV Export
# ===========================================================================
