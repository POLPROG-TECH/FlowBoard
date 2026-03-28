"""Core middleware tests — CSRF, auth, rate limiting, SSE bounds, CSP headers, error masking."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

# ===================================================================
# CSRF protection
# ===================================================================


class TestCSRFProtection:
    """Verify CSRF middleware blocks unprotected state-changing requests."""

    def test_rejects_post_without_header(self):
        from flowboard.web.middleware import CSRFMiddleware

        app = MagicMock()
        middleware = CSRFMiddleware(app)
        sent = []

        async def mock_send(msg):
            sent.append(msg)

        scope = {"type": "http", "method": "POST", "path": "/api/analyze", "headers": []}
        asyncio.get_event_loop().run_until_complete(middleware(scope, MagicMock(), mock_send))
        assert sent[0]["status"] == 403
        app.assert_not_called()

    def test_allows_post_with_correct_header(self):
        from flowboard.web.middleware import CSRFMiddleware

        called = []

        async def mock_app(scope, receive, send):
            called.append(True)

        middleware = CSRFMiddleware(mock_app)
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/analyze",
            "headers": [(b"x-requested-with", b"FlowBoard")],
        }
        asyncio.get_event_loop().run_until_complete(middleware(scope, MagicMock(), MagicMock()))
        assert called

    def test_allows_get_without_header(self):
        from flowboard.web.middleware import CSRFMiddleware

        called = []

        async def mock_app(scope, receive, send):
            called.append(True)

        middleware = CSRFMiddleware(mock_app)
        scope = {"type": "http", "method": "GET", "path": "/api/status", "headers": []}
        asyncio.get_event_loop().run_until_complete(middleware(scope, MagicMock(), MagicMock()))
        assert called

    def test_case_insensitive_header_value(self):
        from flowboard.web.middleware import CSRFMiddleware

        called = []

        async def mock_app(scope, receive, send):
            called.append(True)

        middleware = CSRFMiddleware(mock_app)
        scope = {
            "type": "http",
            "method": "DELETE",
            "path": "/something",
            "headers": [(b"x-requested-with", b"FLOWBOARD")],
        }
        asyncio.get_event_loop().run_until_complete(middleware(scope, MagicMock(), MagicMock()))
        assert called


# ===================================================================
# Authentication middleware
# ===================================================================


class TestAuthMiddleware:
    """Verify bearer-token authentication works correctly."""

    def test_disabled_without_env_var(self):
        from flowboard.web.middleware import AuthMiddleware

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("FLOWBOARD_API_TOKEN", None)
            middleware = AuthMiddleware(MagicMock())
            assert not middleware.enabled

    def test_enabled_with_env_var(self):
        from flowboard.web.middleware import AuthMiddleware

        with patch.dict(os.environ, {"FLOWBOARD_API_TOKEN": "s3cret"}):
            middleware = AuthMiddleware(MagicMock())
            assert middleware.enabled

    def test_rejects_without_token(self):
        from flowboard.web.middleware import AuthMiddleware

        with patch.dict(os.environ, {"FLOWBOARD_API_TOKEN": "s3cret"}):
            app = MagicMock()
            middleware = AuthMiddleware(app)
            sent = []

            async def mock_send(msg):
                sent.append(msg)

            scope = {"type": "http", "path": "/api/status", "headers": []}
            asyncio.get_event_loop().run_until_complete(middleware(scope, MagicMock(), mock_send))
            assert sent[0]["status"] == 401
            app.assert_not_called()

    def test_allows_valid_bearer(self):
        from flowboard.web.middleware import AuthMiddleware

        with patch.dict(os.environ, {"FLOWBOARD_API_TOKEN": "s3cret"}):
            called = []

            async def mock_app(scope, receive, send):
                called.append(True)

            middleware = AuthMiddleware(mock_app)
            scope = {
                "type": "http",
                "path": "/api/status",
                "headers": [(b"authorization", b"Bearer s3cret")],
            }
            asyncio.get_event_loop().run_until_complete(middleware(scope, MagicMock(), MagicMock()))
            assert called

    def test_allows_health_endpoints_without_token(self):
        from flowboard.web.middleware import AuthMiddleware

        with patch.dict(os.environ, {"FLOWBOARD_API_TOKEN": "s3cret"}):
            called = []

            async def mock_app(scope, receive, send):
                called.append(True)

            middleware = AuthMiddleware(mock_app)
            scope = {"type": "http", "path": "/health/live", "headers": []}
            asyncio.get_event_loop().run_until_complete(middleware(scope, MagicMock(), MagicMock()))
            assert called

    def test_allows_cookie_auth(self):
        from flowboard.web.middleware import AuthMiddleware

        with patch.dict(os.environ, {"FLOWBOARD_API_TOKEN": "s3cret"}):
            called = []

            async def mock_app(scope, receive, send):
                called.append(True)

            middleware = AuthMiddleware(mock_app)
            scope = {
                "type": "http",
                "path": "/api/status",
                "headers": [(b"cookie", b"fb_token=s3cret; other=val")],
            }
            asyncio.get_event_loop().run_until_complete(middleware(scope, MagicMock(), MagicMock()))
            assert called

    def test_rejects_wrong_token(self):
        from flowboard.web.middleware import AuthMiddleware

        with patch.dict(os.environ, {"FLOWBOARD_API_TOKEN": "s3cret"}):
            app = MagicMock()
            middleware = AuthMiddleware(app)
            sent = []

            async def mock_send(msg):
                sent.append(msg)

            scope = {
                "type": "http",
                "path": "/api/status",
                "headers": [(b"authorization", b"Bearer wrong")],
            }
            asyncio.get_event_loop().run_until_complete(middleware(scope, MagicMock(), mock_send))
            assert sent[0]["status"] == 401


# ===================================================================
# Credential warnings in config
# ===================================================================


class TestCredentialWarnings:
    def test_warns_on_embedded_auth_token(self, caplog):
        from flowboard.infrastructure.config.loader import _warn_embedded_credentials

        raw = {"jira": {"auth_token": "SECRET", "base_url": "https://j.example.com"}}
        with caplog.at_level(logging.WARNING):
            _warn_embedded_credentials(raw)
        assert any("auth_token" in r.message for r in caplog.records)

    def test_warns_on_pat(self, caplog):
        from flowboard.infrastructure.config.loader import _warn_embedded_credentials

        raw = {"jira": {"pat": "SECRET_PAT", "base_url": "https://j.example.com"}}
        with caplog.at_level(logging.WARNING):
            _warn_embedded_credentials(raw)
        assert any("pat" in r.message for r in caplog.records)

    def test_no_warning_without_creds(self, caplog):
        from flowboard.infrastructure.config.loader import _warn_embedded_credentials

        raw = {"jira": {"base_url": "https://j.example.com"}}
        with caplog.at_level(logging.WARNING):
            _warn_embedded_credentials(raw)
        assert not caplog.records


# ===================================================================
# Rate limiting
# ===================================================================


class TestRateLimiting:
    def test_allows_normal_traffic(self):
        from flowboard.web.middleware import RateLimitMiddleware

        called = []

        async def mock_app(scope, receive, send):
            called.append(True)

        with patch.dict(os.environ, {"FLOWBOARD_RATE_LIMIT": "10", "FLOWBOARD_RATE_WINDOW": "60"}):
            middleware = RateLimitMiddleware(mock_app)

        scope = {
            "type": "http",
            "path": "/api/status",
            "method": "GET",
            "client": ("10.0.0.1", 9999),
        }
        for _ in range(5):
            asyncio.get_event_loop().run_until_complete(middleware(scope, MagicMock(), MagicMock()))
        assert len(called) == 5

    def test_blocks_excess(self):
        from flowboard.web.middleware import RateLimitMiddleware

        called = []

        async def mock_app(scope, receive, send):
            called.append(True)

        with patch.dict(os.environ, {"FLOWBOARD_RATE_LIMIT": "3", "FLOWBOARD_RATE_WINDOW": "60"}):
            middleware = RateLimitMiddleware(mock_app)

        scope = {
            "type": "http",
            "path": "/api/status",
            "method": "GET",
            "client": ("10.0.0.1", 9999),
        }
        sent = []

        async def mock_send(msg):
            sent.append(msg)

        for _ in range(5):
            asyncio.get_event_loop().run_until_complete(middleware(scope, MagicMock(), mock_send))
        assert len(called) == 3
        blocked = [m for m in sent if m.get("status") == 429]
        assert len(blocked) == 2

    def test_health_exempt(self):
        from flowboard.web.middleware import RateLimitMiddleware

        called = []

        async def mock_app(scope, receive, send):
            called.append(True)

        with patch.dict(os.environ, {"FLOWBOARD_RATE_LIMIT": "1", "FLOWBOARD_RATE_WINDOW": "60"}):
            middleware = RateLimitMiddleware(mock_app)

        scope = {
            "type": "http",
            "path": "/health/live",
            "method": "GET",
            "client": ("10.0.0.1", 9999),
        }
        for _ in range(5):
            asyncio.get_event_loop().run_until_complete(middleware(scope, MagicMock(), MagicMock()))
        assert len(called) == 5


# ===================================================================
# SSE subscriber memory bounds
# ===================================================================


class TestSSEBounds:
    def test_subscriber_limit_enforced(self):
        from flowboard.web.state import _MAX_SSE_SUBSCRIBERS, AppState

        state = AppState()
        for _ in range(_MAX_SSE_SUBSCRIBERS + 20):
            state.subscribe()
        assert len(state._sse_subscribers) <= _MAX_SSE_SUBSCRIBERS

    def test_broadcast_cleans_full_queues(self):
        from flowboard.web.state import AppState

        state = AppState()
        q = state.subscribe()
        # Fill the queue to maxsize
        for i in range(100):
            q.put_nowait({"event": "test", "data": {"i": i}})

        asyncio.get_event_loop().run_until_complete(state.broadcast("test", {"x": 1}))
        # Full queue should have been removed
        assert q not in state._sse_subscribers


# ===================================================================
# CSP header
# ===================================================================


class TestCSPHeader:
    def test_csp_header_present(self):
        from flowboard.web.middleware import SecurityHeadersMiddleware

        captured = []

        async def mock_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        async def capture_send(msg):
            if msg["type"] == "http.response.start":
                captured.extend(msg.get("headers", []))

        middleware = SecurityHeadersMiddleware(mock_app)
        scope = {"type": "http", "method": "GET", "path": "/"}
        asyncio.get_event_loop().run_until_complete(middleware(scope, MagicMock(), capture_send))
        header_names = [h[0] for h in captured]
        assert b"content-security-policy" in header_names
        csp = next(h[1] for h in captured if h[0] == b"content-security-policy")
        assert b"default-src" in csp
        assert b"frame-ancestors 'none'" in csp


# ===================================================================
# Error message masking
# ===================================================================


class TestErrorMasking:
    def test_demo_error_masked(self):
        from fastapi.testclient import TestClient

        from flowboard.web.server import create_app

        app = create_app(config_path=None, first_run=True)
        client = TestClient(app, raise_server_exceptions=False)
        with patch(
            "flowboard.web.server.locate_demo_fixture", side_effect=RuntimeError("db password=LEAK")
        ):
            resp = client.post("/api/demo", headers={"X-Requested-With": "FlowBoard"})
        assert resp.status_code == 500
        assert "LEAK" not in resp.json().get("error", "")
        assert "server logs" in resp.json()["error"].lower()

    def test_verify_error_masked(self):
        from fastapi.testclient import TestClient

        from flowboard.web.server import create_app

        app = create_app(config_path="/tmp/nonexistent_cfg.json", first_run=False)
        client = TestClient(app, raise_server_exceptions=False)
        # Verify fails because config path doesn't exist — error should be masked
        with patch("flowboard.web.server.locate_demo_fixture"):
            resp = client.post("/api/verify", headers={"X-Requested-With": "FlowBoard"})
        assert resp.status_code == 500
        error_msg = resp.json().get("error", "")
        assert "server logs" in error_msg.lower()


# ===================================================================
# CSV dataset input validation
# ===================================================================


class TestCSVDatasetValidation:
    def test_rejects_unknown_dataset(self):
        from fastapi.testclient import TestClient

        from flowboard.web.server import create_app

        app = create_app(config_path=None, first_run=True)
        client = TestClient(app)
        resp = client.get("/api/export/csv?dataset='; DROP TABLE")
        assert resp.status_code == 400
        assert "Unknown dataset" in resp.json()["error"]

    def test_accepts_valid_datasets(self):
        from fastapi.testclient import TestClient

        from flowboard.web.server import create_app

        app = create_app(config_path=None, first_run=True)
        client = TestClient(app)
        for ds in ("issues", "workload", "risks"):
            resp = client.get(f"/api/export/csv?dataset={ds}")
            # 404 expected because no analysis done, but NOT 400
            assert resp.status_code == 404


# ===================================================================
# Demo fixture path traversal
# ===================================================================


class TestDemoFixturePathSafety:
    def test_fixture_path_within_project(self):
        from flowboard.web.server_helpers import locate_demo_fixture

        try:
            path = locate_demo_fixture()
            project_root = Path(__file__).resolve().parents[1]
            assert str(path).startswith(str(project_root))
        except FileNotFoundError:
            pass  # OK in CI without fixtures


# ===================================================================
# Analysis pipeline timeout
# ===================================================================


class TestPipelineTimeout:
    def test_timeout_env_parsed(self):
        with patch.dict(os.environ, {"FLOWBOARD_ANALYSIS_TIMEOUT": "42"}):
            import importlib

            import flowboard.web.server as srv

            importlib.reload(srv)
            assert srv._ANALYSIS_TIMEOUT == 42
            os.environ.pop("FLOWBOARD_ANALYSIS_TIMEOUT", None)
            importlib.reload(srv)

    def test_default_timeout_is_300(self):
        import flowboard.web.server as srv

        assert srv._ANALYSIS_TIMEOUT == 300


# ===================================================================
# Thread-safe locale handling
# ===================================================================
