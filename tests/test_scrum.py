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
    def test_high_priority_items_are_goal_items(
        self,
        sprint_active: Sprint,
        alice: Person,
        sprint_health_active: SprintHealth,
    ) -> None:
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
        assert len(reports) == 1
        r = reports[0]
        assert r.total_goal_items == 2
        assert r.completed == 1
        assert r.in_progress == 1

    def test_blocked_goal_sets_off_track(
        self,
        sprint_active: Sprint,
        alice: Person,
        sprint_health_active: SprintHealth,
    ) -> None:
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
        assert reports[0].health == "off_track"
        assert reports[0].blocked == 1

    def test_not_started_in_active_sprint_is_at_risk(
        self,
        sprint_active: Sprint,
        alice: Person,
        sprint_health_active: SprintHealth,
    ) -> None:
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
        assert reports[0].health == "at_risk"

    def test_empty_issues_returns_on_track(self, sprint_health_active: SprintHealth) -> None:
        reports = compute_sprint_goals([], [sprint_health_active])
        assert len(reports) == 1
        assert reports[0].health == "on_track"
        assert reports[0].total_goal_items == 0

    def test_no_sprint_healths_returns_empty(self) -> None:
        assert compute_sprint_goals([], []) == []


# ---------------------------------------------------------------------------
# compute_scope_changes
# ---------------------------------------------------------------------------


class TestComputeScopeChanges:
    def test_items_added_after_sprint_start_are_scope_changes(
        self,
        sprint_active: Sprint,
        alice: Person,
        sprint_health_active: SprintHealth,
    ) -> None:
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
        assert len(reports) == 1
        r = reports[0]
        assert r.original_count == 1
        assert r.added_count == 1
        assert r.churn_pct == 100.0  # 1 added / 1 original = 100% churn
        assert r.stability == "unstable"

    def test_stable_when_no_additions(
        self,
        sprint_active: Sprint,
        alice: Person,
        sprint_health_active: SprintHealth,
    ) -> None:
        issues = [
            _issue(
                "S-1",
                assignee=alice,
                sprint=sprint_active,
                created=datetime(2026, 2, 28, tzinfo=UTC),
            ),
        ]
        reports = compute_scope_changes(issues, [sprint_health_active])
        assert reports[0].churn_pct == 0.0
        assert reports[0].stability == "stable"

    def test_sprint_without_start_date_skipped(self, alice: Person) -> None:
        sp = Sprint(id=99, name="No Date")
        sh = SprintHealth(sprint=sp)
        issues = [_issue("S-1", assignee=alice, sprint=sp)]
        assert compute_scope_changes(issues, [sh]) == []

    def test_empty_sprint_returns_report(self, sprint_health_active: SprintHealth) -> None:
        reports = compute_scope_changes([], [sprint_health_active])
        assert len(reports) == 1
        assert reports[0].churn_pct == 0.0


# ---------------------------------------------------------------------------
# compute_blockers
# ---------------------------------------------------------------------------


class TestComputeBlockers:
    def test_blocked_issue_detected(self, alice: Person) -> None:
        now = datetime.now(tz=UTC)
        issues = [
            _issue("B-1", assignee=alice, links=[_blocked_link()], created=now - timedelta(days=2)),
        ]
        blockers = compute_blockers(issues, today=_TODAY)
        assert len(blockers) == 1
        assert blockers[0].key == "B-1"
        assert blockers[0].severity == "warning"

    def test_severity_critical_after_3_days(self, alice: Person) -> None:
        now = datetime.now(tz=UTC)
        issues = [
            _issue("B-1", assignee=alice, links=[_blocked_link()], created=now - timedelta(days=5)),
        ]
        blockers = compute_blockers(issues, today=_TODAY)
        # age = 5 days → > 3 but ≤ 7 → critical
        assert blockers[0].severity == "critical"
        assert blockers[0].blocked_days == 5

    def test_severity_escalate_after_7_days(self, alice: Person) -> None:
        now = datetime.now(tz=UTC)
        issues = [
            _issue(
                "B-1", assignee=alice, links=[_blocked_link()], created=now - timedelta(days=14)
            ),
        ]
        blockers = compute_blockers(issues, today=_TODAY)
        # age = 14 days → > 7 → escalate
        assert blockers[0].severity == "escalate"

    def test_unblocked_issues_excluded(self, alice: Person) -> None:
        issues = [_issue("OK-1", assignee=alice)]
        assert compute_blockers(issues, today=_TODAY) == []

    def test_empty_issues(self) -> None:
        assert compute_blockers([], today=_TODAY) == []

    def test_sorted_by_age_descending(self, alice: Person) -> None:
        now = datetime.now(tz=UTC)
        issues = [
            _issue("B-1", assignee=alice, links=[_blocked_link()], created=now - timedelta(days=2)),
            _issue(
                "B-2", assignee=alice, links=[_blocked_link()], created=now - timedelta(days=14)
            ),
        ]
        blockers = compute_blockers(issues, today=_TODAY)
        assert blockers[0].key == "B-2"
        assert blockers[1].key == "B-1"


