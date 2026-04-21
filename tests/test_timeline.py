"""Tests for domain/timeline.py - timeline data preparation."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from flowboard.domain.models import (
    BoardSnapshot,
    Issue,
    Person,
    RoadmapItem,
    Sprint,
    Team,
)
from flowboard.domain.timeline import (
    TimelineBar,
    TimelineData,
    TimelineMode,
    _detect_overlaps,
    _issue_date_range,
    build_assignee_timeline,
    build_conflict_timeline,
    build_epic_timeline,
    build_executive_timeline,
    build_team_timeline,
    build_timeline,
)
from flowboard.shared.types import (
    IssueType,
    Priority,
    SprintState,
    StatusCategory,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def people() -> list[Person]:
    return [
        Person(account_id="u1", display_name="Alice", team="Platform"),
        Person(account_id="u2", display_name="Bob", team="Platform"),
        Person(account_id="u3", display_name="Carol", team="Frontend"),
    ]


@pytest.fixture()
def sprint() -> Sprint:
    return Sprint(
        id=100,
        name="Sprint 12",
        state=SprintState.ACTIVE,
        start_date=date(2026, 3, 3),
        end_date=date(2026, 3, 17),
    )


@pytest.fixture()
def issues(people: list[Person], sprint: Sprint) -> list[Issue]:
    return [
        Issue(
            key="P-1",
            summary="Auth overhaul",
            issue_type=IssueType.STORY,
            status_category=StatusCategory.IN_PROGRESS,
            assignee=people[0],
            story_points=8,
            priority=Priority.HIGH,
            created=datetime(2026, 2, 15, tzinfo=UTC),
            due_date=date(2026, 3, 20),
            sprint=sprint,
        ),
        Issue(
            key="P-2",
            summary="MFA support",
            issue_type=IssueType.STORY,
            status_category=StatusCategory.TODO,
            assignee=people[0],  # Alice - overlaps with P-1
            story_points=13,
            priority=Priority.HIGH,
            created=datetime(2026, 3, 1, tzinfo=UTC),
            due_date=date(2026, 3, 25),
            sprint=sprint,
        ),
        Issue(
            key="P-3",
            summary="Fix login bug",
            issue_type=IssueType.BUG,
            status_category=StatusCategory.DONE,
            assignee=people[1],
            story_points=3,
            priority=Priority.HIGHEST,
            created=datetime(2026, 3, 5, tzinfo=UTC),
            due_date=date(2026, 3, 10),
            sprint=sprint,
        ),
        Issue(
            key="P-4",
            summary="Dashboard redesign",
            issue_type=IssueType.STORY,
            status_category=StatusCategory.IN_PROGRESS,
            assignee=people[2],
            story_points=5,
            priority=Priority.MEDIUM,
            created=datetime(2026, 3, 3, tzinfo=UTC),
            due_date=date(2026, 3, 28),
            sprint=sprint,
        ),
        Issue(
            key="P-5",
            summary="No dates issue",
            issue_type=IssueType.TASK,
            status_category=StatusCategory.TODO,
            assignee=people[1],
            story_points=2,
            priority=Priority.LOW,
            # No created/due_date - should be skipped
        ),
    ]


@pytest.fixture()
def roadmap_items(people: list[Person]) -> list[RoadmapItem]:
    return [
        RoadmapItem(
            key="E-1",
            title="Auth Initiative",
            team="Platform",
            owner=people[0],
            start_date=date(2026, 1, 15),
            target_date=date(2026, 4, 1),
            progress_pct=60.0,
            total_points=40,
        ),
        RoadmapItem(
            key="E-2",
            title="UI Refresh",
            team="Frontend",
            owner=people[2],
            start_date=date(2026, 2, 1),
            target_date=date(2026, 5, 1),
            progress_pct=25.0,
            total_points=30,
        ),
    ]


@pytest.fixture()
def snapshot(
    issues: list[Issue],
    sprint: Sprint,
    people: list[Person],
    roadmap_items: list[RoadmapItem],
) -> BoardSnapshot:
    return BoardSnapshot(
        issues=issues,
        sprints=[sprint],
        people=people,
        teams=[
            Team(key="platform", name="Platform", members=("u1", "u2")),
            Team(key="frontend", name="Frontend", members=("u3",)),
        ],
        roadmap_items=roadmap_items,
    )


# ---------------------------------------------------------------------------
# _issue_date_range
# ---------------------------------------------------------------------------


class TestIssueDateRange:
    """GIVEN issue date range and the scenario: created and due"""
    def test_created_and_due(self, issues: list[Issue]) -> None:
        """WHEN the code under test is exercised for: created and due"""
        rng = _issue_date_range(issues[0])

        """THEN the expected behaviour holds: created and due"""
        assert rng is not None
        assert rng[0] == date(2026, 2, 15)
        assert rng[1] == date(2026, 3, 20)

    """GIVEN issue date range and the scenario: no dates returns none"""
    def test_no_dates_returns_none(self, issues: list[Issue]) -> None:
        """THEN the expected behaviour holds: no dates returns none"""
        assert _issue_date_range(issues[4]) is None

    """GIVEN issue date range and the scenario: fallback to sprint dates"""
    def test_fallback_to_sprint_dates(self, sprint: Sprint) -> None:
        """WHEN the code under test is exercised for: fallback to sprint dates"""
        issue = Issue(
            key="X-1",
            summary="test",
            sprint=sprint,
            created=datetime(2026, 3, 5, tzinfo=UTC),
        )
        rng = _issue_date_range(issue)

        """THEN the expected behaviour holds: fallback to sprint dates"""
        assert rng is not None
        assert rng[1] == sprint.end_date

    """GIVEN issue date range and the scenario: end before start gets padded"""
    def test_end_before_start_gets_padded(self) -> None:
        """WHEN the code under test is exercised for: end before start gets padded"""
        issue = Issue(
            key="X-2",
            summary="test",
            created=datetime(2026, 3, 10, tzinfo=UTC),
            due_date=date(2026, 3, 5),  # before created
        )
        rng = _issue_date_range(issue)

        """THEN the expected behaviour holds: end before start gets padded"""
        assert rng is not None
        assert rng[1] == date(2026, 3, 24)  # 14 days after start


# ---------------------------------------------------------------------------
# _detect_overlaps
# ---------------------------------------------------------------------------


class TestDetectOverlaps:
    """GIVEN detect overlaps and the scenario: no overlap"""
    def test_no_overlap(self) -> None:
        """WHEN the code under test is exercised for: no overlap"""
        bars = [
            TimelineBar(
                key="A",
                label="A",
                assignee="X",
                team="",
                start=date(2026, 1, 1),
                end=date(2026, 1, 10),
            ),
            TimelineBar(
                key="B",
                label="B",
                assignee="X",
                team="",
                start=date(2026, 1, 15),
                end=date(2026, 1, 25),
            ),
        ]

        """THEN the expected behaviour holds: no overlap"""
        assert _detect_overlaps(bars, "X") == []

    """GIVEN detect overlaps and the scenario: overlap detected"""
    def test_overlap_detected(self) -> None:
        """WHEN the code under test is exercised for: overlap detected"""
        bars = [
            TimelineBar(
                key="A",
                label="A",
                assignee="X",
                team="",
                start=date(2026, 1, 1),
                end=date(2026, 1, 15),
            ),
            TimelineBar(
                key="B",
                label="B",
                assignee="X",
                team="",
                start=date(2026, 1, 10),
                end=date(2026, 1, 25),
            ),
        ]
        overlaps = _detect_overlaps(bars, "X")

        """THEN the expected behaviour holds: overlap detected"""
        assert len(overlaps) >= 1
        assert overlaps[0].severity == "medium"
        assert "A" in overlaps[0].bar_keys
        assert "B" in overlaps[0].bar_keys

    """GIVEN detect overlaps and the scenario: high severity for triple overlap"""
    def test_high_severity_for_triple_overlap(self) -> None:
        """WHEN the code under test is exercised for: high severity for triple overlap"""
        bars = [
            TimelineBar(
                key="A",
                label="A",
                assignee="X",
                team="",
                start=date(2026, 1, 1),
                end=date(2026, 1, 20),
            ),
            TimelineBar(
                key="B",
                label="B",
                assignee="X",
                team="",
                start=date(2026, 1, 5),
                end=date(2026, 1, 25),
            ),
            TimelineBar(
                key="C",
                label="C",
                assignee="X",
                team="",
                start=date(2026, 1, 10),
                end=date(2026, 1, 30),
            ),
        ]
        overlaps = _detect_overlaps(bars, "X")
        high_or_critical = [o for o in overlaps if o.severity in ("high", "critical")]

        """THEN the expected behaviour holds: high severity for triple overlap"""
        assert len(high_or_critical) >= 1

    """GIVEN detect overlaps and the scenario: single bar no overlap"""
    def test_single_bar_no_overlap(self) -> None:
        """WHEN the code under test is exercised for: single bar no overlap"""
        bars = [
            TimelineBar(
                key="A",
                label="A",
                assignee="X",
                team="",
                start=date(2026, 1, 1),
                end=date(2026, 1, 10),
            ),
        ]

        """THEN the expected behaviour holds: single bar no overlap"""
        assert _detect_overlaps(bars, "X") == []


# ---------------------------------------------------------------------------
# build_assignee_timeline
# ---------------------------------------------------------------------------


class TestAssigneeTimeline:
    """GIVEN assignee timeline and the scenario: groups by assignee"""
    def test_groups_by_assignee(self, snapshot: BoardSnapshot) -> None:
        """WHEN the code under test is exercised for: groups by assignee"""
        data = build_assignee_timeline(snapshot)

        """THEN the expected behaviour holds: groups by assignee"""
        assert data.mode == TimelineMode.ASSIGNEE
        names = {s.key for s in data.swimlanes}
        assert "Alice" in names
        assert "Bob" in names
        assert "Carol" in names

    """GIVEN assignee timeline and the scenario: detects alice overlap"""
    def test_detects_alice_overlap(self, snapshot: BoardSnapshot) -> None:
        """WHEN the code under test is exercised for: detects alice overlap"""
        data = build_assignee_timeline(snapshot)
        alice_lane = next(s for s in data.swimlanes if s.key == "Alice")

        """THEN the expected behaviour holds: detects alice overlap"""
        assert alice_lane.overlap_count >= 1
        assert len(alice_lane.bars) == 2

    """GIVEN assignee timeline and the scenario: date range covers all bars"""
    def test_date_range_covers_all_bars(self, snapshot: BoardSnapshot) -> None:
        """WHEN the code under test is exercised for: date range covers all bars"""
        data = build_assignee_timeline(snapshot)

        """THEN the expected behaviour holds: date range covers all bars"""
        assert data.total_days > 0
        assert data.range_start < data.range_end

    """GIVEN assignee timeline and the scenario: sprint boundaries"""
    def test_sprint_boundaries(self, snapshot: BoardSnapshot) -> None:
        """WHEN the code under test is exercised for: sprint boundaries"""
        data = build_assignee_timeline(snapshot)

        """THEN the expected behaviour holds: sprint boundaries"""
        assert len(data.sprint_boundaries) >= 1
        assert data.sprint_boundaries[0][0] == "Sprint 12"


# ---------------------------------------------------------------------------
# build_team_timeline
# ---------------------------------------------------------------------------


class TestTeamTimeline:
    """GIVEN team timeline and the scenario: groups by team"""
    def test_groups_by_team(self, snapshot: BoardSnapshot) -> None:
        """WHEN the code under test is exercised for: groups by team"""
        data = build_team_timeline(snapshot)

        """THEN the expected behaviour holds: groups by team"""
        assert data.mode == TimelineMode.TEAM
        names = {s.key for s in data.swimlanes}
        assert "Platform" in names
        assert "Frontend" in names


# ---------------------------------------------------------------------------
# build_epic_timeline
# ---------------------------------------------------------------------------


class TestEpicTimeline:
    """GIVEN epic timeline and the scenario: uses roadmap items"""
    def test_uses_roadmap_items(self, snapshot: BoardSnapshot) -> None:
        """WHEN the code under test is exercised for: uses roadmap items"""
        data = build_epic_timeline(snapshot)

        """THEN the expected behaviour holds: uses roadmap items"""
        assert data.mode == TimelineMode.EPIC
        keys = {s.key for s in data.swimlanes}
        assert "E-1" in keys
        assert "E-2" in keys

    """GIVEN epic timeline and the scenario: epic bar has progress"""
    def test_epic_bar_has_progress(self, snapshot: BoardSnapshot) -> None:
        """WHEN the code under test is exercised for: epic bar has progress"""
        data = build_epic_timeline(snapshot)
        e1_lane = next(s for s in data.swimlanes if s.key == "E-1")

        """THEN the expected behaviour holds: epic bar has progress"""
        assert e1_lane.bars[0].progress_pct == 60.0


# ---------------------------------------------------------------------------
# build_conflict_timeline
# ---------------------------------------------------------------------------


class TestConflictTimeline:
    """GIVEN conflict timeline and the scenario: only conflicting lanes"""
    def test_only_conflicting_lanes(self, snapshot: BoardSnapshot) -> None:
        """WHEN the code under test is exercised for: only conflicting lanes"""
        data = build_conflict_timeline(snapshot)

        """THEN the expected behaviour holds: only conflicting lanes"""
        assert data.mode == TimelineMode.CONFLICT
        for lane in data.swimlanes:
            assert lane.overlap_count > 0

    """GIVEN conflict timeline and the scenario: empty when no conflicts"""
    def test_empty_when_no_conflicts(self) -> None:
        """WHEN the code under test is exercised for: empty when no conflicts"""
        issue = Issue(
            key="X-1",
            summary="solo",
            assignee=Person("u1", "Solo Person"),
            created=datetime(2026, 1, 1, tzinfo=UTC),
            due_date=date(2026, 1, 10),
        )
        snap = BoardSnapshot(issues=[issue])
        data = build_conflict_timeline(snap)

        """THEN the expected behaviour holds: empty when no conflicts"""
        assert len(data.swimlanes) == 0


# ---------------------------------------------------------------------------
# build_executive_timeline
# ---------------------------------------------------------------------------


class TestExecutiveTimeline:
    """GIVEN executive timeline and the scenario: caps swimlanes"""
    def test_caps_swimlanes(self, snapshot: BoardSnapshot) -> None:
        """WHEN the code under test is exercised for: caps swimlanes"""
        data = build_executive_timeline(snapshot)

        """THEN the expected behaviour holds: caps swimlanes"""
        assert data.mode == TimelineMode.EXECUTIVE
        assert len(data.swimlanes) <= 15

    """GIVEN executive timeline and the scenario: uses epics when available"""
    def test_uses_epics_when_available(self, snapshot: BoardSnapshot) -> None:
        """WHEN the code under test is exercised for: uses epics when available"""
        data = build_executive_timeline(snapshot)
        keys = {s.key for s in data.swimlanes}

        """THEN the expected behaviour holds: uses epics when available"""
        assert "E-1" in keys or "E-2" in keys


# ---------------------------------------------------------------------------
# build_timeline dispatcher
# ---------------------------------------------------------------------------


class TestBuildTimelineDispatcher:
    """GIVEN build timeline dispatcher and the scenario: all modes"""
    def test_all_modes(self, snapshot: BoardSnapshot) -> None:
        """THEN the expected behaviour holds: all modes"""
        for mode in TimelineMode:
            data = build_timeline(snapshot, mode)
            assert isinstance(data, TimelineData)
            assert data.mode == mode
