"""Low-level HTTP client for the Jira REST API.

This module handles authentication, pagination, rate-limit back-off,
and error translation.  It exposes a minimal surface that the higher-level
:mod:`connector` consumes.

SSL/TLS
-------
The session is configured with corporate-network-aware CA bundle resolution
via :func:`flowboard.shared.network.configure_session_ssl`.  This ensures
FlowBoard works behind corporate proxies (Zscaler, Netskope, etc.) that
use custom CA certificates.

Set ``SSL_CERT_FILE`` or ``REQUESTS_CA_BUNDLE`` to point to your corporate
CA bundle if the default resolution doesn't work.
"""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Iterator
from typing import Any

import requests

from flowboard.infrastructure.config.loader import JiraConfig
from flowboard.shared.network import configure_session_ssl
from flowboard.shared.utils import mask_secret

logger = logging.getLogger(__name__)

_BACKOFF_CODES = {429, 502, 503, 504}
_MAX_RETRIES = 3
_MAX_BACKOFF_SECONDS = 30
_REQUEST_TIMEOUT = (10, 60)  # (connect, read) in seconds


class JiraAuthError(Exception):
    """Raised on 401/403 from the Jira API."""

    def __init__(self, status_code: int, message: str | None = None):
        self.status_code = status_code
        super().__init__(message or f"Authentication failed ({status_code})")


class JiraApiError(Exception):
    """Raised on unexpected Jira API errors."""

    def __init__(self, status_code: int = 0, detail: str = "", message: str | None = None):
        self.status_code = status_code
        self.detail = detail
        super().__init__(message or f"Jira API error {status_code}: {detail}")


