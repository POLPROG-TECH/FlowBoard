"""High-level Jira data connector.

Orchestrates the :class:`JiraClient` to fetch and assemble raw Jira data
for a given configuration (projects, boards, sprints, JQL).
"""

from __future__ import annotations

import logging
from typing import Any

import requests

from flowboard.infrastructure.config.loader import FlowBoardConfig
from flowboard.infrastructure.jira.client import JiraApiError, JiraAuthError, JiraClient

logger = logging.getLogger(__name__)


class JiraConnector:
    """Fetches raw Jira data according to config and exposes it as plain dicts."""

    def __init__(self, client: JiraClient, config: FlowBoardConfig) -> None:
        self._client = client
        self._config = config

    # ------------------------------------------------------------------
    # Public fetch methods
    # ------------------------------------------------------------------

    def fetch_all(self) -> dict[str, Any]:
        """Return a combined payload with issues, sprints, and boards."""
        issues = self._fetch_issues()
        sprints = self._fetch_sprints()
        return {
            "issues": issues,
            "sprints": sprints,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_jql(self) -> str:
        import re

        parts: list[str] = []
        projects = self._config.jira.projects
        if projects:
            safe_keys: list[str] = []
            for p in projects:
                if re.match(r"^[A-Za-z][A-Za-z0-9_]{0,255}$", p):
                    safe_keys.append(f'"{p}"')
                else:
                    logger.warning("Skipping invalid project key for JQL: %r", p)
            if safe_keys:
                parts.append(f"project in ({', '.join(safe_keys)})")
        jql_filter = self._config.jira.jql_filter
        if jql_filter:
            # Blocker #13: sanitize JQL filter — reject obviously dangerous patterns
            forbidden_jql = re.compile(
                r"(;|--|\bdrop\b|\bdelete\b|\binsert\b|\bupdate\b|\balter\b)",
                re.IGNORECASE,
            )
            if forbidden_jql.search(jql_filter):
                logger.error(
                    "JQL filter contains forbidden SQL-like pattern, ignoring: %r", jql_filter
                )
            else:
                parts.append(f"({jql_filter})")
        return " AND ".join(parts) if parts else ""

    def _fetch_issues(self) -> list[dict[str, Any]]:
        jql = self._build_jql()
        if not jql:
            logger.warning("No JQL filter — fetching all accessible issues.")
            jql = "ORDER BY updated DESC"
        else:
            jql += " ORDER BY updated DESC"
        logger.info("Fetching issues with JQL: %s", jql)
        return list(self._client.search_issues(jql))

    def _fetch_sprints(self) -> list[dict[str, Any]]:
        boards = self._config.jira.boards
        if not boards:
            all_boards = self._client.get_boards()
            project_keys = set(self._config.jira.projects)
            if project_keys:
                boards = [
                    b.get("id")
                    for b in all_boards
                    if b.get("id") is not None
                    and b.get("location", {}).get("projectKey") in project_keys
                ]
            else:
                boards = [b.get("id") for b in all_boards if b.get("id") is not None]

        all_sprints: list[dict[str, Any]] = []
        for bid in boards:
            try:
                all_sprints.extend(self._client.get_sprints(bid))
            except JiraAuthError:
                raise
            except (JiraApiError, requests.RequestException, ValueError):
                logger.warning("Could not fetch sprints for board %s", bid, exc_info=True)
        # Deduplicate by sprint id.
        seen: set[int] = set()
        unique: list[dict[str, Any]] = []
        for s in all_sprints:
            sid = s.get("id")
            if sid is not None and sid not in seen:
                seen.add(sid)
                unique.append(s)
            elif sid is None:
                logger.warning(
                    "Sprint with no ID encountered, including anyway: %s", s.get("name", "unknown")
                )
                unique.append(s)
        return unique
