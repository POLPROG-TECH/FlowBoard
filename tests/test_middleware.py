"""Core middleware tests - CSRF, auth, rate limiting, SSE bounds, CSP headers, error masking."""

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
    """Tests for c s r f protection."""

    """GIVEN c s r f protection and the scenario: rejects post without header"""
    def test_rejects_post_without_header(self):
        """WHEN the code under test is exercised for: rejects post without header"""
        from flowboard.web.middleware import CSRFMiddleware

        app = MagicMock()
        middleware = CSRFMiddleware(app)
        sent = []

        async def mock_send(msg):
            sent.append(msg)

        scope = {"type": "http", "method": "POST", "path": "/api/analyze", "headers": []}
        asyncio.get_event_loop().run_until_complete(middleware(scope, MagicMock(), mock_send))

        """THEN the expected behaviour holds: rejects post without header"""
        assert sent[0]["status"] == 403
        app.assert_not_called()

    """GIVEN c s r f protection and the scenario: allows post with correct header"""
    def test_allows_post_with_correct_header(self):
        """WHEN the code under test is exercised for: allows post with correct header"""
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

        """THEN the expected behaviour holds: allows post with correct header"""
        assert called

    """GIVEN c s r f protection and the scenario: allows get without header"""
    def test_allows_get_without_header(self):
        """WHEN the code under test is exercised for: allows get without header"""
        from flowboard.web.middleware import CSRFMiddleware

        called = []

        async def mock_app(scope, receive, send):
            called.append(True)

        middleware = CSRFMiddleware(mock_app)
        scope = {"type": "http", "method": "GET", "path": "/api/status", "headers": []}
        asyncio.get_event_loop().run_until_complete(middleware(scope, MagicMock(), MagicMock()))

        """THEN the expected behaviour holds: allows get without header"""
        assert called

    """GIVEN c s r f protection and the scenario: case insensitive header value"""
    def test_case_insensitive_header_value(self):
        """WHEN the code under test is exercised for: case insensitive header value"""
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

        """THEN the expected behaviour holds: case insensitive header value"""
        assert called


# ===================================================================
# Authentication middleware
# ===================================================================


class TestAuthMiddleware:
    """Tests for auth middleware."""

    """GIVEN auth middleware and the scenario: disabled without env var"""
    def test_disabled_without_env_var(self):
        """WHEN the code under test is exercised for: disabled without env var"""
        from flowboard.web.middleware import AuthMiddleware

        """THEN the expected behaviour holds: disabled without env var"""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("FLOWBOARD_API_TOKEN", None)
            middleware = AuthMiddleware(MagicMock())
            assert not middleware.enabled

    """GIVEN auth middleware and the scenario: enabled with env var"""
    def test_enabled_with_env_var(self):
        """WHEN the code under test is exercised for: enabled with env var"""
        from flowboard.web.middleware import AuthMiddleware

        """THEN the expected behaviour holds: enabled with env var"""
        with patch.dict(os.environ, {"FLOWBOARD_API_TOKEN": "s3cret"}):
            middleware = AuthMiddleware(MagicMock())
            assert middleware.enabled

    """GIVEN auth middleware and the scenario: rejects without token"""
    def test_rejects_without_token(self):
        """WHEN the code under test is exercised for: rejects without token"""
        from flowboard.web.middleware import AuthMiddleware

        """THEN the expected behaviour holds: rejects without token"""
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

    """GIVEN auth middleware and the scenario: allows valid bearer"""
    def test_allows_valid_bearer(self):
        """WHEN the code under test is exercised for: allows valid bearer"""
        from flowboard.web.middleware import AuthMiddleware

        """THEN the expected behaviour holds: allows valid bearer"""
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

    """GIVEN auth middleware and the scenario: allows health endpoints without token"""
    def test_allows_health_endpoints_without_token(self):
        """WHEN the code under test is exercised for: allows health endpoints without token"""
        from flowboard.web.middleware import AuthMiddleware

        """THEN the expected behaviour holds: allows health endpoints without token"""
        with patch.dict(os.environ, {"FLOWBOARD_API_TOKEN": "s3cret"}):
            called = []

            async def mock_app(scope, receive, send):
                called.append(True)

            middleware = AuthMiddleware(mock_app)
            scope = {"type": "http", "path": "/health/live", "headers": []}
            asyncio.get_event_loop().run_until_complete(middleware(scope, MagicMock(), MagicMock()))
            assert called

    """GIVEN auth middleware and the scenario: allows cookie auth"""
    def test_allows_cookie_auth(self):
        """WHEN the code under test is exercised for: allows cookie auth"""
        from flowboard.web.middleware import AuthMiddleware

        """THEN the expected behaviour holds: allows cookie auth"""
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

    """GIVEN auth middleware and the scenario: rejects wrong token"""
    def test_rejects_wrong_token(self):
        """WHEN the code under test is exercised for: rejects wrong token"""
        from flowboard.web.middleware import AuthMiddleware

        """THEN the expected behaviour holds: rejects wrong token"""
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
    """GIVEN credential warnings and the scenario: warns on embedded auth token"""
    def test_warns_on_embedded_auth_token(self, caplog):
        """WHEN the code under test is exercised for: warns on embedded auth token"""
        from flowboard.infrastructure.config.loader import _warn_embedded_credentials

        raw = {"jira": {"auth_token": "SECRET", "base_url": "https://j.example.com"}}
        with caplog.at_level(logging.WARNING):
            _warn_embedded_credentials(raw)

        """THEN the expected behaviour holds: warns on embedded auth token"""
        assert any("auth_token" in r.message for r in caplog.records)

    """GIVEN credential warnings and the scenario: warns on pat"""
    def test_warns_on_pat(self, caplog):
        """WHEN the code under test is exercised for: warns on pat"""
        from flowboard.infrastructure.config.loader import _warn_embedded_credentials

        raw = {"jira": {"pat": "SECRET_PAT", "base_url": "https://j.example.com"}}
        with caplog.at_level(logging.WARNING):
            _warn_embedded_credentials(raw)

        """THEN the expected behaviour holds: warns on pat"""
        assert any("pat" in r.message for r in caplog.records)

    """GIVEN credential warnings and the scenario: no warning without creds"""
    def test_no_warning_without_creds(self, caplog):
        """WHEN the code under test is exercised for: no warning without creds"""
        from flowboard.infrastructure.config.loader import _warn_embedded_credentials

        raw = {"jira": {"base_url": "https://j.example.com"}}
        with caplog.at_level(logging.WARNING):
            _warn_embedded_credentials(raw)

        """THEN the expected behaviour holds: no warning without creds"""
        assert not caplog.records