# ---------------------------------------------------------------------------
# compute_backlog_quality
# ---------------------------------------------------------------------------


class TestComputeBacklogQuality:
    def test_perfect_backlog_scores_high(self, alice: Person) -> None:
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
        assert report.quality_score >= 85
        assert report.grade == "A"

    def test_poor_backlog_scores_low(self) -> None:
        issues = [
            _issue(
                "BQ-1", sp=0, status=StatusCategory.TODO, created=datetime(2025, 1, 1, tzinfo=UTC)
            ),
        ]
        report = compute_backlog_quality(issues, stale_days=30, today=_TODAY)
        assert report.no_estimate == 1
        assert report.no_assignee == 1
        assert report.no_epic == 1
        assert report.stale_count == 1
        assert report.grade in ("C", "D")

    def test_empty_backlog_returns_perfect(self) -> None:
        report = compute_backlog_quality([], today=_TODAY)
        assert report.quality_score == 100.0
        assert report.grade == "A"

    def test_non_todo_items_excluded(self, alice: Person) -> None:
        issues = [
            _issue("BQ-1", assignee=alice, sp=0, status=StatusCategory.DONE),
        ]
        report = compute_backlog_quality(issues, today=_TODAY)
        assert report.total_backlog == 0
        assert report.grade == "A"

    def test_grade_boundaries(self) -> None:
        # Create 4 TODO items: one missing each check → score ~75 → B
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
        assert report.grade == "A"


# ---------------------------------------------------------------------------
# compute_readiness
# ---------------------------------------------------------------------------


class TestComputeReadiness:
    def test_fully_ready_item(self, alice: Person) -> None:
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
        assert report.total_candidates == 1
        assert report.ready_count == 1
        assert report.items[0].readiness_pct == 100.0

    def test_missing_fields_reduce_readiness(self) -> None:
        issues = [
            _issue("R-1", sp=0, status=StatusCategory.TODO),
        ]
        report = compute_readiness(issues, max_sp=13.0)
        assert report.ready_count == 0
        item = report.items[0]
        assert "estimate" in item.missing
        assert "assignee" in item.missing

    def test_too_large_item_flagged(self, alice: Person) -> None:
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
        assert "too_large" in report.items[0].missing

    def test_blocked_items_excluded(self, alice: Person) -> None:
        issues = [
            _issue(
                "R-1", assignee=alice, sp=5.0, status=StatusCategory.TODO, links=[_blocked_link()]
            ),
        ]
        report = compute_readiness(issues, max_sp=13.0)
        assert report.total_candidates == 0

    def test_empty_issues(self) -> None:
        report = compute_readiness([], max_sp=13.0)
        assert report.total_candidates == 0


# ---------------------------------------------------------------------------
# compute_delivery_risks
# ---------------------------------------------------------------------------


class TestComputeDeliveryRisks:
    def test_blocked_epic_increases_risk(self, alice: Person) -> None:
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
        assert len(risks) == 1
        assert risks[0].risk_score > 0
        assert any("blocked" in f for f in risks[0].factors)

    def test_no_epic_returns_empty(self, alice: Person) -> None:
        issues = [_issue("DR-1", assignee=alice)]
        risks = compute_delivery_risks(issues, [])
        assert risks == []

    def test_risk_levels(self, alice: Person) -> None:
        # Create epic with many blockers → high score
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
        assert risks[0].level in ("high", "critical")

    def test_empty_issues(self) -> None:
        assert compute_delivery_risks([], []) == []


# ---------------------------------------------------------------------------
# compute_dependency_heatmap
# ---------------------------------------------------------------------------


class TestComputeDependencyHeatmap:
    def test_cross_team_deps_counted(self, alice: Person, bob: Person) -> None:
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
        assert len(cells) == 1
        assert cells[0].from_team == "alpha"
        assert cells[0].to_team == "beta"
        assert cells[0].count == 1
        assert "alpha" in teams and "beta" in teams

    def test_same_team_deps_excluded(self, alice: Person) -> None:
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
        assert len(cells) == 0

    def test_empty_snapshot(self) -> None:
        snap = BoardSnapshot()
        cells, teams = compute_dependency_heatmap(snap)
        assert cells == [] and teams == []


# ---------------------------------------------------------------------------
# compute_capacity
# ---------------------------------------------------------------------------


