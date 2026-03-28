"""ASGI middleware for security headers, request logging, auth, CSRF, rate limiting, and correlation IDs."""

from __future__ import annotations

import contextlib
import hmac
import os
import time
import uuid
from typing import Any

from .logging import get_logger

_log = get_logger("middleware")


# ---------------------------------------------------------------------------
# Global error handler (Blocker #12)
# ---------------------------------------------------------------------------


class ErrorHandlerMiddleware:
    """Catch unhandled exceptions and return JSON 500 without leaking stack traces."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        try:
            await self.app(scope, receive, send)
        except Exception:
            _log.exception("Unhandled error in request %s %s", scope.get("method", "?"), scope.get("path", "/"))
            body = b'{"ok":false,"error":"Internal server error"}'
            await send({
                "type": "http.response.start",
                "status": 500,
                "headers": [(b"content-type", b"application/json")],
            })
            await send({"type": "http.response.body", "body": body})


# Simple request metrics (Blocker #19)
_metrics: dict[str, int] = {
    "requests_total": 0,
    "requests_4xx": 0,
    "requests_5xx": 0,
}

# Paths that bypass auth and rate limiting.
_PUBLIC_PATHS: frozenset[str] = frozenset(
    {
        "/health/live",
        "/health/ready",
        "/favicon.ico",
        "/metrics",
    }
)


# ---------------------------------------------------------------------------
# Security headers (Blocker #6: CSP added)
# ---------------------------------------------------------------------------


class SecurityHeadersMiddleware:
    """Add security headers including Content-Security-Policy to every response."""

    def __init__(self, app: Any) -> None:
        self.app = app
        self._allow_framing = os.getenv("FLOWBOARD_ALLOW_FRAMING", "").lower() in (
            "1",
            "true",
            "yes",
        )
        # NOTE: 'unsafe-inline' is retained for script-src and style-src because
        # the app generates self-contained HTML with inline CSS/JS and adding
        # nonces to every tag is impractical.  XSS is mitigated via Jinja2
        # autoescape and the _esc() output-escaping helper.  base-uri and
        # form-action are locked down as additional hardening.
        self._csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "img-src 'self' data:; "
            "font-src 'self' data: https://fonts.gstatic.com; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-content-type-options", b"nosniff"))
                headers.append((b"referrer-policy", b"strict-origin-when-cross-origin"))
                headers.append((b"x-xss-protection", b"1; mode=block"))
                headers.append((b"content-security-policy", self._csp.encode()))
                if not self._allow_framing:
                    headers.append((b"x-frame-options", b"DENY"))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)


# ---------------------------------------------------------------------------
# Correlation ID (Improvement #17)
# ---------------------------------------------------------------------------


class CorrelationIdMiddleware:
    """Propagate or generate X-Request-ID for request tracing."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Extract or generate correlation ID
        headers = dict(scope.get("headers", []))
        request_id = (headers.get(b"x-request-id", b"") or b"").decode() or str(uuid.uuid4())[:8]
        scope["state"] = scope.get("state", {})
        scope["state"]["request_id"] = request_id

        async def send_with_id(message: dict) -> None:
            if message["type"] == "http.response.start":
                resp_headers = list(message.get("headers", []))
                resp_headers.append((b"x-request-id", request_id.encode()))
                message["headers"] = resp_headers
            await send(message)

        await self.app(scope, receive, send_with_id)


# ---------------------------------------------------------------------------
# Request logging (Blocker #23: structured logging)
# ---------------------------------------------------------------------------


