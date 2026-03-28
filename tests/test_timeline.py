"""Tests for domain/timeline.py — timeline data preparation."""

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
            assignee=people[0],  # Alice — overlaps with P-1
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
            # No created/due_date — should be skipped
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
    def test_created_and_due(self, issues: list[Issue]) -> None:
        rng = _issue_date_range(issues[0])
        assert rng is not None
        assert rng[0] == date(2026, 2, 15)
        assert rng[1] == date(2026, 3, 20)

    def test_no_dates_returns_none(self, issues: list[Issue]) -> None:
        assert _issue_date_range(issues[4]) is None

    def test_fallback_to_sprint_dates(self, sprint: Sprint) -> None:
        issue = Issue(
            key="X-1",
            summary="test",
            sprint=sprint,
            created=datetime(2026, 3, 5, tzinfo=UTC),
        )
        rng = _issue_date_range(issue)
        assert rng is not None
        assert rng[1] == sprint.end_date

    def test_end_before_start_gets_padded(self) -> None:
        issue = Issue(
            key="X-2",
            summary="test",
            created=datetime(2026, 3, 10, tzinfo=UTC),
            due_date=date(2026, 3, 5),  # before created
        )
        rng = _issue_date_range(issue)
        assert rng is not None
        assert rng[1] == date(2026, 3, 24)  # 14 days after start


# ---------------------------------------------------------------------------
# _detect_overlaps
# ---------------------------------------------------------------------------

class TestDetectOverlaps:
    def test_no_overlap(self) -> None:
        bars = [
            TimelineBar(key="A", label="A", assignee="X", team="", start=date(2026, 1, 1), end=date(2026, 1, 10)),
            TimelineBar(key="B", label="B", assignee="X", team="", start=date(2026, 1, 15), end=date(2026, 1, 25)),
        ]
        assert _detect_overlaps(bars, "X") == []

    def test_overlap_detected(self) -> None:
        bars = [
            TimelineBar(key="A", label="A", assignee="X", team="", start=date(2026, 1, 1), end=date(2026, 1, 15)),
            TimelineBar(key="B", label="B", assignee="X", team="", start=date(2026, 1, 10), end=date(2026, 1, 25)),
        ]
        overlaps = _detect_overlaps(bars, "X")
        assert len(overlaps) >= 1
        assert overlaps[0].severity == "medium"
        assert "A" in overlaps[0].bar_keys
        assert "B" in overlaps[0].bar_keys

    def test_high_severity_for_triple_overlap(self) -> None:
        bars = [
            TimelineBar(key="A", label="A", assignee="X", team="", start=date(2026, 1, 1), end=date(2026, 1, 20)),
            TimelineBar(key="B", label="B", assignee="X", team="", start=date(2026, 1, 5), end=date(2026, 1, 25)),
            TimelineBar(key="C", label="C", assignee="X", team="", start=date(2026, 1, 10), end=date(2026, 1, 30)),
        ]
        overlaps = _detect_overlaps(bars, "X")
        high_or_critical = [o for o in overlaps if o.severity in ("high", "critical")]
        assert len(high_or_critical) >= 1

    def test_single_bar_no_overlap(self) -> None:
        bars = [
            TimelineBar(key="A", label="A", assignee="X", team="", start=date(2026, 1, 1), end=date(2026, 1, 10)),
        ]
        assert _detect_overlaps(bars, "X") == []


# ---------------------------------------------------------------------------
# build_assignee_timeline
# ---------------------------------------------------------------------------

class TestAssigneeTimeline:
    def test_groups_by_assignee(self, snapshot: BoardSnapshot) -> None:
        data = build_assignee_timeline(snapshot)
        assert data.mode == TimelineMode.ASSIGNEE
        names = {s.key for s in data.swimlanes}
        assert "Alice" in names
        assert "Bob" in names
        assert "Carol" in names

    def test_detects_alice_overlap(self, snapshot: BoardSnapshot) -> None:
        data = build_assignee_timeline(snapshot)
        alice_lane = next(s for s in data.swimlanes if s.key == "Alice")
        assert alice_lane.overlap_count >= 1
        assert len(alice_lane.bars) == 2

    def test_date_range_covers_all_bars(self, snapshot: BoardSnapshot) -> None:
        data = build_assignee_timeline(snapshot)
        assert data.total_days > 0
        assert data.range_start < data.range_end

    def test_sprint_boundaries(self, snapshot: BoardSnapshot) -> None:
        data = build_assignee_timeline(snapshot)
        assert len(data.sprint_boundaries) >= 1
        assert data.sprint_boundaries[0][0] == "Sprint 12"


# ---------------------------------------------------------------------------
# build_team_timeline
# ---------------------------------------------------------------------------

class TestTeamTimeline:
    def test_groups_by_team(self, snapshot: BoardSnapshot) -> None:
        data = build_team_timeline(snapshot)
        assert data.mode == TimelineMode.TEAM
        names = {s.key for s in data.swimlanes}
        assert "Platform" in names
        assert "Frontend" in names


# ---------------------------------------------------------------------------
# build_epic_timeline
# ---------------------------------------------------------------------------

class TestEpicTimeline:
    def test_uses_roadmap_items(self, snapshot: BoardSnapshot) -> None:
        data = build_epic_timeline(snapshot)
        assert data.mode == TimelineMode.EPIC
        keys = {s.key for s in data.swimlanes}
        assert "E-1" in keys
        assert "E-2" in keys

    def test_epic_bar_has_progress(self, snapshot: BoardSnapshot) -> None:
        data = build_epic_timeline(snapshot)
        e1_lane = next(s for s in data.swimlanes if s.key == "E-1")
        assert e1_lane.bars[0].progress_pct == 60.0


# ---------------------------------------------------------------------------
# build_conflict_timeline
# ---------------------------------------------------------------------------

class TestConflictTimeline:
    def test_only_conflicting_lanes(self, snapshot: BoardSnapshot) -> None:
        data = build_conflict_timeline(snapshot)
        assert data.mode == TimelineMode.CONFLICT
        for lane in data.swimlanes:
            assert lane.overlap_count > 0

    def test_empty_when_no_conflicts(self) -> None:
        issue = Issue(
            key="X-1",
            summary="solo",
            assignee=Person("u1", "Solo Person"),
            created=datetime(2026, 1, 1, tzinfo=UTC),
            due_date=date(2026, 1, 10),
        )
        snap = BoardSnapshot(issues=[issue])
        data = build_conflict_timeline(snap)
        assert len(data.swimlanes) == 0


# ---------------------------------------------------------------------------
# build_executive_timeline
# ---------------------------------------------------------------------------

class TestExecutiveTimeline:
    def test_caps_swimlanes(self, snapshot: BoardSnapshot) -> None:
        data = build_executive_timeline(snapshot)
        assert data.mode == TimelineMode.EXECUTIVE
        assert len(data.swimlanes) <= 15

    def test_uses_epics_when_available(self, snapshot: BoardSnapshot) -> None:
        data = build_executive_timeline(snapshot)
        keys = {s.key for s in data.swimlanes}
        assert "E-1" in keys or "E-2" in keys


# ---------------------------------------------------------------------------
# build_timeline dispatcher
# ---------------------------------------------------------------------------

class TestBuildTimelineDispatcher:
    def test_all_modes(self, snapshot: BoardSnapshot) -> None:
        for mode in TimelineMode:
            data = build_timeline(snapshot, mode)
            assert isinstance(data, TimelineData)
            assert data.mode == mode
