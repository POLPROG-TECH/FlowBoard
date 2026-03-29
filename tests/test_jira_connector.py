"""Tests for the Jira client (mocked HTTP)."""

from __future__ import annotations

import pytest
import responses

from flowboard.infrastructure.config.loader import JiraConfig
from flowboard.infrastructure.jira.client import JiraAuthError, JiraClient


@pytest.fixture()
def jira_config() -> JiraConfig:
    return JiraConfig(
        base_url="https://test.atlassian.net",
        auth_token="test-token",
        auth_email="test@co.com",
        max_results=10,
    )


class TestJiraClient:
    @responses.activate
    def test_search_issues_paginates(self, jira_config: JiraConfig) -> None:
        # GIVEN two pages of results
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/2/search",
            json={"issues": [{"key": "T-1"}], "total": 2, "startAt": 0},
        )
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/2/search",
            json={"issues": [{"key": "T-2"}], "total": 2, "startAt": 1},
        )
        client = JiraClient(jira_config)

        # WHEN
        issues = list(client.search_issues("project = TEST"))

        # THEN both pages fetched
        assert len(issues) == 2
        assert issues[0]["key"] == "T-1"
        assert issues[1]["key"] == "T-2"

    @responses.activate
    def test_auth_error_raises(self, jira_config: JiraConfig) -> None:
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/2/serverInfo",
            status=401,
        )
        client = JiraClient(jira_config)
        with pytest.raises(JiraAuthError):
            client.verify_connection()

    @responses.activate
    def test_verify_connection_success(self, jira_config: JiraConfig) -> None:
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/2/serverInfo",
            json={
                "baseUrl": "https://test.atlassian.net",
                "version": "9.0",
                "serverTitle": "Test Jira",
            },
        )
        client = JiraClient(jira_config)
        info = client.verify_connection()
        assert info["version"] == "9.0"

    def test_missing_base_url_raises(self) -> None:
        with pytest.raises(ValueError, match="base_url"):
            JiraClient(JiraConfig())
