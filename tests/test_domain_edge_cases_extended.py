"""Extended domain edge case tests — simulation resources, risk filtering, backlog quality, config deep copy."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from flowboard.domain.models import (
    Issue,
    IssueLink,
    Person,
    Sprint,
    SprintHealth,
    Team,
    WorkloadRecord,
)
from flowboard.domain.pi import _to_wd_set
from flowboard.domain.scrum import (
    compute_backlog_quality,
    compute_scope_changes,
)
from flowboard.domain.simulation import _simulate_workloads
from flowboard.i18n.translator import Translator
from flowboard.infrastructure.config.loader import (
    Thresholds,
    load_config_from_dict,
)
from flowboard.shared.types import (
    IssueType,
    LinkType,
    Priority,
    SprintState,
    StatusCategory,
)

# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------


def _person(name: str = "Alice", team: str = "api") -> Person:
    return Person(account_id=name.lower(), display_name=name, email="", team=team)


def _sprint(sid: int = 1, name: str = "Sprint 1") -> Sprint:
    return Sprint(
        id=sid,
        name=name,
        board_id=1,
        state=SprintState.ACTIVE,
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 14),
    )


def _issue(
    key: str = "T-1",
    *,
    assignee: Person | None = None,
    sprint: Sprint | None = None,
    status_cat: StatusCategory = StatusCategory.IN_PROGRESS,
    issue_type: IssueType = IssueType.STORY,
    sp: float = 5.0,
    created: datetime | None = None,
    links: list[IssueLink] | None = None,
    priority: Priority = Priority.MEDIUM,
) -> Issue:
    return Issue(
        key=key,
        summary=f"Issue {key}",
        issue_type=issue_type,
        status_category=status_cat,
        assignee=assignee,
        story_points=sp,
        sprint=sprint,
        created=created or datetime(2026, 3, 1, tzinfo=UTC),
        priority=priority,
        links=links or [],
    )


def _sprint_health(sprint: Sprint) -> SprintHealth:
    return SprintHealth(
        sprint=sprint,
        total_issues=5,
        done_issues=2,
        in_progress_issues=2,
        todo_issues=1,
        blocked_issues=0,
        total_points=25.0,
        completed_points=10.0,
        aging_issues=0,
    )


def _minimal_config() -> dict:
    return {
        "jira": {"base_url": "https://test.atlassian.net"},
        "output": {"path": "output/test.html"},
    }


# =======================================================================
# JSON decode error handling in JiraClient._get_json
# =======================================================================


class TestPiEmptyWorkingDaysGuard:
    """Covers: empty working_days must raise ValueError, not hang."""

    def test_empty_frozenset_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            _to_wd_set(frozenset())

    def test_empty_list_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            _to_wd_set([])

    def test_none_uses_defaults(self):
        result = _to_wd_set(None)
        assert len(result) == 5  # Mon-Fri


# =======================================================================
# Scope churn wrong denominator
# =======================================================================


class TestScopeChurnDenominator:
    """Covers: churn must be calculated against original scope, not total."""

    def test_churn_is_added_over_original(self):
        sp = _sprint()
        sh = _sprint_health(sp)
        alice = _person("Alice")
        # 2 original, 1 added = 50% churn (1/2), not 33% (1/3)
        issues = [
            _issue("O-1", assignee=alice, sprint=sp, created=datetime(2026, 2, 28, tzinfo=UTC)),
            _issue("O-2", assignee=alice, sprint=sp, created=datetime(2026, 2, 28, tzinfo=UTC)),
            _issue("A-1", assignee=alice, sprint=sp, created=datetime(2026, 3, 5, tzinfo=UTC)),
        ]
        reports = compute_scope_changes(issues, [sh])
        assert reports[0].churn_pct == 50.0  # 1 added / 2 original * 100


# =======================================================================
# Simulation resource removal must have effect
# =======================================================================


class TestSimulationResourceRemoval:
    """Covers: removing a resource must increase remaining members' load."""

    def test_removing_member_increases_load(self):
        teams = [Team(key="api", name="API", members=("a", "b", "c"))]
        wrs = [
            WorkloadRecord(
                person=_person("A", "api"),
                team="api",
                issue_count=3,
                story_points=9.0,
                in_progress_count=2,
                blocked_count=0,
            ),
            WorkloadRecord(
                person=_person("B", "api"),
                team="api",
                issue_count=3,
                story_points=9.0,
                in_progress_count=2,
                blocked_count=0,
            ),
            WorkloadRecord(
                person=_person("C", "api"),
                team="api",
                issue_count=3,
                story_points=9.0,
                in_progress_count=2,
                blocked_count=0,
            ),
        ]
        from flowboard.domain.simulation import ResourceChange, SimulationScenario

        scenario = SimulationScenario(
            id="minus1",
            name="-1 API",
            description="Remove one from API",
            changes=(ResourceChange(team_key="api", delta=-1),),
        )
        sim_workloads, _metrics = _simulate_workloads(wrs, teams, scenario, Thresholds())
        # After removing 1, remaining 2 members should carry more load
        existing_loads = [w["story_points"] for w in sim_workloads if not w.get("is_new")]
        assert all(sp > 9.0 for sp in existing_loads)