# ===================================================================
# Rate limiting
# ===================================================================


class TestRateLimiting:
    """GIVEN rate limiting and the scenario: allows normal traffic"""
    def test_allows_normal_traffic(self):
        """WHEN the code under test is exercised for: allows normal traffic"""
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

        """THEN the expected behaviour holds: allows normal traffic"""
        assert len(called) == 5

    """GIVEN rate limiting and the scenario: blocks excess"""
    def test_blocks_excess(self):
        """WHEN the code under test is exercised for: blocks excess"""
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

        """THEN the expected behaviour holds: blocks excess"""
        assert len(called) == 3
        blocked = [m for m in sent if m.get("status") == 429]
        assert len(blocked) == 2

    """GIVEN rate limiting and the scenario: health exempt"""
    def test_health_exempt(self):
        """WHEN the code under test is exercised for: health exempt"""
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

        """THEN the expected behaviour holds: health exempt"""
        assert len(called) == 5


# ===================================================================
# SSE subscriber memory bounds
# ===================================================================


class TestSSEBounds:
    """GIVEN s s e bounds and the scenario: subscriber limit enforced"""
    def test_subscriber_limit_enforced(self):
        """WHEN the code under test is exercised for: subscriber limit enforced"""
        from flowboard.web.state import _MAX_SSE_SUBSCRIBERS, AppState

        state = AppState()
        for _ in range(_MAX_SSE_SUBSCRIBERS + 20):
            state.subscribe()

        """THEN the expected behaviour holds: subscriber limit enforced"""
        assert len(state._sse_subscribers) <= _MAX_SSE_SUBSCRIBERS

    """GIVEN s s e bounds and the scenario: broadcast cleans full queues"""
    def test_broadcast_cleans_full_queues(self):
        """WHEN the code under test is exercised for: broadcast cleans full queues"""
        from flowboard.web.state import AppState

        state = AppState()
        q = state.subscribe()
        # Fill the queue to maxsize
        for i in range(100):
            q.put_nowait({"event": "test", "data": {"i": i}})

        asyncio.get_event_loop().run_until_complete(state.broadcast("test", {"x": 1}))
        # Full queue should have been removed

        """THEN the expected behaviour holds: broadcast cleans full queues"""
        assert q not in state._sse_subscribers


# ===================================================================
# CSP header
# ===================================================================


