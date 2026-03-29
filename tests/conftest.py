"""Shared pytest fixtures for FlowBoard tests."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from flowboard.domain.models import (
    Issue,
    IssueLink,
    Person,
    Sprint,
    Team,
)
from flowboard.infrastructure.config.loader import (
    FlowBoardConfig,
    load_config_from_dict,
)
from flowboard.shared.types import (
    IssueStatus,
    IssueType,
    LinkType,
    Priority,
    SprintState,
    StatusCategory,
)

FIXTURES_DIR = Path(__file__).parent.parent / "examples" / "fixtures"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@pytest.fixture()
def minimal_config_dict() -> dict:
    return {
        "jira": {"base_url": "https://test.atlassian.net"},
    }


@pytest.fixture()
def full_config_dict() -> dict:
    return {
        "jira": {
            "base_url": "https://test.atlassian.net",
            "auth_token": "tok-123",
            "auth_email": "test@co.com",
            "projects": ["PROJ"],
            "max_results": 50,
        },
        "teams": [
            {"key": "alpha", "name": "Alpha", "members": ["u1", "u2"]},
            {"key": "beta", "name": "Beta", "members": ["u3"]},
        ],
        "thresholds": {"overload_points": 15, "aging_days": 10},
        "output": {"path": "/tmp/test_dashboard.html", "title": "Test Board"},
    }


@pytest.fixture()
def config(full_config_dict: dict) -> FlowBoardConfig:
    return load_config_from_dict(full_config_dict)


# ---------------------------------------------------------------------------
# People & Teams
# ---------------------------------------------------------------------------


@pytest.fixture()
def alice() -> Person:
    return Person(account_id="u1", display_name="Alice", email="alice@co.com", team="alpha")


@pytest.fixture()
def bob() -> Person:
    return Person(account_id="u2", display_name="Bob", email="bob@co.com", team="alpha")


@pytest.fixture()
def carol() -> Person:
    return Person(account_id="u3", display_name="Carol", email="carol@co.com", team="beta")


@pytest.fixture()
def team_alpha(alice: Person, bob: Person) -> Team:
    return Team(key="alpha", name="Alpha", members=(alice.account_id, bob.account_id))


@pytest.fixture()
def team_beta(carol: Person) -> Team:
    return Team(key="beta", name="Beta", members=(carol.account_id,))


# ---------------------------------------------------------------------------
# Sprints
# ---------------------------------------------------------------------------


@pytest.fixture()
def active_sprint() -> Sprint:
    return Sprint(
        id=100,
        name="Sprint 10",
        state=SprintState.ACTIVE,
        start_date=date(2026, 3, 3),
        end_date=date(2026, 3, 17),
    )


# ---------------------------------------------------------------------------
# Issues
# ---------------------------------------------------------------------------


def _make_issue(
    key: str = "TEST-1",
    summary: str = "Test issue",
    issue_type: IssueType = IssueType.STORY,
    status_category: StatusCategory = StatusCategory.TODO,
    assignee: Person | None = None,
    story_points: float = 0.0,
    priority: Priority = Priority.MEDIUM,
    sprint: Sprint | None = None,
    epic_key: str = "",
    created: datetime | None = None,
    links: list[IssueLink] | None = None,
    due_date: date | None = None,
) -> Issue:
    return Issue(
        key=key,
        summary=summary,
        issue_type=issue_type,
        status=IssueStatus.OTHER,
        status_category=status_category,
        assignee=assignee,
        story_points=story_points,
        priority=priority,
        sprint=sprint,
        epic_key=epic_key,
        created=created or datetime(2026, 3, 1, tzinfo=UTC),
        links=links or [],
        due_date=due_date,
    )


@pytest.fixture()
def make_issue():
    """Factory fixture for creating test issues."""
    return _make_issue


@pytest.fixture()
def sample_issues(alice: Person, bob: Person, carol: Person, active_sprint: Sprint) -> list[Issue]:
    """A set of 8 issues with a realistic mix of types, statuses, and assignments."""
    return [
        _make_issue(
            "P-1",
            "Epic Alpha",
            IssueType.EPIC,
            StatusCategory.IN_PROGRESS,
            alice,
            0,
            Priority.HIGH,
            due_date=date(2026, 4, 1),
        ),
        _make_issue(
            "P-2",
            "Story A",
            IssueType.STORY,
            StatusCategory.IN_PROGRESS,
            alice,
            8,
            Priority.HIGH,
            active_sprint,
            "P-1",
        ),
        _make_issue(
            "P-3",
            "Story B",
            IssueType.STORY,
            StatusCategory.TODO,
            bob,
            13,
            Priority.HIGH,
            active_sprint,
            "P-1",
            links=[IssueLink("P-2", LinkType.IS_BLOCKED_BY, is_resolved=False)],
        ),
        _make_issue(
            "P-4",
            "Bug fix",
            IssueType.BUG,
            StatusCategory.DONE,
            alice,
            3,
            Priority.HIGHEST,
            active_sprint,
            "P-1",
        ),
        _make_issue(
            "P-5",
            "Story C",
            IssueType.STORY,
            StatusCategory.IN_PROGRESS,
            carol,
            5,
            Priority.MEDIUM,
            active_sprint,
        ),
        _make_issue(
            "P-6",
            "Task X",
            IssueType.TASK,
            StatusCategory.TODO,
            bob,
            5,
            Priority.LOW,
            active_sprint,
        ),
        _make_issue(
            "P-7",
            "Story D",
            IssueType.STORY,
            StatusCategory.DONE,
            carol,
            5,
            Priority.MEDIUM,
            active_sprint,
        ),
        _make_issue(
            "P-8",
            "Task Y",
            IssueType.TASK,
            StatusCategory.IN_PROGRESS,
            alice,
            3,
            Priority.HIGH,
            active_sprint,
        ),
    ]


# ---------------------------------------------------------------------------
# Raw Jira payload (from fixture file)
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_jira_payload() -> dict:
    with (FIXTURES_DIR / "mock_jira_data.json").open() as f:
        return json.load(f)