# =======================================================================
# Risk unfiltered blocker links
# =======================================================================


class TestRiskBlockerLinkFiltering:
    """Covers: only IS_BLOCKED_BY/DEPENDS_ON links should appear as blockers."""

    def test_relates_to_not_listed_as_blocker(self):
        from flowboard.domain.risk import _detect_blocked_risks

        t = Translator("en")

        relates_link = IssueLink(
            target_key="R-1",
            link_type=LinkType.RELATES_TO,
            is_resolved=False,
            target_summary="Related",
        )
        blocks_link = IssueLink(
            target_key="B-1",
            link_type=LinkType.IS_BLOCKED_BY,
            is_resolved=False,
            target_summary="Blocker",
        )
        issue = _issue("T-1", links=[relates_link, blocks_link])
        issue = Issue(
            key="T-1",
            summary="Test",
            issue_type=IssueType.STORY,
            status_category=StatusCategory.IN_PROGRESS,
            story_points=5,
            links=[relates_link, blocks_link],
        )
        # The issue is blocked (has IS_BLOCKED_BY link)
        signals = _detect_blocked_risks([issue], t=t)
        # Find the per-issue signal
        per_issue = [s for s in signals if s.category.value == "blocked" and "T-1" in s.title]
        assert len(per_issue) == 1
        # The affected_keys should include B-1 but not R-1
        assert "B-1" in per_issue[0].affected_keys
        assert "R-1" not in per_issue[0].affected_keys


# =======================================================================
# Backlog quality score includes no_priority
# =======================================================================


class TestBacklogQualityScoreIncludesNoPriority:
    """Covers: no_priority must reduce the quality score."""

    def test_score_penalizes_missing_priority(self):
        issues = [
            _issue("B-1", status_cat=StatusCategory.TODO, priority=Priority.UNSET, sp=0),
        ]
        report = compute_backlog_quality(issues, stale_days=30, today=date(2026, 3, 10))
        # With 5 checks per item and 2 issues found (no_est=1 from sp=0, no_pri=1), score < 100
        assert report.quality_score < 100.0
        assert report.no_priority == 1


# =======================================================================
# Shallow copy mutation in load_config_from_dict
# =======================================================================


class TestConfigLoadDeepCopy:
    """Covers: load_config_from_dict must not mutate the input dict."""

    def test_input_dict_not_mutated(self):
        original = _minimal_config()
        original_jira = original["jira"].copy()
        load_config_from_dict(original)
        assert original["jira"] == original_jira  # original not mutated


# =======================================================================
# Fixes from second production audit pass
# =======================================================================


class TestPluralEmptyFormKeys:
    """Plural() crashed with IndexError when called with no form_keys."""

    def test_plural_no_form_keys_returns_str_n(self):
        from flowboard.i18n.translator import Translator

        t = Translator("en")
        result = t.plural(5)
        assert result == "5"

    def test_plural_single_form_key_works(self):
        from flowboard.i18n.translator import Translator

        t = Translator("en")
        result = t.plural(1, "sprint.label")
        assert isinstance(result, str)
        assert len(result) > 0


class TestScopeChangeAllAdded:
    """Churn reported 0% when all items were added post-sprint (no originals)."""

    def test_all_items_added_reports_100_churn(self):
        """When every issue was created after sprint start and no original items
        existed, churn must be 100% (not 0%)."""
        from flowboard.domain.scrum_compute import compute_scope_changes

        sprint_start = date(2020, 1, 1)

        sprint = MagicMock()
        sprint.name = "Sprint 99"
        sprint.start_date = sprint_start
        sprint.end_date = sprint_start + timedelta(days=14)
        sprint.state = MagicMock(value="active")

        sh = MagicMock()
        sh.sprint = sprint

        issues = []
        for i in range(3):
            iss = MagicMock()
            iss.key = f"ADD-{i}"
            iss.summary = f"Added task {i}"
            iss.story_points = 3.0
            iss.status_category = StatusCategory.IN_PROGRESS
            iss.assignee = None
            iss.is_blocked = False
            iss.created = datetime(2020, 1, 15, tzinfo=UTC)  # well after start+1 day
            iss.sprint = sprint
            iss.labels = []
            issues.append(iss)

        reports = compute_scope_changes(issues, [sh])
        assert len(reports) == 1
        assert reports[0].churn_pct == 100.0
        assert reports[0].stability != "stable"


class TestInvalidPIDateSafe:
    """Invalid pi.start_date no longer crashes analytics pipeline."""

    def test_invalid_date_raises_value_error(self):
        from flowboard.domain.pi import compute_pi_snapshot

        with pytest.raises(ValueError):
            compute_pi_snapshot(
                name="PI",
                pi_start_iso="not-a-date",
                sprint_length=14,
                num_sprints=5,
                working_days=[0, 1, 2, 3, 4],
            )