class RequestLoggingMiddleware:
    """Log every HTTP request with structured key=value pairs."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.monotonic()
        path = scope.get("path", "/")
        method = scope.get("method", "?")
        status_code = 0

        async def send_wrapper(message: dict) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 0)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = round((time.monotonic() - start) * 1000, 1)
            _log.info(
                'method=%s path="%s" status=%s duration_ms=%.1f',
                method,
                path,
                status_code,
                duration_ms,
                extra={"request_path": path, "duration_ms": duration_ms},
            )
            _metrics["requests_total"] += 1
            if 400 <= status_code < 500:
                _metrics["requests_4xx"] += 1
            elif status_code >= 500:
                _metrics["requests_5xx"] += 1


# ---------------------------------------------------------------------------
# Bearer-token authentication (Blocker #2)
# ---------------------------------------------------------------------------


class AuthMiddleware:
    """Optional bearer-token authentication.

    Enable by setting ``FLOWBOARD_API_TOKEN``.  When set, requests must
    include ``Authorization: Bearer <token>`` or a ``fb_token`` cookie.
    Health-check paths are always public.
    """

    def __init__(self, app: Any) -> None:
        self.app = app
        self._token = os.getenv("FLOWBOARD_API_TOKEN", "").strip()
        if self._token:
            _log.info("Authentication enabled (FLOWBOARD_API_TOKEN is set)")

    @property
    def enabled(self) -> bool:
        return bool(self._token)

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http" or not self._token:
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "/")
        if path in _PUBLIC_PATHS:
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))

        # Check Authorization header
        auth_header = headers.get(b"authorization", b"").decode()
        if auth_header.startswith("Bearer ") and hmac.compare_digest(auth_header[7:], self._token):
            await self.app(scope, receive, send)
            return

        # Check cookie fallback (for browser access)
        for part in headers.get(b"cookie", b"").decode().split(";"):
            part = part.strip()
            if part.startswith("fb_token=") and hmac.compare_digest(part[9:], self._token):
                await self.app(scope, receive, send)
                return

        _log.warning("Unauthorized request to %s", path)
        body = b'{"ok":false,"error":"Authentication required"}'
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"www-authenticate", b"Bearer"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


# ---------------------------------------------------------------------------
# CSRF protection (Blocker #1)
# ---------------------------------------------------------------------------


class CSRFMiddleware:
    """Require ``X-Requested-With: FlowBoard`` on state-changing requests.

    GET/HEAD/OPTIONS are exempt.  This prevents cross-origin POST attacks
    because browsers will not add custom headers without a CORS preflight.
    """

    _SAFE_METHODS: frozenset[str] = frozenset({"GET", "HEAD", "OPTIONS"})
    _REQUIRED_HEADER = b"x-requested-with"
    _REQUIRED_VALUE = "flowboard"

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET")
        if method in self._SAFE_METHODS:
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        xrw = headers.get(self._REQUIRED_HEADER, b"").decode().lower()
        if xrw == self._REQUIRED_VALUE:
            await self.app(scope, receive, send)
            return

        _log.warning("CSRF check failed for %s %s", method, scope.get("path", "/"))
        body = b'{"ok":false,"error":"Missing X-Requested-With header"}'
        await send(
            {
                "type": "http.response.start",
                "status": 403,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": body})


# ---------------------------------------------------------------------------
# Rate limiting (Blocker #4)
# ---------------------------------------------------------------------------


_MAX_BODY_SIZE = int(os.getenv("FLOWBOARD_MAX_BODY_SIZE", str(1024 * 1024)))  # 1 MB default


class BodySizeLimitMiddleware:
    """Reject request bodies exceeding the configured size limit."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET")
        if method in ("GET", "HEAD", "OPTIONS"):
            await self.app(scope, receive, send)
            return

        content_length = 0
        for header_name, header_value in scope.get("headers", []):
            if header_name == b"content-length":
                with contextlib.suppress(ValueError, TypeError):
                    content_length = int(header_value)
                break

        if content_length > _MAX_BODY_SIZE:
            body = b'{"ok":false,"error":"Request body too large"}'
            await send({
                "type": "http.response.start",
                "status": 413,
                "headers": [(b"content-type", b"application/json")],
            })
            await send({"type": "http.response.body", "body": body})
            return

        await self.app(scope, receive, send)


class RateLimitMiddleware:
    """Simple in-memory sliding-window rate limiter per client IP.

    Defaults: 60 requests per minute.  Override with ``FLOWBOARD_RATE_LIMIT``
    and ``FLOWBOARD_RATE_WINDOW`` env vars.
    """

    def __init__(self, app: Any) -> None:
        self.app = app
        self._limit = int(os.getenv("FLOWBOARD_RATE_LIMIT", "60"))
        self._window = int(os.getenv("FLOWBOARD_RATE_WINDOW", "60"))
        self._requests: dict[str, list[float]] = {}
        self._cleanup_counter = 0

    def _client_ip(self, scope: dict) -> str:
        client = scope.get("client")
        return client[0] if client else "unknown"

    def _is_rate_limited(self, ip: str) -> bool:
        now = time.monotonic()
        cutoff = now - self._window
        timestamps = self._requests.get(ip, [])
        fresh = [t for t in timestamps if t > cutoff]
        if len(fresh) >= self._limit:
            self._requests[ip] = fresh
            return True
        fresh.append(now)
        self._requests[ip] = fresh
        # Periodic cleanup of stale IPs (every 200 requests)
        self._cleanup_counter += 1
        if self._cleanup_counter >= 200:
            self._cleanup_counter = 0
            stale_ips = [k for k, v in self._requests.items() if not v or v[-1] < cutoff]
            for k in stale_ips:
                del self._requests[k]
        return False

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "/")
        if path in _PUBLIC_PATHS:
            await self.app(scope, receive, send)
            return

        ip = self._client_ip(scope)
        if self._is_rate_limited(ip):
            body = b'{"ok":false,"error":"Rate limit exceeded"}'
            await send(
                {
                    "type": "http.response.start",
                    "status": 429,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"retry-after", str(self._window).encode()),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return

        await self.app(scope, receive, send)