class TestComputeCapacity:
    def test_balanced_team(self, alice: Person) -> None:
        issues = [
            _issue("C-1", assignee=alice, sp=10.0, status=StatusCategory.IN_PROGRESS),
        ]
        snap = BoardSnapshot(issues=issues)
        rows = compute_capacity(snap, capacity_per_person=13.0)
        assert len(rows) == 1
        r = rows[0]
        assert r.team == "alpha"
        assert r.capacity_sp == 13.0
        assert r.committed_sp == 10.0
        assert r.utilization_pct == pytest.approx(76.9, abs=0.1)
        assert r.status == "balanced"

    def test_over_committed_team(self, alice: Person) -> None:
        issues = [
            _issue("C-1", assignee=alice, sp=20.0, status=StatusCategory.IN_PROGRESS),
        ]
        snap = BoardSnapshot(issues=issues)
        rows = compute_capacity(snap, capacity_per_person=13.0)
        assert rows[0].status == "over"
        assert rows[0].utilization_pct > 100

    def test_under_utilised_team(self, alice: Person) -> None:
        issues = [
            _issue("C-1", assignee=alice, sp=3.0, status=StatusCategory.IN_PROGRESS),
        ]
        snap = BoardSnapshot(issues=issues)
        rows = compute_capacity(snap, capacity_per_person=13.0)
        assert rows[0].status == "under"

    def test_unassigned_issues_excluded(self) -> None:
        issues = [_issue("C-1", sp=10.0)]
        snap = BoardSnapshot(issues=issues)
        rows = compute_capacity(snap, capacity_per_person=13.0)
        assert rows == []

    def test_done_issues_counted_separately(self, alice: Person) -> None:
        issues = [
            _issue("C-1", assignee=alice, sp=8.0, status=StatusCategory.DONE),
            _issue("C-2", assignee=alice, sp=5.0, status=StatusCategory.IN_PROGRESS),
        ]
        snap = BoardSnapshot(issues=issues)
        rows = compute_capacity(snap, capacity_per_person=13.0)
        assert rows[0].done_sp == 8.0
        assert rows[0].in_progress_sp == 5.0


# ---------------------------------------------------------------------------
# compute_ceremonies
# ---------------------------------------------------------------------------


class TestComputeCeremonies:
    def test_all_four_ceremonies_present(self) -> None:
        cere = compute_ceremonies(
            issues=[],
            blockers=[],
            sprint_goals=[],
            scope_changes=[],
            readiness=ReadinessReport(),
            capacity=[],
            today=_TODAY,
        )
        assert set(cere.keys()) == {"daily", "planning", "review", "retro"}

    def test_daily_counts_escalations(self) -> None:
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
        assert cere["daily"].metrics["blockers"] == 1  # only critical/escalate

    def test_planning_uses_readiness_data(self) -> None:
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
        assert cere["planning"].metrics["ready"] == 5
        assert cere["planning"].metrics["not_ready"] == 2


# ---------------------------------------------------------------------------
# compute_product_progress
# ---------------------------------------------------------------------------


class TestComputeProductProgress:
    def test_epic_completion_tracked(self, alice: Person) -> None:
        issues = [
            _issue("PP-1", assignee=alice, epic_key="EPIC-1", status=StatusCategory.DONE, sp=5.0),
            _issue(
                "PP-2", assignee=alice, epic_key="EPIC-1", status=StatusCategory.IN_PROGRESS, sp=3.0
            ),
        ]
        report = compute_product_progress(issues, today=_TODAY)
        assert len(report.epics) == 1
        ep = report.epics[0]
        assert ep.total_issues == 2
        assert ep.done_issues == 1
        assert ep.completion_pct == 50.0
        assert ep.status == "on_track"

    def test_blocked_epic_at_risk(self, alice: Person) -> None:
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
        assert report.epics[0].status == "at_risk"
        assert report.at_risk == 1

    def test_all_done_epic(self, alice: Person) -> None:
        issues = [
            _issue("PP-1", assignee=alice, epic_key="EPIC-1", status=StatusCategory.DONE),
        ]
        report = compute_product_progress(issues, today=_TODAY)
        assert report.epics[0].status == "done"
        assert report.done == 1

    def test_no_epics_returns_empty(self, alice: Person) -> None:
        issues = [_issue("PP-1", assignee=alice)]
        report = compute_product_progress(issues, today=_TODAY)
        assert report.epics == []
        assert report.overall_completion == 0.0

    def test_empty_issues(self) -> None:
        report = compute_product_progress([], today=_TODAY)
        assert report.epics == []


# ---------------------------------------------------------------------------
# compute_scrum_insights (top-level orchestrator)
# ---------------------------------------------------------------------------


class TestComputeScrumInsights:
    def test_orchestrator_returns_all_sections(self, alice: Person, sprint_active: Sprint) -> None:
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

    def test_orchestrator_empty_snapshot(self) -> None:
        snap = BoardSnapshot()
        thresholds = Thresholds()
        insights = compute_scrum_insights(snap, thresholds, today=_TODAY)
        assert insights.sprint_goals == []
        assert insights.blockers == []
        assert insights.backlog_quality.grade == "A"
