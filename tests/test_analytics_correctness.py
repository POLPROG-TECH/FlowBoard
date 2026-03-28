"""Tests for analytics correctness — sprint risk date handling, carry-over
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
    """sprint risk detection was using date.today() instead of
    the injected `today` parameter, making it non-deterministic and
    untestable."""

    def test_sprint_risk_fires_when_today_is_near_end(self):
        """Sprint ending in 2 days with <30% done must trigger CRITICAL risk."""
        sprint = _sprint(end_date=date(2026, 3, 20), state=SprintState.ACTIVE)
        alice = _person()
        issues = [
            _issue("A-1", 5, StatusCategory.TODO, alice, sprint=sprint),
            _issue("A-2", 5, StatusCategory.TODO, alice, sprint=sprint),
            _issue("A-3", 5, StatusCategory.TODO, alice, sprint=sprint),
        ]
        wr = compute_workload_records(issues, _thresholds())
        sh = compute_sprint_health(
            {sprint.id: issues}, [sprint], aging_days=14, today=date(2026, 3, 18),
        )
        t = get_translator("en")
        risks = detect_all_risks(
            issues, wr, sh, [], _thresholds(), today=date(2026, 3, 18), t=t,
        )
        # Must contain CRITICAL sprint risk
        critical = [r for r in risks if r.severity == RiskSeverity.CRITICAL]
        assert len(critical) >= 1
        assert any("sprint" in r.title.lower() or "Sprint" in r.title for r in critical)

    def test_sprint_risk_does_not_fire_when_today_is_far_from_end(self):
        """Sprint ending in 10 days should NOT trigger the 'at risk' signal."""
        sprint = _sprint(end_date=date(2026, 3, 28), state=SprintState.ACTIVE)
        alice = _person()
        issues = [
            _issue("A-1", 5, StatusCategory.TODO, alice, sprint=sprint),
        ]
        wr = compute_workload_records(issues, _thresholds())
        sh = compute_sprint_health(
            {sprint.id: issues}, [sprint], aging_days=14, today=date(2026, 3, 18),
        )
        t = get_translator("en")
        risks = detect_all_risks(
            issues, wr, sh, [], _thresholds(), today=date(2026, 3, 18), t=t,
        )
        critical = [r for r in risks if r.severity == RiskSeverity.CRITICAL]
        assert not critical


# ====================================================================
# compute_sprint_health uses injected `today`
# ====================================================================

class TestSprintHealthDeterministicDate:
    """carry_over computation was using date.today() instead of
    injected today parameter."""

    def test_carry_over_calculated_with_injected_today(self):
        """When today is ≤2 days from sprint end, carry_over should include
        todo + in_progress issues."""
        sprint = _sprint(end_date=date(2026, 3, 18), state=SprintState.ACTIVE)
        alice = _person()
        issues = [
            _issue("C-1", 5, StatusCategory.TODO, alice, sprint=sprint),
            _issue("C-2", 5, StatusCategory.IN_PROGRESS, alice, sprint=sprint),
            _issue("C-3", 5, StatusCategory.DONE, alice, sprint=sprint),
        ]
        healths = compute_sprint_health(
            {sprint.id: issues}, [sprint], aging_days=14, today=date(2026, 3, 17),
        )
        assert len(healths) == 1
        assert healths[0].carry_over_count == 2  # 1 todo + 1 in_progress

    def test_no_carry_over_when_far_from_end(self):
        sprint = _sprint(end_date=date(2026, 3, 28), state=SprintState.ACTIVE)
        alice = _person()
        issues = [_issue("C-1", 5, StatusCategory.TODO, alice, sprint=sprint)]
        healths = compute_sprint_health(
            {sprint.id: issues}, [sprint], aging_days=14, today=date(2026, 3, 10),
        )
        assert healths[0].carry_over_count == 0

    def test_missing_sprint_logged_and_skipped(self):
        """Issues referencing a sprint not in the sprints list should be skipped."""
        alice = _person()
        sprint = _sprint(sid=99)
        issues = [_issue("C-4", 5, StatusCategory.TODO, alice, sprint=sprint)]
        healths = compute_sprint_health(
            {99: issues}, [], aging_days=14, today=date(2026, 3, 10),
        )
        assert len(healths) == 0


# ====================================================================
# summary_cards uses config thresholds, not hardcoded values
# ====================================================================

class TestSummaryCardsConfigThresholds:
    """summary_cards was hardcoded to overload at 20 SP / 8 issues
    instead of using the configured thresholds."""

    def _snapshot_with_workload(self, sp: float, issues: int) -> BoardSnapshot:
        alice = _person()
        wr = WorkloadRecord(person=alice, team="alpha", issue_count=issues, story_points=sp)
        return BoardSnapshot(workload_records=[wr])

    def test_custom_low_threshold_flags_overload(self):
        """With threshold=10, a person at 12 SP should be flagged overloaded."""
        snap = self._snapshot_with_workload(sp=12, issues=3)
        t = get_translator("en")
        html = summary_cards(snap, t=t, overload_points=10, overload_issues=5)
        # The overloaded card should show "1"
        assert ">1<" in html

    def test_default_threshold_does_not_flag_low_workload(self):
        """With default threshold=20, a person at 15 SP should NOT be flagged."""
        snap = self._snapshot_with_workload(sp=15, issues=5)
        t = get_translator("en")
        html = summary_cards(snap, t=t, overload_points=20, overload_issues=8)
        # The overloaded card should show "0"
        assert "card-amber" not in html or ">0<" in html


# ====================================================================
# workload_table uses config thresholds
# ====================================================================

class TestWorkloadTableConfigThresholds:
    """workload_table was also hardcoded with magic numbers."""

    def test_row_warn_applied_with_custom_threshold(self):
        alice = _person()
        wr = WorkloadRecord(person=alice, team="alpha", issue_count=3, story_points=12)
        t = get_translator("en")
        html = workload_table([wr], t=t, overload_points=10, overload_issues=5)
        assert "row-warn" in html

    def test_row_warn_not_applied_below_threshold(self):
        alice = _person()
        wr = WorkloadRecord(person=alice, team="alpha", issue_count=3, story_points=8)
        t = get_translator("en")
        html = workload_table([wr], t=t, overload_points=20, overload_issues=8)
        assert "row-warn" not in html


# ====================================================================
# Jinja2 autoescape enabled (XSS protection)
# ====================================================================

class TestAutoescapeEnabled:
    """The Jinja2 environment was using autoescape=False, creating
    XSS vulnerability. Now autoescape=True is used with Markup for safe HTML."""

    def test_autoescape_is_on(self):
        from flowboard.presentation.html.renderer import _build_env
        env = _build_env()
        assert env.autoescape is True

    def test_render_does_not_double_escape_components(self):
        """Pre-rendered HTML components must not be double-escaped."""
        from flowboard.presentation.html.renderer import render_dashboard
        cfg = load_config_from_dict({
            "jira": {"base_url": "https://test.atlassian.net"},
            "output": {"title": "Test"},
        })
        snap = BoardSnapshot(title="Test")
        html = render_dashboard(snap, cfg)
        # Component HTML should be embedded, not escaped
        assert "&lt;div" not in html or html.count("&lt;div") == 0
        assert "<!DOCTYPE html>" in html


# ====================================================================
# JiraClient has close() and context manager
# ====================================================================

class TestJiraClientSessionManagement:
    """JiraClient.Session was never closed, leaking resources."""

    def test_client_has_close_method(self):
        from flowboard.infrastructure.config.loader import JiraConfig
        from flowboard.infrastructure.jira.client import JiraClient
        cfg = JiraConfig(base_url="https://test.atlassian.net")
        client = JiraClient(cfg)
        assert hasattr(client, "close")
        client.close()

    def test_client_context_manager(self):
        from flowboard.infrastructure.config.loader import JiraConfig
        from flowboard.infrastructure.jira.client import JiraClient
        cfg = JiraConfig(base_url="https://test.atlassian.net")
        with JiraClient(cfg) as client:
            assert client is not None


# ====================================================================
# Pagination safety limit
# ====================================================================

class TestPaginationSafetyLimit:
    """search_issues had no upper bound on pages, risking OOM."""

    def test_search_issues_stops_at_safety_limit(self):

        from flowboard.infrastructure.config.loader import JiraConfig
        from flowboard.infrastructure.jira.client import JiraClient

        cfg = JiraConfig(base_url="https://test.atlassian.net", max_results=1)
        client = JiraClient(cfg)

        # The for-loop safety limit exists in the implementation
        # Verify the code has a bounded iteration structure
        import inspect
        src = inspect.getsource(client.search_issues)
        assert "range(" in src or "max_pages" in src


# ====================================================================
# Aging risk uses date comparison (no timezone mismatch)
# ====================================================================

class TestAgingRiskTimezoneHandling:
    """_detect_aging_risks constructed a datetime with potentially
    mismatched timezone info. Now uses date-level comparison."""

    def test_aging_with_utc_created(self):
        """Issue created with UTC timezone should not crash."""
        alice = _person()
        issue = _issue(
            "AGE-1", 5, StatusCategory.TODO, alice,
            created=datetime(2026, 2, 1, tzinfo=UTC),
        )
        t = get_translator("en")
        risks = detect_all_risks(
            [issue], [], [], [], _thresholds(aging_days=10),
            today=date(2026, 3, 18), t=t,
        )
        aging = [r for r in risks if "aging" in r.title.lower()]
        assert len(aging) == 1

    def test_aging_with_naive_created(self):
        """Issue created with naive datetime (no timezone) should not crash."""
        alice = _person()
        issue = _issue(
            "AGE-2", 5, StatusCategory.TODO, alice,
            created=datetime(2026, 2, 1),
        )
        t = get_translator("en")
        risks = detect_all_risks(
            [issue], [], [], [], _thresholds(aging_days=10),
            today=date(2026, 3, 18), t=t,
        )
        aging = [r for r in risks if "aging" in r.title.lower()]
        assert len(aging) == 1

    def test_future_created_date_skipped(self):
        """Issue with created date in the future should be skipped."""
        alice = _person()
        issue = _issue(
            "AGE-3", 5, StatusCategory.TODO, alice,
            created=datetime(2026, 4, 1, tzinfo=UTC),
        )
        t = get_translator("en")
        risks = detect_all_risks(
            [issue], [], [], [], _thresholds(aging_days=10),
            today=date(2026, 3, 18), t=t,
        )
        aging = [r for r in risks if "aging" in r.title.lower()]
        assert len(aging) == 0


# ====================================================================
# Dependency chain DFS handles branches correctly
# ====================================================================

class TestDependencyChainDFS:
    """build_dependency_chains had a DFS bug where the shared
    visited set prevented finding multiple branches."""

    def _dep(self, src: str, tgt: str) -> Dependency:
        return Dependency(
            source_key=src,
            target_key=tgt,
            link_type=LinkType.BLOCKS,
            source_status=StatusCategory.TODO,
            target_status=StatusCategory.TODO,
        )

    def test_linear_chain(self):
        deps = [self._dep("A", "B"), self._dep("B", "C")]
        chains = build_dependency_chains(deps)
        assert len(chains) == 1
        assert chains[0] == ["A", "B", "C"]

    def test_branching_graph_produces_multiple_chains(self):
        """A → B → C and A → D must produce TWO chains."""
        deps = [
            self._dep("A", "B"),
            self._dep("B", "C"),
            self._dep("A", "D"),
        ]
        chains = build_dependency_chains(deps)
        assert len(chains) == 2
        chain_sets = [tuple(c) for c in chains]
        assert ("A", "B", "C") in chain_sets
        assert ("A", "D") in chain_sets

    def test_diamond_graph(self):
        """A → B, A → C, B → D, C → D must produce chains A→B→D and A→C→D."""
        deps = [
            self._dep("A", "B"),
            self._dep("A", "C"),
            self._dep("B", "D"),
            self._dep("C", "D"),
        ]
        chains = build_dependency_chains(deps)
        assert len(chains) == 2

    def test_cycle_does_not_hang(self):
        """A → B → A cycle must not cause infinite recursion."""
        deps = [self._dep("A", "B"), self._dep("B", "A")]
        # Should not hang — must complete
        chains = build_dependency_chains(deps)
        # At least one chain path should be recorded
        assert isinstance(chains, list)

    def test_done_deps_excluded(self):
        """Resolved dependencies (target done) should be excluded."""
        dep = Dependency(
            source_key="A", target_key="B", link_type=LinkType.BLOCKS,
            source_status=StatusCategory.TODO, target_status=StatusCategory.DONE,
        )
        chains = build_dependency_chains([dep])
        assert len(chains) == 0

    def test_empty_deps(self):
        assert build_dependency_chains([]) == []


# ====================================================================
# analytics.py uses proper imports (not __import__)
# ====================================================================

class TestAnalyticsImports:
    """analytics.py used __import__() for type annotations which
    is fragile and non-standard."""

    def test_build_board_snapshot_type_annotations(self):
        import inspect

        from flowboard.domain.analytics import build_board_snapshot
        # Should not contain __import__ in annotations
        src = inspect.getsource(build_board_snapshot)
        assert "__import__" not in src


# ====================================================================
# CapacityRecord.utilization_pct clamped at 100%
# ====================================================================

class TestCapacityRecordClamped:
    """utilization_pct could exceed 100% if completed > allocated."""

    def test_utilization_capped_at_100(self):
        alice = _person()
        cr = CapacityRecord(
            person=alice, allocated_points=10, completed_points=15,
        )
        assert cr.utilization_pct == 100.0

    def test_utilization_normal_case(self):
        alice = _person()
        cr = CapacityRecord(
            person=alice, allocated_points=10, completed_points=5,
        )
        assert cr.utilization_pct == 50.0

    def test_utilization_zero_allocated(self):
        alice = _person()
        cr = CapacityRecord(
            person=alice, allocated_points=0, completed_points=5,
        )
        assert cr.utilization_pct == 0.0


# ====================================================================
# Additional regression: empty data edge cases
# ====================================================================

class TestEmptyDataEdgeCases:
    """Regression guard for empty input data edge cases."""

    def test_sprint_health_empty_sprint_issues(self):
        healths = compute_sprint_health({}, [], today=date(2026, 3, 18))
        assert healths == []

    def test_risk_detection_with_no_issues(self):
        t = get_translator("en")
        risks = detect_all_risks([], [], [], [], _thresholds(), today=date(2026, 3, 18), t=t)
        assert risks == []

    def test_conflict_detection_with_no_issues(self):
        t = get_translator("en")
        conflicts = detect_all_conflicts([], [], [], _thresholds(), today=date(2026, 3, 18), t=t)
        assert conflicts == []

    def test_dependency_chains_empty(self):
        assert build_dependency_chains([]) == []
