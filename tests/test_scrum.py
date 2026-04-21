"""Tests for Scrum-oriented analytics module."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from flowboard.domain.models import (
    BoardSnapshot,
    Dependency,
    Issue,
    IssueLink,
    Person,
    Sprint,
    SprintHealth,
)
from flowboard.domain.scrum import (
    BacklogQualityReport,
    BlockerItem,
    ReadinessReport,
    ScrumInsights,
    compute_backlog_quality,
    compute_blockers,
    compute_capacity,
    compute_ceremonies,
    compute_delivery_risks,
    compute_dependency_heatmap,
    compute_product_progress,
    compute_readiness,
    compute_scope_changes,
    compute_scrum_insights,
    compute_sprint_goals,
)
from flowboard.infrastructure.config.loader import Thresholds
from flowboard.shared.types import (
    IssueType,
    LinkType,
    Priority,
    SprintState,
    StatusCategory,
)

# ---------------------------------------------------------------------------
# Helpers & fixtures
# ---------------------------------------------------------------------------

_TODAY = date(2026, 3, 15)


def _person(name: str, team: str = "alpha") -> Person:
    return Person(account_id=name.lower(), display_name=name, team=team)


def _sprint(
    name: str = "Sprint 1",
    sid: int = 1,
    state: SprintState = SprintState.ACTIVE,
    start: date | None = None,
    end: date | None = None,
) -> Sprint:
    return Sprint(
        id=sid,
        name=name,
        state=state,
        start_date=start or date(2026, 3, 1),
        end_date=end or date(2026, 3, 14),
    )


def _issue(
    key: str,
    *,
    assignee: Person | None = None,
    sp: float = 5.0,
    status: StatusCategory = StatusCategory.IN_PROGRESS,
    priority: Priority = Priority.MEDIUM,
    sprint: Sprint | None = None,
    epic_key: str = "",
    created: datetime | None = None,
    links: list[IssueLink] | None = None,
) -> Issue:
    return Issue(
        key=key,
        summary=f"Issue {key}",
        issue_type=IssueType.STORY,
        status_category=status,
        assignee=assignee,
        story_points=sp,
        priority=priority,
        sprint=sprint,
        epic_key=epic_key,
        created=created or datetime(2026, 3, 1, tzinfo=UTC),
        links=links or [],
    )


def _blocked_link() -> IssueLink:
    return IssueLink(
        target_key="BLOCK-1",
        link_type=LinkType.IS_BLOCKED_BY,
        is_resolved=False,
    )


@pytest.fixture()
def sprint_active() -> Sprint:
    return _sprint("Sprint 1", sid=1, state=SprintState.ACTIVE)


@pytest.fixture()
def sprint_future() -> Sprint:
    return _sprint("Sprint 2", sid=2, state=SprintState.FUTURE, start=date(2026, 3, 15))


@pytest.fixture()
def alice() -> Person:
    return _person("Alice", "alpha")


@pytest.fixture()
def bob() -> Person:
    return _person("Bob", "beta")


@pytest.fixture()
def sprint_health_active(sprint_active: Sprint) -> SprintHealth:
    return SprintHealth(sprint=sprint_active)


# ---------------------------------------------------------------------------
# compute_sprint_goals
# ---------------------------------------------------------------------------


class TestComputeSprintGoals:
    """GIVEN compute sprint goals and the scenario: high priority items are goal items"""
    def test_high_priority_items_are_goal_items(
        self,
        sprint_active: Sprint,
        alice: Person,
        sprint_health_active: SprintHealth,
    ) -> None:
        """WHEN the code under test is exercised for: high priority items are goal items"""
        issues = [
            _issue(
                "G-1",
                assignee=alice,
                priority=Priority.HIGH,
                sprint=sprint_active,
                status=StatusCategory.DONE,
            ),
            _issue(
                "G-2",
                assignee=alice,
                priority=Priority.HIGHEST,
                sprint=sprint_active,
                status=StatusCategory.IN_PROGRESS,
            ),
            _issue("G-3", assignee=alice, priority=Priority.LOW, sprint=sprint_active),
        ]
        reports = compute_sprint_goals(issues, [sprint_health_active])

        """THEN the expected behaviour holds: high priority items are goal items"""
        assert len(reports) == 1
        r = reports[0]
        assert r.total_goal_items == 2
        assert r.completed == 1
        assert r.in_progress == 1

    """GIVEN compute sprint goals and the scenario: blocked goal sets off track"""
    def test_blocked_goal_sets_off_track(
        self,
        sprint_active: Sprint,
        alice: Person,
        sprint_health_active: SprintHealth,
    ) -> None:
        """WHEN the code under test is exercised for: blocked goal sets off track"""
        issues = [
            _issue(
                "G-1",
                assignee=alice,
                priority=Priority.HIGH,
                sprint=sprint_active,
                status=StatusCategory.IN_PROGRESS,
                links=[_blocked_link()],
            ),
        ]
        reports = compute_sprint_goals(issues, [sprint_health_active])

        """THEN the expected behaviour holds: blocked goal sets off track"""
        assert reports[0].health == "off_track"
        assert reports[0].blocked == 1

    """GIVEN compute sprint goals and the scenario: not started in active sprint is at risk"""
    def test_not_started_in_active_sprint_is_at_risk(
        self,
        sprint_active: Sprint,
        alice: Person,
        sprint_health_active: SprintHealth,
    ) -> None:
        """WHEN the code under test is exercised for: not started in active sprint is at risk"""
        issues = [
            _issue(
                "G-1",
                assignee=alice,
                priority=Priority.HIGH,
                sprint=sprint_active,
                status=StatusCategory.DONE,
            ),
            _issue(
                "G-2",
                assignee=alice,
                priority=Priority.HIGH,
                sprint=sprint_active,
                status=StatusCategory.TODO,
            ),
        ]
        reports = compute_sprint_goals(issues, [sprint_health_active])
        # not_started > 0 and active → at_risk (but not_started <= completed so not off_track)

        """THEN the expected behaviour holds: not started in active sprint is at risk"""
        assert reports[0].health == "at_risk"

    """GIVEN compute sprint goals and the scenario: empty issues returns on track"""
    def test_empty_issues_returns_on_track(self, sprint_health_active: SprintHealth) -> None:
        """WHEN the code under test is exercised for: empty issues returns on track"""
        reports = compute_sprint_goals([], [sprint_health_active])

        """THEN the expected behaviour holds: empty issues returns on track"""
        assert len(reports) == 1
        assert reports[0].health == "on_track"
        assert reports[0].total_goal_items == 0

    """GIVEN compute sprint goals and the scenario: no sprint healths returns empty"""
    def test_no_sprint_healths_returns_empty(self) -> None:
        """THEN the expected behaviour holds: no sprint healths returns empty"""
        assert compute_sprint_goals([], []) == []


# ---------------------------------------------------------------------------
# compute_scope_changes
# ---------------------------------------------------------------------------


class TestComputeScopeChanges:
    """GIVEN compute scope changes and the scenario: items added after sprint start are scope changes"""
    def test_items_added_after_sprint_start_are_scope_changes(
        self,
        sprint_active: Sprint,
        alice: Person,
        sprint_health_active: SprintHealth,
    ) -> None:
        """WHEN the code under test is exercised for: items added after sprint start are scope changes"""
        issues = [
            _issue(
                "S-1",
                assignee=alice,
                sprint=sprint_active,
                created=datetime(2026, 2, 28, tzinfo=UTC),
            ),
            _issue(
                "S-2",
                assignee=alice,
                sprint=sprint_active,
                created=datetime(2026, 3, 5, tzinfo=UTC),
            ),
        ]
        reports = compute_scope_changes(issues, [sprint_health_active])

        """THEN the expected behaviour holds: items added after sprint start are scope changes"""
        assert len(reports) == 1
        r = reports[0]
        assert r.original_count == 1
        assert r.added_count == 1
        assert r.churn_pct == 100.0  # 1 added / 1 original = 100% churn
        assert r.stability == "unstable"

    """GIVEN compute scope changes and the scenario: stable when no additions"""
    def test_stable_when_no_additions(
        self,
        sprint_active: Sprint,
        alice: Person,
        sprint_health_active: SprintHealth,
    ) -> None:
        """WHEN the code under test is exercised for: stable when no additions"""
        issues = [
            _issue(
                "S-1",
                assignee=alice,
                sprint=sprint_active,
                created=datetime(2026, 2, 28, tzinfo=UTC),
            ),
        ]
        reports = compute_scope_changes(issues, [sprint_health_active])

        """THEN the expected behaviour holds: stable when no additions"""
        assert reports[0].churn_pct == 0.0
        assert reports[0].stability == "stable"

    """GIVEN compute scope changes and the scenario: sprint without start date skipped"""
    def test_sprint_without_start_date_skipped(self, alice: Person) -> None:
        """WHEN the code under test is exercised for: sprint without start date skipped"""
        sp = Sprint(id=99, name="No Date")
        sh = SprintHealth(sprint=sp)
        issues = [_issue("S-1", assignee=alice, sprint=sp)]

        """THEN the expected behaviour holds: sprint without start date skipped"""
        assert compute_scope_changes(issues, [sh]) == []

    """GIVEN compute scope changes and the scenario: empty sprint returns report"""
    def test_empty_sprint_returns_report(self, sprint_health_active: SprintHealth) -> None:
        """WHEN the code under test is exercised for: empty sprint returns report"""
        reports = compute_scope_changes([], [sprint_health_active])

        """THEN the expected behaviour holds: empty sprint returns report"""
        assert len(reports) == 1
        assert reports[0].churn_pct == 0.0


# ---------------------------------------------------------------------------
# compute_blockers
# ---------------------------------------------------------------------------


class TestComputeBlockers:
    """GIVEN compute blockers and the scenario: blocked issue detected"""
    def test_blocked_issue_detected(self, alice: Person) -> None:
        """WHEN the code under test is exercised for: blocked issue detected"""
        now = datetime.now(tz=UTC)
        issues = [
            _issue("B-1", assignee=alice, links=[_blocked_link()], created=now - timedelta(days=2)),
        ]
        blockers = compute_blockers(issues, today=_TODAY)

        """THEN the expected behaviour holds: blocked issue detected"""
        assert len(blockers) == 1
        assert blockers[0].key == "B-1"
        assert blockers[0].severity == "warning"

    """GIVEN compute blockers and the scenario: severity critical after 3 days"""
    def test_severity_critical_after_3_days(self, alice: Person) -> None:
        """WHEN the code under test is exercised for: severity critical after 3 days"""
        now = datetime.now(tz=UTC)
        issues = [
            _issue("B-1", assignee=alice, links=[_blocked_link()], created=now - timedelta(days=5)),
        ]
        blockers = compute_blockers(issues, today=_TODAY)
        # age = 5 days → > 3 but ≤ 7 → critical

        """THEN the expected behaviour holds: severity critical after 3 days"""
        assert blockers[0].severity == "critical"
        assert blockers[0].blocked_days == 5

    """GIVEN compute blockers and the scenario: severity escalate after 7 days"""
    def test_severity_escalate_after_7_days(self, alice: Person) -> None:
        """WHEN the code under test is exercised for: severity escalate after 7 days"""
        now = datetime.now(tz=UTC)
        issues = [
            _issue(
                "B-1", assignee=alice, links=[_blocked_link()], created=now - timedelta(days=14)
            ),
        ]
        blockers = compute_blockers(issues, today=_TODAY)
        # age = 14 days → > 7 → escalate

        """THEN the expected behaviour holds: severity escalate after 7 days"""
        assert blockers[0].severity == "escalate"

    """GIVEN compute blockers and the scenario: unblocked issues excluded"""
    def test_unblocked_issues_excluded(self, alice: Person) -> None:
        """WHEN the code under test is exercised for: unblocked issues excluded"""
        issues = [_issue("OK-1", assignee=alice)]

        """THEN the expected behaviour holds: unblocked issues excluded"""
        assert compute_blockers(issues, today=_TODAY) == []

    """GIVEN compute blockers and the scenario: empty issues"""
    def test_empty_issues(self) -> None:
        """THEN the expected behaviour holds: empty issues"""
        assert compute_blockers([], today=_TODAY) == []

    """GIVEN compute blockers and the scenario: sorted by age descending"""
    def test_sorted_by_age_descending(self, alice: Person) -> None:
        """WHEN the code under test is exercised for: sorted by age descending"""
        now = datetime.now(tz=UTC)
        issues = [
            _issue("B-1", assignee=alice, links=[_blocked_link()], created=now - timedelta(days=2)),
            _issue(
                "B-2", assignee=alice, links=[_blocked_link()], created=now - timedelta(days=14)
            ),
        ]
        blockers = compute_blockers(issues, today=_TODAY)

        """THEN the expected behaviour holds: sorted by age descending"""
        assert blockers[0].key == "B-2"
        assert blockers[1].key == "B-1"


# ---------------------------------------------------------------------------
# compute_backlog_quality
# ---------------------------------------------------------------------------


class TestComputeBacklogQuality:
    """GIVEN compute backlog quality and the scenario: perfect backlog scores high"""
    def test_perfect_backlog_scores_high(self, alice: Person) -> None:
        """WHEN the code under test is exercised for: perfect backlog scores high"""
        issues = [
            _issue(
                "BQ-1",
                assignee=alice,
                sp=3.0,
                status=StatusCategory.TODO,
                priority=Priority.HIGH,
                epic_key="EPIC-1",
                created=datetime(2026, 3, 10, tzinfo=UTC),
            ),
        ]
        report = compute_backlog_quality(issues, stale_days=30, today=_TODAY)

        """THEN the expected behaviour holds: perfect backlog scores high"""
        assert report.quality_score >= 85
        assert report.grade == "A"

    """GIVEN compute backlog quality and the scenario: poor backlog scores low"""
    def test_poor_backlog_scores_low(self) -> None:
        """WHEN the code under test is exercised for: poor backlog scores low"""
        issues = [
            _issue(
                "BQ-1", sp=0, status=StatusCategory.TODO, created=datetime(2025, 1, 1, tzinfo=UTC)
            ),
        ]
        report = compute_backlog_quality(issues, stale_days=30, today=_TODAY)

        """THEN the expected behaviour holds: poor backlog scores low"""
        assert report.no_estimate == 1
        assert report.no_assignee == 1
        assert report.no_epic == 1
        assert report.stale_count == 1
        assert report.grade in ("C", "D")

    """GIVEN compute backlog quality and the scenario: empty backlog returns perfect"""
    def test_empty_backlog_returns_perfect(self) -> None:
        """WHEN the code under test is exercised for: empty backlog returns perfect"""
        report = compute_backlog_quality([], today=_TODAY)

        """THEN the expected behaviour holds: empty backlog returns perfect"""
        assert report.quality_score == 100.0
        assert report.grade == "A"

    """GIVEN compute backlog quality and the scenario: non todo items excluded"""
    def test_non_todo_items_excluded(self, alice: Person) -> None:
        """WHEN the code under test is exercised for: non todo items excluded"""
        issues = [
            _issue("BQ-1", assignee=alice, sp=0, status=StatusCategory.DONE),
        ]
        report = compute_backlog_quality(issues, today=_TODAY)

        """THEN the expected behaviour holds: non todo items excluded"""
        assert report.total_backlog == 0
        assert report.grade == "A"

    """GIVEN compute backlog quality and the scenario: grade boundaries"""
    def test_grade_boundaries(self) -> None:
        # Create 4 TODO items: one missing each check → score ~75 → B

        """WHEN the code under test is exercised for: grade boundaries"""
        alice = _person("Alice")
        issues = [
            _issue(
                f"BQ-{i}",
                assignee=alice,
                sp=3.0,
                status=StatusCategory.TODO,
                priority=Priority.HIGH,
                epic_key="EPIC-1",
                created=datetime(2026, 3, 10, tzinfo=UTC),
            )
            for i in range(4)
        ]
        # Make one item stale
        issues[0] = _issue(
            "BQ-stale",
            assignee=alice,
            sp=3.0,
            status=StatusCategory.TODO,
            priority=Priority.HIGH,
            epic_key="EPIC-1",
            created=datetime(2025, 1, 1, tzinfo=UTC),
        )
        report = compute_backlog_quality(issues, stale_days=30, today=_TODAY)
        # 1 stale out of 16 checks → score = (1 - 1/16) * 100 = 93.75 → A

        """THEN the expected behaviour holds: grade boundaries"""
        assert report.grade == "A"


# ---------------------------------------------------------------------------
# compute_readiness
# ---------------------------------------------------------------------------


class TestComputeReadiness:
    """GIVEN compute readiness and the scenario: fully ready item"""
    def test_fully_ready_item(self, alice: Person) -> None:
        """WHEN the code under test is exercised for: fully ready item"""
        issues = [
            _issue(
                "R-1",
                assignee=alice,
                sp=5.0,
                status=StatusCategory.TODO,
                priority=Priority.HIGH,
                epic_key="EPIC-1",
            ),
        ]
        report = compute_readiness(issues, max_sp=13.0)

        """THEN the expected behaviour holds: fully ready item"""
        assert report.total_candidates == 1
        assert report.ready_count == 1
        assert report.items[0].readiness_pct == 100.0

    """GIVEN compute readiness and the scenario: missing fields reduce readiness"""
    def test_missing_fields_reduce_readiness(self) -> None:
        """WHEN the code under test is exercised for: missing fields reduce readiness"""
        issues = [
            _issue("R-1", sp=0, status=StatusCategory.TODO),
        ]
        report = compute_readiness(issues, max_sp=13.0)

        """THEN the expected behaviour holds: missing fields reduce readiness"""
        assert report.ready_count == 0
        item = report.items[0]
        assert "estimate" in item.missing
        assert "assignee" in item.missing

    """GIVEN compute readiness and the scenario: too large item flagged"""
    def test_too_large_item_flagged(self, alice: Person) -> None:
        """WHEN the code under test is exercised for: too large item flagged"""
        issues = [
            _issue(
                "R-1",
                assignee=alice,
                sp=21.0,
                status=StatusCategory.TODO,
                priority=Priority.HIGH,
                epic_key="EPIC-1",
            ),
        ]
        report = compute_readiness(issues, max_sp=13.0)

        """THEN the expected behaviour holds: too large item flagged"""
        assert "too_large" in report.items[0].missing

    """GIVEN compute readiness and the scenario: blocked items excluded"""
    def test_blocked_items_excluded(self, alice: Person) -> None:
        """WHEN the code under test is exercised for: blocked items excluded"""
        issues = [
            _issue(
                "R-1", assignee=alice, sp=5.0, status=StatusCategory.TODO, links=[_blocked_link()]
            ),
        ]
        report = compute_readiness(issues, max_sp=13.0)

        """THEN the expected behaviour holds: blocked items excluded"""
        assert report.total_candidates == 0

    """GIVEN compute readiness and the scenario: empty issues"""
    def test_empty_issues(self) -> None:
        """WHEN the code under test is exercised for: empty issues"""
        report = compute_readiness([], max_sp=13.0)

        """THEN the expected behaviour holds: empty issues"""
        assert report.total_candidates == 0


# ---------------------------------------------------------------------------
# compute_delivery_risks
# ---------------------------------------------------------------------------


class TestComputeDeliveryRisks:
    """GIVEN compute delivery risks and the scenario: blocked epic increases risk"""
    def test_blocked_epic_increases_risk(self, alice: Person) -> None:
        """WHEN the code under test is exercised for: blocked epic increases risk"""
        issues = [
            _issue(
                "DR-1",
                assignee=alice,
                epic_key="EPIC-1",
                status=StatusCategory.IN_PROGRESS,
                links=[_blocked_link()],
            ),
            _issue("DR-2", assignee=alice, epic_key="EPIC-1", status=StatusCategory.TODO),
        ]
        sh = SprintHealth(sprint=_sprint())
        risks = compute_delivery_risks(issues, [sh])

        """THEN the expected behaviour holds: blocked epic increases risk"""
        assert len(risks) == 1
        assert risks[0].risk_score > 0
        assert any("blocked" in f for f in risks[0].factors)

    """GIVEN compute delivery risks and the scenario: no epic returns empty"""
    def test_no_epic_returns_empty(self, alice: Person) -> None:
        """WHEN the code under test is exercised for: no epic returns empty"""
        issues = [_issue("DR-1", assignee=alice)]
        risks = compute_delivery_risks(issues, [])

        """THEN the expected behaviour holds: no epic returns empty"""
        assert risks == []

    """GIVEN compute delivery risks and the scenario: risk levels"""
    def test_risk_levels(self, alice: Person) -> None:
        # Create epic with many blockers → high score

        """WHEN the code under test is exercised for: risk levels"""
        issues = [
            _issue(
                f"DR-{i}",
                assignee=alice,
                epic_key="EPIC-1",
                status=StatusCategory.IN_PROGRESS,
                links=[_blocked_link()],
            )
            for i in range(5)
        ]
        risks = compute_delivery_risks(issues, [])

        """THEN the expected behaviour holds: risk levels"""
        assert risks[0].level in ("high", "critical")

    """GIVEN compute delivery risks and the scenario: empty issues"""
    def test_empty_issues(self) -> None:
        """THEN the expected behaviour holds: empty issues"""
        assert compute_delivery_risks([], []) == []


# ---------------------------------------------------------------------------
# compute_dependency_heatmap
# ---------------------------------------------------------------------------


class TestComputeDependencyHeatmap:
    """GIVEN compute dependency heatmap and the scenario: cross team deps counted"""
    def test_cross_team_deps_counted(self, alice: Person, bob: Person) -> None:
        """WHEN the code under test is exercised for: cross team deps counted"""
        issues = [
            _issue("DH-1", assignee=alice),
            _issue("DH-2", assignee=bob),
        ]
        deps = [
            Dependency(
                source_key="DH-1",
                target_key="DH-2",
                link_type=LinkType.BLOCKS,
                source_status=StatusCategory.IN_PROGRESS,
                target_status=StatusCategory.TODO,
            ),
        ]
        snap = BoardSnapshot(issues=issues, dependencies=deps)
        cells, teams = compute_dependency_heatmap(snap)

        """THEN the expected behaviour holds: cross team deps counted"""
        assert len(cells) == 1
        assert cells[0].from_team == "alpha"
        assert cells[0].to_team == "beta"
        assert cells[0].count == 1
        assert "alpha" in teams and "beta" in teams

    """GIVEN compute dependency heatmap and the scenario: same team deps excluded"""
    def test_same_team_deps_excluded(self, alice: Person) -> None:
        """WHEN the code under test is exercised for: same team deps excluded"""
        alice2 = _person("Alice2", "alpha")
        issues = [
            _issue("DH-1", assignee=alice),
            _issue("DH-2", assignee=alice2),
        ]
        deps = [
            Dependency(
                source_key="DH-1",
                target_key="DH-2",
                link_type=LinkType.BLOCKS,
            ),
        ]
        snap = BoardSnapshot(issues=issues, dependencies=deps)
        cells, _teams = compute_dependency_heatmap(snap)

        """THEN the expected behaviour holds: same team deps excluded"""
        assert len(cells) == 0

    """GIVEN compute dependency heatmap and the scenario: empty snapshot"""
    def test_empty_snapshot(self) -> None:
        """WHEN the code under test is exercised for: empty snapshot"""
        snap = BoardSnapshot()
        cells, teams = compute_dependency_heatmap(snap)

        """THEN the expected behaviour holds: empty snapshot"""
        assert cells == [] and teams == []


# ---------------------------------------------------------------------------
# compute_capacity
# ---------------------------------------------------------------------------


class TestComputeCapacity:
    """GIVEN compute capacity and the scenario: balanced team"""
    def test_balanced_team(self, alice: Person) -> None:
        """WHEN the code under test is exercised for: balanced team"""
        issues = [
            _issue("C-1", assignee=alice, sp=10.0, status=StatusCategory.IN_PROGRESS),
        ]
        snap = BoardSnapshot(issues=issues)
        rows = compute_capacity(snap, capacity_per_person=13.0)

        """THEN the expected behaviour holds: balanced team"""
        assert len(rows) == 1
        r = rows[0]
        assert r.team == "alpha"
        assert r.capacity_sp == 13.0
        assert r.committed_sp == 10.0
        assert r.utilization_pct == pytest.approx(76.9, abs=0.1)
        assert r.status == "balanced"

    """GIVEN compute capacity and the scenario: over committed team"""
    def test_over_committed_team(self, alice: Person) -> None:
        """WHEN the code under test is exercised for: over committed team"""
        issues = [
            _issue("C-1", assignee=alice, sp=20.0, status=StatusCategory.IN_PROGRESS),
        ]
        snap = BoardSnapshot(issues=issues)
        rows = compute_capacity(snap, capacity_per_person=13.0)

        """THEN the expected behaviour holds: over committed team"""
        assert rows[0].status == "over"
        assert rows[0].utilization_pct > 100

    """GIVEN compute capacity and the scenario: under utilised team"""
    def test_under_utilised_team(self, alice: Person) -> None:
        """WHEN the code under test is exercised for: under utilised team"""
        issues = [
            _issue("C-1", assignee=alice, sp=3.0, status=StatusCategory.IN_PROGRESS),
        ]
        snap = BoardSnapshot(issues=issues)
        rows = compute_capacity(snap, capacity_per_person=13.0)

        """THEN the expected behaviour holds: under utilised team"""
        assert rows[0].status == "under"

    """GIVEN compute capacity and the scenario: unassigned issues excluded"""
    def test_unassigned_issues_excluded(self) -> None:
        """WHEN the code under test is exercised for: unassigned issues excluded"""
        issues = [_issue("C-1", sp=10.0)]
        snap = BoardSnapshot(issues=issues)
        rows = compute_capacity(snap, capacity_per_person=13.0)

        """THEN the expected behaviour holds: unassigned issues excluded"""
        assert rows == []

    """GIVEN compute capacity and the scenario: done issues counted separately"""
    def test_done_issues_counted_separately(self, alice: Person) -> None:
        """WHEN the code under test is exercised for: done issues counted separately"""
        issues = [
            _issue("C-1", assignee=alice, sp=8.0, status=StatusCategory.DONE),
            _issue("C-2", assignee=alice, sp=5.0, status=StatusCategory.IN_PROGRESS),
        ]
        snap = BoardSnapshot(issues=issues)
        rows = compute_capacity(snap, capacity_per_person=13.0)

        """THEN the expected behaviour holds: done issues counted separately"""
        assert rows[0].done_sp == 8.0
        assert rows[0].in_progress_sp == 5.0


# ---------------------------------------------------------------------------
# compute_ceremonies
# ---------------------------------------------------------------------------


class TestComputeCeremonies:
    """GIVEN compute ceremonies and the scenario: all four ceremonies present"""
    def test_all_four_ceremonies_present(self) -> None:
        """WHEN the code under test is exercised for: all four ceremonies present"""
        cere = compute_ceremonies(
            issues=[],
            blockers=[],
            sprint_goals=[],
            scope_changes=[],
            readiness=ReadinessReport(),
            capacity=[],
            today=_TODAY,
        )

        """THEN the expected behaviour holds: all four ceremonies present"""
        assert set(cere.keys()) == {"daily", "planning", "review", "retro"}

    """GIVEN compute ceremonies and the scenario: daily counts escalations"""
    def test_daily_counts_escalations(self) -> None:
        """WHEN the code under test is exercised for: daily counts escalations"""
        blockers = [
            BlockerItem(
                key="B-1",
                summary="x",
                assignee="a",
                team="t",
                blocked_days=10,
                severity="escalate",
                sprint_name="S1",
            ),
            BlockerItem(
                key="B-2",
                summary="y",
                assignee="b",
                team="t",
                blocked_days=2,
                severity="warning",
                sprint_name="S1",
            ),
        ]
        cere = compute_ceremonies(
            issues=[],
            blockers=blockers,
            sprint_goals=[],
            scope_changes=[],
            readiness=ReadinessReport(),
            capacity=[],
            today=_TODAY,
        )

        """THEN the expected behaviour holds: daily counts escalations"""
        assert cere["daily"].metrics["blockers"] == 1  # only critical/escalate

    """GIVEN compute ceremonies and the scenario: planning uses readiness data"""
    def test_planning_uses_readiness_data(self) -> None:
        """WHEN the code under test is exercised for: planning uses readiness data"""
        readiness = ReadinessReport(ready_count=5, not_ready_count=2, avg_readiness=70.0)
        cere = compute_ceremonies(
            issues=[],
            blockers=[],
            sprint_goals=[],
            scope_changes=[],
            readiness=readiness,
            capacity=[],
            today=_TODAY,
        )

        """THEN the expected behaviour holds: planning uses readiness data"""
        assert cere["planning"].metrics["ready"] == 5
        assert cere["planning"].metrics["not_ready"] == 2


# ---------------------------------------------------------------------------
# compute_product_progress
# ---------------------------------------------------------------------------


class TestComputeProductProgress:
    """GIVEN compute product progress and the scenario: epic completion tracked"""
    def test_epic_completion_tracked(self, alice: Person) -> None:
        """WHEN the code under test is exercised for: epic completion tracked"""
        issues = [
            _issue("PP-1", assignee=alice, epic_key="EPIC-1", status=StatusCategory.DONE, sp=5.0),
            _issue(
                "PP-2", assignee=alice, epic_key="EPIC-1", status=StatusCategory.IN_PROGRESS, sp=3.0
            ),
        ]
        report = compute_product_progress(issues, today=_TODAY)

        """THEN the expected behaviour holds: epic completion tracked"""
        assert len(report.epics) == 1
        ep = report.epics[0]
        assert ep.total_issues == 2
        assert ep.done_issues == 1
        assert ep.completion_pct == 50.0
        assert ep.status == "on_track"

    """GIVEN compute product progress and the scenario: blocked epic at risk"""
    def test_blocked_epic_at_risk(self, alice: Person) -> None:
        """WHEN the code under test is exercised for: blocked epic at risk"""
        issues = [
            _issue(
                "PP-1",
                assignee=alice,
                epic_key="EPIC-1",
                status=StatusCategory.IN_PROGRESS,
                links=[_blocked_link()],
            ),
            _issue("PP-2", assignee=alice, epic_key="EPIC-1", status=StatusCategory.TODO),
        ]
        report = compute_product_progress(issues, today=_TODAY)

        """THEN the expected behaviour holds: blocked epic at risk"""
        assert report.epics[0].status == "at_risk"
        assert report.at_risk == 1

    """GIVEN compute product progress and the scenario: all done epic"""
    def test_all_done_epic(self, alice: Person) -> None:
        """WHEN the code under test is exercised for: all done epic"""
        issues = [
            _issue("PP-1", assignee=alice, epic_key="EPIC-1", status=StatusCategory.DONE),
        ]
        report = compute_product_progress(issues, today=_TODAY)

        """THEN the expected behaviour holds: all done epic"""
        assert report.epics[0].status == "done"
        assert report.done == 1

    """GIVEN compute product progress and the scenario: no epics returns empty"""
    def test_no_epics_returns_empty(self, alice: Person) -> None:
        """WHEN the code under test is exercised for: no epics returns empty"""
        issues = [_issue("PP-1", assignee=alice)]
        report = compute_product_progress(issues, today=_TODAY)

        """THEN the expected behaviour holds: no epics returns empty"""
        assert report.epics == []
        assert report.overall_completion == 0.0

    """GIVEN compute product progress and the scenario: empty issues"""
    def test_empty_issues(self) -> None:
        """WHEN the code under test is exercised for: empty issues"""
        report = compute_product_progress([], today=_TODAY)

        """THEN the expected behaviour holds: empty issues"""
        assert report.epics == []


# ---------------------------------------------------------------------------
# compute_scrum_insights (top-level orchestrator)
# ---------------------------------------------------------------------------


class TestComputeScrumInsights:
    """GIVEN compute scrum insights and the scenario: orchestrator returns all sections"""
    def test_orchestrator_returns_all_sections(self, alice: Person, sprint_active: Sprint) -> None:
        """WHEN the code under test is exercised for: orchestrator returns all sections"""
        sh = SprintHealth(sprint=sprint_active)
        issues = [
            _issue(
                "I-1",
                assignee=alice,
                sp=5.0,
                status=StatusCategory.TODO,
                priority=Priority.HIGH,
                sprint=sprint_active,
                epic_key="EPIC-1",
                created=datetime(2026, 3, 1, tzinfo=UTC),
            ),
        ]
        snap = BoardSnapshot(issues=issues, sprint_health=[sh], sprints=[sprint_active])
        thresholds = Thresholds()

        insights = compute_scrum_insights(snap, thresholds, today=_TODAY)

        """THEN the expected behaviour holds: orchestrator returns all sections"""
        assert isinstance(insights, ScrumInsights)
        assert isinstance(insights.sprint_goals, list)
        assert isinstance(insights.scope_changes, list)
        assert isinstance(insights.blockers, list)
        assert isinstance(insights.backlog_quality, BacklogQualityReport)
        assert isinstance(insights.readiness, ReadinessReport)
        assert isinstance(insights.delivery_risks, list)
        assert isinstance(insights.dependency_heat, list)
        assert isinstance(insights.capacity, list)
        assert isinstance(insights.ceremonies, dict)

    """GIVEN compute scrum insights and the scenario: orchestrator empty snapshot"""
    def test_orchestrator_empty_snapshot(self) -> None:
        """WHEN the code under test is exercised for: orchestrator empty snapshot"""
        snap = BoardSnapshot()
        thresholds = Thresholds()
        insights = compute_scrum_insights(snap, thresholds, today=_TODAY)

        """THEN the expected behaviour holds: orchestrator empty snapshot"""
        assert insights.sprint_goals == []
        assert insights.blockers == []
        assert insights.backlog_quality.grade == "A"