class TestCSPHeader:
    """GIVEN c s p header and the scenario: csp header present"""
    def test_csp_header_present(self):
        """WHEN the code under test is exercised for: csp header present"""
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

        """THEN the expected behaviour holds: csp header present"""
        assert b"content-security-policy" in header_names
        csp = next(h[1] for h in captured if h[0] == b"content-security-policy")
        assert b"default-src" in csp
        assert b"frame-ancestors 'none'" in csp


# ===================================================================
# Error message masking
# ===================================================================


class TestErrorMasking:
    """GIVEN error masking and the scenario: demo error masked"""
    def test_demo_error_masked(self):
        """WHEN the code under test is exercised for: demo error masked"""
        from fastapi.testclient import TestClient

        from flowboard.web.server import create_app

        app = create_app(config_path=None, first_run=True)
        client = TestClient(app, raise_server_exceptions=False)
        with patch(
            "flowboard.web.server.locate_demo_fixture", side_effect=RuntimeError("db password=LEAK")
        ):
            resp = client.post("/api/demo", headers={"X-Requested-With": "FlowBoard"})

        """THEN the expected behaviour holds: demo error masked"""
        assert resp.status_code == 500
        assert "LEAK" not in resp.json().get("error", "")
        assert "server logs" in resp.json()["error"].lower()

    """GIVEN error masking and the scenario: verify error masked"""
    def test_verify_error_masked(self):
        """WHEN the code under test is exercised for: verify error masked"""
        from fastapi.testclient import TestClient

        from flowboard.web.server import create_app

        app = create_app(config_path="/tmp/nonexistent_cfg.json", first_run=False)
        client = TestClient(app, raise_server_exceptions=False)
        # Verify fails because config path doesn't exist - error should be masked
        with patch("flowboard.web.server.locate_demo_fixture"):
            resp = client.post("/api/verify", headers={"X-Requested-With": "FlowBoard"})

        """THEN the expected behaviour holds: verify error masked"""
        assert resp.status_code == 500
        error_msg = resp.json().get("error", "")
        assert "server logs" in error_msg.lower()


# ===================================================================
# CSV dataset input validation
# ===================================================================


class TestCSVDatasetValidation:
    """GIVEN c s v dataset validation and the scenario: rejects unknown dataset"""
    def test_rejects_unknown_dataset(self):
        """WHEN the code under test is exercised for: rejects unknown dataset"""
        from fastapi.testclient import TestClient

        from flowboard.web.server import create_app

        app = create_app(config_path=None, first_run=True)
        client = TestClient(app)
        resp = client.get("/api/export/csv?dataset='; DROP TABLE")

        """THEN the expected behaviour holds: rejects unknown dataset"""
        assert resp.status_code == 400
        assert "Unknown dataset" in resp.json()["error"]

    """GIVEN c s v dataset validation and the scenario: accepts valid datasets"""
    def test_accepts_valid_datasets(self):
        """WHEN the code under test is exercised for: accepts valid datasets"""
        from fastapi.testclient import TestClient

        from flowboard.web.server import create_app

        app = create_app(config_path=None, first_run=True)
        client = TestClient(app)

        """THEN the expected behaviour holds: accepts valid datasets"""
        for ds in ("issues", "workload", "risks"):
            resp = client.get(f"/api/export/csv?dataset={ds}")
            # 404 expected because no analysis done, but NOT 400
            assert resp.status_code == 404


# ===================================================================
# Demo fixture path traversal
# ===================================================================


class TestDemoFixturePathSafety:
    """GIVEN demo fixture path safety and the scenario: fixture path within project"""
    def test_fixture_path_within_project(self):
        """WHEN the code under test is exercised for: fixture path within project"""
        from flowboard.web.server_helpers import locate_demo_fixture

        """THEN the expected behaviour holds: fixture path within project"""
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
    """GIVEN pipeline timeout and the scenario: timeout env parsed"""
    def test_timeout_env_parsed(self):
        """THEN the expected behaviour holds: timeout env parsed"""
        with patch.dict(os.environ, {"FLOWBOARD_ANALYSIS_TIMEOUT": "42"}):
            import importlib

            import flowboard.web.server as srv

            importlib.reload(srv)
            assert srv._ANALYSIS_TIMEOUT == 42
            os.environ.pop("FLOWBOARD_ANALYSIS_TIMEOUT", None)
            importlib.reload(srv)

    """GIVEN pipeline timeout and the scenario: default timeout is 300"""
    def test_default_timeout_is_300(self):
        """WHEN the code under test is exercised for: default timeout is 300"""
        import flowboard.web.server as srv

        """THEN the expected behaviour holds: default timeout is 300"""
        assert srv._ANALYSIS_TIMEOUT == 300


# ===================================================================
# Thread-safe locale handling
# ===================================================================
