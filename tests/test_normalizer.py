"""Tests for Jira data normalisation."""

from __future__ import annotations

import pytest

from flowboard.infrastructure.config.loader import FlowBoardConfig
from flowboard.infrastructure.jira.normalizer import JiraNormalizer
from flowboard.shared.types import IssueType, LinkType, SprintState, StatusCategory


@pytest.fixture()
def normalizer(config: FlowBoardConfig) -> JiraNormalizer:
    return JiraNormalizer(config)


class TestNormalizeIssue:
    """Tests for normalize issue."""

    """GIVEN normalize issue and the scenario: basic fields"""
    def test_basic_fields(self, normalizer: JiraNormalizer) -> None:
        """WHEN the code under test is exercised for: basic fields"""
        raw = {
            "key": "TEST-1",
            "fields": {
                "summary": "Fix the thing",
                "issuetype": {"name": "Bug"},
                "status": {"name": "In Progress"},
                "priority": {"name": "High"},
                "customfield_10016": 5,
                "project": {"key": "TEST"},
                "created": "2026-03-01T10:00:00+00:00",
                "issuelinks": [],
            },
        }
        issue = normalizer.normalize_issue(raw)

        """THEN the expected behaviour holds: basic fields"""
        assert issue.key == "TEST-1"
        assert issue.issue_type == IssueType.BUG
        assert issue.status_category == StatusCategory.IN_PROGRESS
        assert issue.story_points == 5.0
        assert issue.project_key == "TEST"

    """GIVEN normalize issue and the scenario: assignee normalised"""
    def test_assignee_normalised(self, normalizer: JiraNormalizer) -> None:
        """WHEN the code under test is exercised for: assignee normalised"""
        raw = {
            "key": "TEST-2",
            "fields": {
                "summary": "Assigned task",
                "issuetype": {"name": "Task"},
                "status": {"name": "To Do"},
                "assignee": {"accountId": "u1", "displayName": "Alice", "emailAddress": "a@co.com"},
                "issuelinks": [],
            },
        }
        issue = normalizer.normalize_issue(raw)

        """THEN the expected behaviour holds: assignee normalised"""
        assert issue.assignee is not None
        assert issue.assignee.display_name == "Alice"
        assert issue.assignee.team == "alpha"  # from config fixture

    """GIVEN normalize issue and the scenario: missing story points defaults to zero"""
    def test_missing_story_points_defaults_to_zero(self, normalizer: JiraNormalizer) -> None:
        """WHEN the code under test is exercised for: missing story points defaults to zero"""
        raw = {
            "key": "TEST-3",
            "fields": {
                "summary": "No points",
                "issuetype": {"name": "Story"},
                "status": {"name": "Open"},
                "issuelinks": [],
            },
        }
        issue = normalizer.normalize_issue(raw)

        """THEN the expected behaviour holds: missing story points defaults to zero"""
        assert issue.story_points == 0.0

    """GIVEN normalize issue and the scenario: links are parsed"""
    def test_links_are_parsed(self, normalizer: JiraNormalizer) -> None:
        """WHEN the code under test is exercised for: links are parsed"""
        raw = {
            "key": "TEST-4",
            "fields": {
                "summary": "Blocked task",
                "issuetype": {"name": "Story"},
                "status": {"name": "To Do"},
                "issuelinks": [
                    {
                        "type": {"inward": "is blocked by", "outward": "blocks"},
                        "inwardIssue": {
                            "key": "TEST-5",
                            "fields": {"summary": "Blocker", "status": {"name": "In Progress"}},
                        },
                    }
                ],
            },
        }
        issue = normalizer.normalize_issue(raw)

        """THEN the expected behaviour holds: links are parsed"""
        assert len(issue.links) == 1
        assert issue.links[0].link_type == LinkType.IS_BLOCKED_BY
        assert issue.links[0].target_key == "TEST-5"
        assert not issue.links[0].is_resolved


class TestNormalizeSprint:
    """GIVEN normalize sprint and the scenario: sprint fields"""
    def test_sprint_fields(self, normalizer: JiraNormalizer) -> None:
        """WHEN the code under test is exercised for: sprint fields"""
        raw = {
            "id": 42,
            "name": "Sprint 5",
            "state": "active",
            "startDate": "2026-03-01T00:00:00+00:00",
            "endDate": "2026-03-15T00:00:00+00:00",
            "goal": "Ship auth",
        }
        sprint = normalizer.normalize_sprint(raw)

        """THEN the expected behaviour holds: sprint fields"""
        assert sprint.id == 42
        assert sprint.state == SprintState.ACTIVE
        assert sprint.goal == "Ship auth"


class TestNormalizeBulk:
    """GIVEN normalize bulk and the scenario: normalize mock payload"""
    def test_normalize_mock_payload(self, mock_jira_payload: dict, config: FlowBoardConfig) -> None:
        """WHEN the code under test is exercised for: normalize mock payload"""
        norm = JiraNormalizer(config)
        issues = norm.normalize_issues(mock_jira_payload["issues"])
        sprints = norm.normalize_sprints(mock_jira_payload["sprints"])

        """THEN the expected behaviour holds: normalize mock payload"""
        assert len(issues) == 20
        assert len(sprints) == 3
        # People cache should be populated
        people = norm.get_all_people()
        assert len(people) >= 5

    """GIVEN normalize bulk and the scenario: roadmap items from epics"""
    def test_roadmap_items_from_epics(
        self, mock_jira_payload: dict, config: FlowBoardConfig
    ) -> None:
        """WHEN the code under test is exercised for: roadmap items from epics"""
        norm = JiraNormalizer(config)
        issues = norm.normalize_issues(mock_jira_payload["issues"])
        roadmap = norm.build_roadmap_items(issues)

        """THEN the expected behaviour holds: roadmap items from epics"""
        assert len(roadmap) == 3  # 3 epics in mock data
        # Epic PROJ-1 has children PROJ-2, PROJ-3, PROJ-4
        auth_epic = next(r for r in roadmap if r.key == "PROJ-1")
        assert auth_epic.child_count == 3
        assert auth_epic.done_count == 1  # PROJ-4 is Done

    """GIVEN normalize bulk and the scenario: dependencies extracted"""
    def test_dependencies_extracted(self, mock_jira_payload: dict, config: FlowBoardConfig) -> None:
        """WHEN the code under test is exercised for: dependencies extracted"""
        norm = JiraNormalizer(config)
        issues = norm.normalize_issues(mock_jira_payload["issues"])
        deps = norm.extract_dependencies(issues)

        """THEN the expected behaviour holds: dependencies extracted"""
        assert len(deps) > 0
        blocked_keys = {d.source_key for d in deps}
        assert "PROJ-3" in blocked_keys  # PROJ-3 is blocked by PROJ-2