class JiraClient:
    """Thin wrapper around the Jira REST & Agile APIs."""

    def __init__(self, config: JiraConfig) -> None:
        if not config.base_url:
            raise ValueError("jira_base_url_required")
        self._base = config.base_url.rstrip("/")
        self._max_results = config.max_results
        self._session = requests.Session()
        self._session.headers["Accept"] = "application/json"

        # Configure SSL for corporate proxy environments (Zscaler, Netskope).
        # Resolves the correct CA bundle automatically.
        configure_session_ssl(self._session)

        if config.auth_email and config.auth_token:
            self._session.auth = (config.auth_email, config.auth_token)
            logger.info(
                "Jira auth configured (email=%s, token=…%s)",
                config.auth_email,
                mask_secret(config.auth_token),
            )
        elif config.auth_token:
            self._session.headers["Authorization"] = f"Bearer {config.auth_token}"
            logger.info("Jira auth configured (Bearer token=…%s)", mask_secret(config.auth_token))
        else:
            logger.warning("No Jira auth credentials provided — requests may fail.")

    def close(self) -> None:
        """Close the underlying HTTP session."""
        self._session.close()

    def __enter__(self) -> JiraClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", _REQUEST_TIMEOUT)
        last_exc: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                resp = self._session.request(method, url, **kwargs)
            except (requests.ConnectionError, requests.Timeout) as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    wait = min(2**attempt + random.uniform(0, 1), _MAX_BACKOFF_SECONDS)
                    logger.warning(
                        "Transient network error (%s), retrying in %.1fs… (attempt %d/%d)",
                        type(exc).__name__,
                        wait,
                        attempt,
                        _MAX_RETRIES,
                    )
                    time.sleep(wait)
                    continue
                raise JiraApiError(
                    message=f"Network error after {_MAX_RETRIES} retries: {exc}"
                ) from exc

            if resp.status_code in (401, 403):
                raise JiraAuthError(resp.status_code)
            if resp.status_code in _BACKOFF_CODES and attempt < _MAX_RETRIES:
                try:
                    retry_after = float(resp.headers.get("Retry-After", 2**attempt))
                except (ValueError, TypeError):
                    retry_after = float(2**attempt)
                wait = min(
                    retry_after + random.uniform(0, 1),
                    _MAX_BACKOFF_SECONDS,
                )
                logger.warning("Rate-limited (%s), retrying in %.1fs…", resp.status_code, wait)
                time.sleep(wait)
                continue
            if not resp.ok:
                detail = f"HTTP {resp.status_code}"
                if resp.status_code in _BACKOFF_CODES:
                    detail += f" (after {_MAX_RETRIES} retries)"
                logger.debug(
                    "Jira API error response (HTTP %s): %s", resp.status_code, resp.text[:500]
                )
                raise JiraApiError(resp.status_code, detail)
            return resp
        if last_exc:
            raise JiraApiError(message=f"Max retries exceeded: {last_exc}") from last_exc
        raise JiraApiError(message="Max retries exceeded for Jira API request.")

    def _get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        resp = self._request("GET", url, params=params)
        try:
            return resp.json()
        except (ValueError, requests.exceptions.JSONDecodeError) as exc:
            snippet = resp.text[:200] if resp.text else "(empty body)"
            raise JiraApiError(
                resp.status_code,
                f"Expected JSON but received non-JSON response: {snippet}",
            ) from exc

    # ------------------------------------------------------------------
    # REST v2 helpers
    # ------------------------------------------------------------------

    def search_issues(self, jql: str, fields: list[str] | None = None) -> Iterator[dict[str, Any]]:
        """Paginate through ``/rest/api/2/search`` results."""
        start = 0
        max_pages = 500  # safety limit: 500 pages x 100 results = 50k issues max
        total_reported = 0
        for _ in range(max_pages):
            params: dict[str, Any] = {
                "jql": jql,
                "startAt": start,
                "maxResults": self._max_results,
            }
            if fields:
                params["fields"] = ",".join(fields)
            data = self._get_json(f"{self._base}/rest/api/2/search", params=params)
            issues: list[dict[str, Any]] = data.get("issues", [])
            total_reported = data.get("total", 0)
            yield from issues
            start += len(issues)
            if start >= total_reported or not issues:
                break
        else:
            # Blocker #17: warn clearly when pagination limit is reached
            logger.warning(
                "Pagination safety limit reached (%d pages, %d/%d issues fetched). "
                "Results are TRUNCATED — consider narrowing the JQL filter.",
                max_pages,
                start,
                total_reported,
            )

    def get_issue(self, key: str) -> dict[str, Any]:
        return self._get_json(f"{self._base}/rest/api/2/issue/{key}")

    # ------------------------------------------------------------------
    # Agile API helpers
    # ------------------------------------------------------------------

    def get_boards(self) -> list[dict[str, Any]]:
        all_boards: list[dict[str, Any]] = []
        start = 0
        max_pages = 50
        for _ in range(max_pages):
            data = self._get_json(
                f"{self._base}/rest/agile/1.0/board",
                params={"startAt": start, "maxResults": 50},
            )
            values = data.get("values", [])
            all_boards.extend(values)
            start += len(values)
            if data.get("isLast", True) or not values:
                break
        else:
            logger.warning("Board pagination safety limit reached (%d pages).", max_pages)
        return all_boards

    def get_sprints(self, board_id: int) -> list[dict[str, Any]]:
        all_sprints: list[dict[str, Any]] = []
        start = 0
        max_pages = 200
        for _ in range(max_pages):
            data = self._get_json(
                f"{self._base}/rest/agile/1.0/board/{board_id}/sprint",
                params={"startAt": start, "maxResults": 50},
            )
            values = data.get("values", [])
            all_sprints.extend(values)
            start += len(values)
            if data.get("isLast", True) or not values:
                break
        else:
            logger.warning(
                "Sprint pagination safety limit reached for board %s (%d pages).",
                board_id,
                max_pages,
            )
        return all_sprints

    def get_sprint_issues(self, sprint_id: int) -> list[dict[str, Any]]:
        all_issues: list[dict[str, Any]] = []
        start = 0
        max_pages = 500
        for _ in range(max_pages):
            data = self._get_json(
                f"{self._base}/rest/agile/1.0/sprint/{sprint_id}/issue",
                params={"startAt": start, "maxResults": self._max_results},
            )
            issues = data.get("issues", [])
            all_issues.extend(issues)
            start += len(issues)
            if start >= data.get("total", 0) or not issues:
                break
        else:
            logger.warning(
                "Sprint issue pagination safety limit reached for sprint %s (%d pages).",
                sprint_id,
                max_pages,
            )
        return all_issues

    def verify_connection(self) -> dict[str, Any]:
        """Quick server-info call to verify connectivity and auth."""
        return self._get_json(f"{self._base}/rest/api/2/serverInfo")
