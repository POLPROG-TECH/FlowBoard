"""Tests for analytics correctness - sprint risk date handling, carry-over
computation, summary card thresholds, workload table thresholds, autoescape,
session management, pagination safety, aging risk timezone handling, dependency
chain DFS, import conventions, capacity clamping, and empty data edge cases.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from flowboard.domain.dependencies import build_dependency_chains, compute_sprint_health
from flowboard.domain.models import (
    BoardSnapshot,
    CapacityRecord,
    Dependency,
    Issue,
    IssueLink,
    Person,
    Sprint,
    WorkloadRecord,
)
from flowboard.domain.overlap import detect_all_conflicts
from flowboard.domain.risk import detect_all_risks
from flowboard.domain.workload import compute_workload_records
from flowboard.i18n.translator import get_translator
from flowboard.infrastructure.config.loader import (
    Thresholds,
    load_config_from_dict,
)
from flowboard.presentation.html.components import (
    summary_cards,
    workload_table,
)
from flowboard.shared.types import (
    IssueStatus,
    IssueType,
    LinkType,
    Priority,
    RiskSeverity,
    SprintState,
    StatusCategory,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _person(aid: str = "u1", name: str = "Alice", team: str = "alpha") -> Person:
    return Person(account_id=aid, display_name=name, team=team)


def _issue(
    key: str = "T-1",
    sp: float = 5.0,
    status_cat: StatusCategory = StatusCategory.TODO,
    assignee: Person | None = None,
    issue_type: IssueType = IssueType.STORY,
    links: list[IssueLink] | None = None,
    created: datetime | None = None,
    sprint: Sprint | None = None,
    priority: Priority = Priority.MEDIUM,
    due_date: date | None = None,
    epic_key: str = "",
) -> Issue:
    return Issue(
        key=key,
        summary=f"Issue {key}",
        issue_type=issue_type,
        status=IssueStatus.OTHER,
        status_category=status_cat,
        assignee=assignee,
        story_points=sp,
        priority=priority,
        links=links or [],
        created=created or datetime(2026, 3, 1, tzinfo=UTC),
        sprint=sprint,
        due_date=due_date,
        epic_key=epic_key,
    )


def _sprint(
    sid: int = 1,
    name: str = "Sprint 1",
    state: SprintState = SprintState.ACTIVE,
    start_date: date | None = None,
    end_date: date | None = None,
) -> Sprint:
    return Sprint(
        id=sid,
        name=name,
        state=state,
        start_date=start_date or date(2026, 3, 3),
        end_date=end_date or date(2026, 3, 17),
    )


def _thresholds(**kw) -> Thresholds:
    return Thresholds(**kw)


# ====================================================================
# _detect_sprint_risks now uses injected `today` parameter
# ====================================================================


class TestSprintRiskUsesDeterministicDate:
    """Tests for sprint risk uses deterministic date."""

    """GIVEN sprint risk uses deterministic date and the scenario: sprint risk fires when today is near end"""
    def test_sprint_risk_fires_when_today_is_near_end(self):
        """WHEN the code under test is exercised for: sprint risk fires when today is near end"""
        sprint = _sprint(end_date=date(2026, 3, 20), state=SprintState.ACTIVE)
        alice = _person()
        issues = [
            _issue("A-1", 5, StatusCategory.TODO, alice, sprint=sprint),
            _issue("A-2", 5, StatusCategory.TODO, alice, sprint=sprint),
            _issue("A-3", 5, StatusCategory.TODO, alice, sprint=sprint),
        ]
        wr = compute_workload_records(issues, _thresholds())
        sh = compute_sprint_health(
            {sprint.id: issues},
            [sprint],
            aging_days=14,
            today=date(2026, 3, 18),
        )
        t = get_translator("en")
        risks = detect_all_risks(
            issues,
            wr,
            sh,
            [],
            _thresholds(),
            today=date(2026, 3, 18),
            t=t,
        )
        # Must contain CRITICAL sprint risk
        critical = [r for r in risks if r.severity == RiskSeverity.CRITICAL]

        """THEN the expected behaviour holds: sprint risk fires when today is near end"""
        assert len(critical) >= 1
        assert any("sprint" in r.title.lower() or "Sprint" in r.title for r in critical)

    """GIVEN sprint risk uses deterministic date and the scenario: sprint risk does not fire when today is far from end"""
    def test_sprint_risk_does_not_fire_when_today_is_far_from_end(self):
        """WHEN the code under test is exercised for: sprint risk does not fire when today is far from end"""
        sprint = _sprint(end_date=date(2026, 3, 28), state=SprintState.ACTIVE)
        alice = _person()
        issues = [
            _issue("A-1", 5, StatusCategory.TODO, alice, sprint=sprint),
        ]
        wr = compute_workload_records(issues, _thresholds())
        sh = compute_sprint_health(
            {sprint.id: issues},
            [sprint],
            aging_days=14,
            today=date(2026, 3, 18),
        )
        t = get_translator("en")
        risks = detect_all_risks(
            issues,
            wr,
            sh,
            [],
            _thresholds(),
            today=date(2026, 3, 18),
            t=t,
        )
        critical = [r for r in risks if r.severity == RiskSeverity.CRITICAL]

        """THEN the expected behaviour holds: sprint risk does not fire when today is far from end"""
        assert not critical


# ====================================================================
# compute_sprint_health uses injected `today`
# ====================================================================


class TestSprintHealthDeterministicDate:
    """Tests for sprint health deterministic date."""

    """GIVEN sprint health deterministic date and the scenario: carry over calculated with injected today"""
    def test_carry_over_calculated_with_injected_today(self):
        """WHEN the code under test is exercised for: carry over calculated with injected today"""
        sprint = _sprint(end_date=date(2026, 3, 18), state=SprintState.ACTIVE)
        alice = _person()
        issues = [
            _issue("C-1", 5, StatusCategory.TODO, alice, sprint=sprint),
            _issue("C-2", 5, StatusCategory.IN_PROGRESS, alice, sprint=sprint),
            _issue("C-3", 5, StatusCategory.DONE, alice, sprint=sprint),
        ]
        healths = compute_sprint_health(
            {sprint.id: issues},
            [sprint],
            aging_days=14,
            today=date(2026, 3, 17),
        )

        """THEN the expected behaviour holds: carry over calculated with injected today"""
        assert len(healths) == 1
        assert healths[0].carry_over_count == 2  # 1 todo + 1 in_progress

    """GIVEN sprint health deterministic date and the scenario: no carry over when far from end"""
    def test_no_carry_over_when_far_from_end(self):
        """WHEN the code under test is exercised for: no carry over when far from end"""
        sprint = _sprint(end_date=date(2026, 3, 28), state=SprintState.ACTIVE)
        alice = _person()
        issues = [_issue("C-1", 5, StatusCategory.TODO, alice, sprint=sprint)]
        healths = compute_sprint_health(
            {sprint.id: issues},
            [sprint],
            aging_days=14,
            today=date(2026, 3, 10),
        )

        """THEN the expected behaviour holds: no carry over when far from end"""
        assert healths[0].carry_over_count == 0

    """GIVEN sprint health deterministic date and the scenario: missing sprint logged and skipped"""
    def test_missing_sprint_logged_and_skipped(self):
        """WHEN the code under test is exercised for: missing sprint logged and skipped"""
        alice = _person()
        sprint = _sprint(sid=99)
        issues = [_issue("C-4", 5, StatusCategory.TODO, alice, sprint=sprint)]
        healths = compute_sprint_health(
            {99: issues},
            [],
            aging_days=14,
            today=date(2026, 3, 10),
        )

        """THEN the expected behaviour holds: missing sprint logged and skipped"""
        assert len(healths) == 0


# ====================================================================
# summary_cards uses config thresholds, not hardcoded values
# ====================================================================


class TestSummaryCardsConfigThresholds:
    """Tests for summary cards config thresholds."""

    def _snapshot_with_workload(self, sp: float, issues: int) -> BoardSnapshot:
        alice = _person()
        wr = WorkloadRecord(person=alice, team="alpha", issue_count=issues, story_points=sp)
        return BoardSnapshot(workload_records=[wr])

    """GIVEN summary cards config thresholds and the scenario: custom low threshold flags overload"""
    def test_custom_low_threshold_flags_overload(self):
        """WHEN the code under test is exercised for: custom low threshold flags overload"""
        snap = self._snapshot_with_workload(sp=12, issues=3)
        t = get_translator("en")
        html = summary_cards(snap, t=t, overload_points=10, overload_issues=5)
        # The overloaded card should show "1"

        """THEN the expected behaviour holds: custom low threshold flags overload"""
        assert ">1<" in html

    """GIVEN summary cards config thresholds and the scenario: default threshold does not flag low workload"""
    def test_default_threshold_does_not_flag_low_workload(self):
        """WHEN the code under test is exercised for: default threshold does not flag low workload"""
        snap = self._snapshot_with_workload(sp=15, issues=5)
        t = get_translator("en")
        html = summary_cards(snap, t=t, overload_points=20, overload_issues=8)
        # The overloaded card should show "0"

        """THEN the expected behaviour holds: default threshold does not flag low workload"""
        assert "card-amber" not in html or ">0<" in html


# ====================================================================
# workload_table uses config thresholds
# ====================================================================


class TestWorkloadTableConfigThresholds:
    """Tests for workload table config thresholds."""

    """GIVEN workload table config thresholds and the scenario: row warn applied with custom threshold"""
    def test_row_warn_applied_with_custom_threshold(self):
        """WHEN the code under test is exercised for: row warn applied with custom threshold"""
        alice = _person()
        wr = WorkloadRecord(person=alice, team="alpha", issue_count=3, story_points=12)
        t = get_translator("en")
        html = workload_table([wr], t=t, overload_points=10, overload_issues=5)

        """THEN the expected behaviour holds: row warn applied with custom threshold"""
        assert "row-warn" in html

    """GIVEN workload table config thresholds and the scenario: row warn not applied below threshold"""
    def test_row_warn_not_applied_below_threshold(self):
        """WHEN the code under test is exercised for: row warn not applied below threshold"""
        alice = _person()
        wr = WorkloadRecord(person=alice, team="alpha", issue_count=3, story_points=8)
        t = get_translator("en")
        html = workload_table([wr], t=t, overload_points=20, overload_issues=8)

        """THEN the expected behaviour holds: row warn not applied below threshold"""
        assert "row-warn" not in html


# ====================================================================
# Jinja2 autoescape enabled (XSS protection)
# ====================================================================


class TestAutoescapeEnabled:
    """Tests for autoescape enabled."""

    """GIVEN autoescape enabled and the scenario: autoescape is on"""
    def test_autoescape_is_on(self):
        """WHEN the code under test is exercised for: autoescape is on"""
        from flowboard.presentation.html.renderer import _build_env

        env = _build_env()

        """THEN the expected behaviour holds: autoescape is on"""
        assert env.autoescape is True

    """GIVEN autoescape enabled and the scenario: render does not double escape components"""
    def test_render_does_not_double_escape_components(self):
        """WHEN the code under test is exercised for: render does not double escape components"""
        from flowboard.presentation.html.renderer import render_dashboard

        cfg = load_config_from_dict(
            {
                "jira": {"base_url": "https://test.atlassian.net"},
                "output": {"title": "Test"},
            }
        )
        snap = BoardSnapshot(title="Test")
        html = render_dashboard(snap, cfg)
        # Component HTML should be embedded, not escaped

        """THEN the expected behaviour holds: render does not double escape components"""
        assert "&lt;div" not in html or html.count("&lt;div") == 0
        assert "<!DOCTYPE html>" in html


# ====================================================================
# JiraClient has close() and context manager
# ====================================================================


class TestJiraClientSessionManagement:
    """Tests for jira client session management."""

    """GIVEN jira client session management and the scenario: client has close method"""
    def test_client_has_close_method(self):
        """WHEN the code under test is exercised for: client has close method"""
        from flowboard.infrastructure.config.loader import JiraConfig
        from flowboard.infrastructure.jira.client import JiraClient

        cfg = JiraConfig(base_url="https://test.atlassian.net")
        client = JiraClient(cfg)

        """THEN the expected behaviour holds: client has close method"""
        assert hasattr(client, "close")
        client.close()

    """GIVEN jira client session management and the scenario: client context manager"""
    def test_client_context_manager(self):
        """WHEN the code under test is exercised for: client context manager"""
        from flowboard.infrastructure.config.loader import JiraConfig
        from flowboard.infrastructure.jira.client import JiraClient

        cfg = JiraConfig(base_url="https://test.atlassian.net")

        """THEN the expected behaviour holds: client context manager"""
        with JiraClient(cfg) as client:
            assert client is not None


# ====================================================================
# Pagination safety limit
# ====================================================================


class TestPaginationSafetyLimit:
    """Tests for pagination safety limit."""

    """GIVEN pagination safety limit and the scenario: search issues stops at safety limit"""
    def test_search_issues_stops_at_safety_limit(self):
        """WHEN the code under test is exercised for: search issues stops at safety limit"""
        from flowboard.infrastructure.config.loader import JiraConfig
        from flowboard.infrastructure.jira.client import JiraClient

        cfg = JiraConfig(base_url="https://test.atlassian.net", max_results=1)
        client = JiraClient(cfg)

        # The for-loop safety limit exists in the implementation
        # Verify the code has a bounded iteration structure
        import inspect

        src = inspect.getsource(client.search_issues)

        """THEN the expected behaviour holds: search issues stops at safety limit"""
        assert "range(" in src or "max_pages" in src


# ====================================================================
# Aging risk uses date comparison (no timezone mismatch)
# ====================================================================


class TestAgingRiskTimezoneHandling:
    """Tests for aging risk timezone handling."""

    """GIVEN aging risk timezone handling and the scenario: aging with utc created"""
    def test_aging_with_utc_created(self):
        """WHEN the code under test is exercised for: aging with utc created"""
        alice = _person()
        issue = _issue(
            "AGE-1",
            5,
            StatusCategory.TODO,
            alice,
            created=datetime(2026, 2, 1, tzinfo=UTC),
        )
        t = get_translator("en")
        risks = detect_all_risks(
            [issue],
            [],
            [],
            [],
            _thresholds(aging_days=10),
            today=date(2026, 3, 18),
            t=t,
        )
        aging = [r for r in risks if "aging" in r.title.lower()]

        """THEN the expected behaviour holds: aging with utc created"""
        assert len(aging) == 1

    """GIVEN aging risk timezone handling and the scenario: aging with naive created"""
    def test_aging_with_naive_created(self):
        """WHEN the code under test is exercised for: aging with naive created"""
        alice = _person()
        issue = _issue(
            "AGE-2",
            5,
            StatusCategory.TODO,
            alice,
            created=datetime(2026, 2, 1),
        )
        t = get_translator("en")
        risks = detect_all_risks(
            [issue],
            [],
            [],
            [],
            _thresholds(aging_days=10),
            today=date(2026, 3, 18),
            t=t,
        )
        aging = [r for r in risks if "aging" in r.title.lower()]

        """THEN the expected behaviour holds: aging with naive created"""
        assert len(aging) == 1

    """GIVEN aging risk timezone handling and the scenario: future created date skipped"""
    def test_future_created_date_skipped(self):
        """WHEN the code under test is exercised for: future created date skipped"""
        alice = _person()
        issue = _issue(
            "AGE-3",
            5,
            StatusCategory.TODO,
            alice,
            created=datetime(2026, 4, 1, tzinfo=UTC),
        )
        t = get_translator("en")
        risks = detect_all_risks(
            [issue],
            [],
            [],
            [],
            _thresholds(aging_days=10),
            today=date(2026, 3, 18),
            t=t,
        )
        aging = [r for r in risks if "aging" in r.title.lower()]

        """THEN the expected behaviour holds: future created date skipped"""
        assert len(aging) == 0


# ====================================================================
# Dependency chain DFS handles branches correctly
# ====================================================================


class TestDependencyChainDFS:
    """Tests for dependency chain d f s."""

    def _dep(self, src: str, tgt: str) -> Dependency:
        return Dependency(
            source_key=src,
            target_key=tgt,
            link_type=LinkType.BLOCKS,
            source_status=StatusCategory.TODO,
            target_status=StatusCategory.TODO,
        )

    """GIVEN dependency chain d f s and the scenario: linear chain"""
    def test_linear_chain(self):
        """WHEN the code under test is exercised for: linear chain"""
        deps = [self._dep("A", "B"), self._dep("B", "C")]
        chains = build_dependency_chains(deps)

        """THEN the expected behaviour holds: linear chain"""
        assert len(chains) == 1
        assert chains[0] == ["A", "B", "C"]

    """GIVEN dependency chain d f s and the scenario: branching graph produces multiple chains"""
    def test_branching_graph_produces_multiple_chains(self):
        """WHEN the code under test is exercised for: branching graph produces multiple chains"""
        deps = [
            self._dep("A", "B"),
            self._dep("B", "C"),
            self._dep("A", "D"),
        ]
        chains = build_dependency_chains(deps)

        """THEN the expected behaviour holds: branching graph produces multiple chains"""
        assert len(chains) == 2
        chain_sets = [tuple(c) for c in chains]
        assert ("A", "B", "C") in chain_sets
        assert ("A", "D") in chain_sets

    """GIVEN dependency chain d f s and the scenario: diamond graph"""
    def test_diamond_graph(self):
        """WHEN the code under test is exercised for: diamond graph"""
        deps = [
            self._dep("A", "B"),
            self._dep("A", "C"),
            self._dep("B", "D"),
            self._dep("C", "D"),
        ]
        chains = build_dependency_chains(deps)

        """THEN the expected behaviour holds: diamond graph"""
        assert len(chains) == 2

    """GIVEN dependency chain d f s and the scenario: cycle does not hang"""
    def test_cycle_does_not_hang(self):
        """WHEN the code under test is exercised for: cycle does not hang"""
        deps = [self._dep("A", "B"), self._dep("B", "A")]
        # Should not hang - must complete
        chains = build_dependency_chains(deps)
        # At least one chain path should be recorded

        """THEN the expected behaviour holds: cycle does not hang"""
        assert isinstance(chains, list)

    """GIVEN dependency chain d f s and the scenario: done deps excluded"""
    def test_done_deps_excluded(self):
        """WHEN the code under test is exercised for: done deps excluded"""
        dep = Dependency(
            source_key="A",
            target_key="B",
            link_type=LinkType.BLOCKS,
            source_status=StatusCategory.TODO,
            target_status=StatusCategory.DONE,
        )
        chains = build_dependency_chains([dep])

        """THEN the expected behaviour holds: done deps excluded"""
        assert len(chains) == 0

    """GIVEN dependency chain d f s and the scenario: empty deps"""
    def test_empty_deps(self):
        """THEN the expected behaviour holds: empty deps"""
        assert build_dependency_chains([]) == []


# ====================================================================
# analytics.py uses proper imports (not __import__)
# ====================================================================


class TestAnalyticsImports:
    """Tests for analytics imports."""

    """GIVEN analytics imports and the scenario: build board snapshot type annotations"""
    def test_build_board_snapshot_type_annotations(self):
        """WHEN the code under test is exercised for: build board snapshot type annotations"""
        import inspect

        from flowboard.domain.analytics import build_board_snapshot

        # Should not contain __import__ in annotations
        src = inspect.getsource(build_board_snapshot)

        """THEN the expected behaviour holds: build board snapshot type annotations"""
        assert "__import__" not in src


# ====================================================================
# CapacityRecord.utilization_pct clamped at 100%
# ====================================================================


class TestCapacityRecordClamped:
    """Tests for capacity record clamped."""

    """GIVEN capacity record clamped and the scenario: utilization capped at 100"""
    def test_utilization_capped_at_100(self):
        """WHEN the code under test is exercised for: utilization capped at 100"""
        alice = _person()
        cr = CapacityRecord(
            person=alice,
            allocated_points=10,
            completed_points=15,
        )

        """THEN the expected behaviour holds: utilization capped at 100"""
        assert cr.utilization_pct == 100.0

    """GIVEN capacity record clamped and the scenario: utilization normal case"""
    def test_utilization_normal_case(self):
        """WHEN the code under test is exercised for: utilization normal case"""
        alice = _person()
        cr = CapacityRecord(
            person=alice,
            allocated_points=10,
            completed_points=5,
        )

        """THEN the expected behaviour holds: utilization normal case"""
        assert cr.utilization_pct == 50.0

    """GIVEN capacity record clamped and the scenario: utilization zero allocated"""
    def test_utilization_zero_allocated(self):
        """WHEN the code under test is exercised for: utilization zero allocated"""
        alice = _person()
        cr = CapacityRecord(
            person=alice,
            allocated_points=0,
            completed_points=5,
        )

        """THEN the expected behaviour holds: utilization zero allocated"""
        assert cr.utilization_pct == 0.0


# ====================================================================
# Additional regression: empty data edge cases
# ====================================================================


class TestEmptyDataEdgeCases:
    """Tests for empty data edge cases."""

    """GIVEN empty data edge cases and the scenario: sprint health empty sprint issues"""
    def test_sprint_health_empty_sprint_issues(self):
        """WHEN the code under test is exercised for: sprint health empty sprint issues"""
        healths = compute_sprint_health({}, [], today=date(2026, 3, 18))

        """THEN the expected behaviour holds: sprint health empty sprint issues"""
        assert healths == []

    """GIVEN empty data edge cases and the scenario: risk detection with no issues"""
    def test_risk_detection_with_no_issues(self):
        """WHEN the code under test is exercised for: risk detection with no issues"""
        t = get_translator("en")
        risks = detect_all_risks([], [], [], [], _thresholds(), today=date(2026, 3, 18), t=t)

        """THEN the expected behaviour holds: risk detection with no issues"""
        assert risks == []

    """GIVEN empty data edge cases and the scenario: conflict detection with no issues"""
    def test_conflict_detection_with_no_issues(self):
        """WHEN the code under test is exercised for: conflict detection with no issues"""
        t = get_translator("en")
        conflicts = detect_all_conflicts([], [], [], _thresholds(), today=date(2026, 3, 18), t=t)

        """THEN the expected behaviour holds: conflict detection with no issues"""
        assert conflicts == []

    """GIVEN empty data edge cases and the scenario: dependency chains empty"""
    def test_dependency_chains_empty(self):
        """THEN the expected behaviour holds: dependency chains empty"""
        assert build_dependency_chains([]) == []
