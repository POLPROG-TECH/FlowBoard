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
    """GIVEN jira client and the scenario: search issues paginates"""

    @responses.activate
    def test_search_issues_paginates(self, jira_config: JiraConfig) -> None:
        """WHEN the code under test is exercised for: search issues paginates"""
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

        issues = list(client.search_issues("project = TEST"))

        """THEN the expected behaviour holds: search issues paginates"""
        assert len(issues) == 2
        assert issues[0]["key"] == "T-1"
        assert issues[1]["key"] == "T-2"

    """GIVEN jira client and the scenario: auth error raises"""

    @responses.activate
    def test_auth_error_raises(self, jira_config: JiraConfig) -> None:
        """WHEN the code under test is exercised for: auth error raises"""
        responses.add(
            responses.GET,
            "https://test.atlassian.net/rest/api/2/serverInfo",
            status=401,
        )
        client = JiraClient(jira_config)
        with pytest.raises(JiraAuthError):
            client.verify_connection()

    """GIVEN jira client and the scenario: verify connection success"""

    @responses.activate
    def test_verify_connection_success(self, jira_config: JiraConfig) -> None:
        """WHEN the code under test is exercised for: verify connection success"""
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

        """THEN the expected behaviour holds: verify connection success"""
        assert info["version"] == "9.0"

    """GIVEN jira client and the scenario: missing base url raises"""
    def test_missing_base_url_raises(self) -> None:
        """WHEN the code under test is exercised for: missing base url raises"""
        with pytest.raises(ValueError, match="base_url"):
            JiraClient(JiraConfig())
