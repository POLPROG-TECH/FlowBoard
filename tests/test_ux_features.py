"""Tests for UX features — table sorting attributes, table container structure,
dependency/blocker detail components, i18n key coverage, renderer context,
chart theming, CSS animations, table engine JavaScript, and footer redesign.
"""

from __future__ import annotations

import json
import typing
from datetime import UTC, datetime
from pathlib import Path

import pytest

from flowboard.domain.models import (
    BoardSnapshot,
    Dependency,
    Issue,
    IssueLink,
    Person,
    WorkloadRecord,
)
from flowboard.domain.risk import RiskCategory, RiskSeverity, RiskSignal
from flowboard.i18n.translator import get_translator
from flowboard.presentation.html.components import (
    dependency_table,
    deps_blockers_detail,
    issues_table,
    risk_table,
    workload_table,
)
from flowboard.shared.types import (
    IssueStatus,
    IssueType,
    LinkType,
    Priority,
    StatusCategory,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _person(name: str = "Alice", team: str = "Alpha") -> Person:
    return Person(account_id=f"acc-{name.lower()}", display_name=name, team=team)


def _blocking_link(target: str = "OTHER-1") -> IssueLink:
    """Create an unresolved IS_BLOCKED_BY link to make an issue blocked."""
    return IssueLink(target_key=target, link_type=LinkType.IS_BLOCKED_BY, is_resolved=False)


def _issue(
    key: str = "TEST-1",
    summary: str = "Test issue",
    assignee: Person | None = None,
    priority: Priority = Priority.HIGH,
    status_category: StatusCategory = StatusCategory.IN_PROGRESS,
    blocked: bool = False,
    links: list | None = None,
    components: list[str] | None = None,
    age_days_approx: int | None = None,
) -> Issue:
    created = datetime.now(UTC)
    if age_days_approx:
        from datetime import timedelta

        created = datetime.now(UTC) - timedelta(days=age_days_approx)
    issue_links = links or []
    if blocked and not issue_links:
        issue_links = [_blocking_link()]
    return Issue(
        key=key,
        summary=summary,
        issue_type=IssueType.TASK,
        priority=priority,
        status=IssueStatus.IN_PROGRESS,
        status_category=status_category,
        assignee=assignee,
        created=created,
        links=issue_links,
        components=components or [],
    )


def _snapshot(
    issues: list[Issue] | None = None,
    dependencies: list[Dependency] | None = None,
) -> BoardSnapshot:
    return BoardSnapshot(
        title="Test Board",
        issues=issues or [],
        dependencies=dependencies or [],
    )


# ---------------------------------------------------------------------------
# Table Container Structure Tests
# ---------------------------------------------------------------------------


class TestTableContainerStructure:
    """Verify fb-table-container wrapping for all table functions."""

    def test_workload_table_container(self):
        wr = WorkloadRecord(person=_person(), team="alpha", issue_count=3, story_points=10)
        html = workload_table([wr], t=get_translator("en"))
        assert 'class="fb-table-container"' in html
        assert 'data-table-id="workload"' in html
        assert 'data-total-rows="1"' in html

    def test_risk_table_container(self):
        sig = RiskSignal(
            severity=RiskSeverity.HIGH,
            category=RiskCategory.OVERLOAD,
            title="Test",
            description="Test desc",
        )
        html = risk_table([sig], t=get_translator("en"))
        assert 'class="fb-table-container"' in html
        assert 'data-table-id="risks"' in html
        assert 'data-total-rows="1"' in html

    def test_issues_table_container(self):
        issue = _issue()
        html = issues_table([issue], t=get_translator("en"))
        assert 'class="fb-table-container"' in html
        assert 'data-table-id="issues"' in html
        assert 'data-total-rows="1"' in html

    def test_dependency_table_container(self):
        dep = Dependency(
            source_key="A-1",
            target_key="A-2",
            link_type=LinkType.BLOCKS,
        )
        snap = _snapshot(dependencies=[dep])
        html = dependency_table(snap, t=get_translator("en"))
        assert 'class="fb-table-container"' in html
        assert 'data-table-id="deps"' in html
        assert 'data-total-rows="1"' in html

    def test_total_rows_matches_record_count(self):
        records = [
            WorkloadRecord(person=_person(f"P{i}"), team="t", issue_count=i, story_points=i)
            for i in range(1, 6)
        ]
        html = workload_table(records, t=get_translator("en"))
        assert 'data-total-rows="5"' in html


# ---------------------------------------------------------------------------
# Table Sorting Attribute Tests
# ---------------------------------------------------------------------------


class TestTableSortAttributes:
    """Verify data-sort-type on headers and data-sort-value on cells."""

    def test_workload_header_sort_types(self):
        wr = WorkloadRecord(person=_person(), team="alpha", issue_count=3, story_points=10)
        html = workload_table([wr], t=get_translator("en"))
        assert 'data-sort-type="text"' in html
        assert 'data-sort-type="num"' in html

    def test_workload_cell_sort_values(self):
        wr = WorkloadRecord(person=_person("Bob"), team="alpha", issue_count=3, story_points=10)
        html = workload_table([wr], t=get_translator("en"))
        assert 'data-sort-value="Bob"' in html
        assert 'data-sort-value="alpha"' in html
        assert 'data-sort-value="3"' in html
        assert 'data-sort-value="10"' in html

    def test_risk_header_sort_types(self):
        sig = RiskSignal(
            severity=RiskSeverity.CRITICAL,
            category=RiskCategory.OVERLOAD,
            title="Test",
            description="Desc",
        )
        html = risk_table([sig], t=get_translator("en"))
        assert 'data-sort-type="num"' in html
        assert 'data-sort-type="text"' in html

    def test_risk_severity_numeric_sort_value(self):
        sig = RiskSignal(
            severity=RiskSeverity.CRITICAL,
            category=RiskCategory.OVERLOAD,
            title="Critical Risk",
            description="Desc",
        )
        html = risk_table([sig], t=get_translator("en"))
        # Critical = 0 (highest priority, sorted first)
        assert 'data-sort-value="0"' in html

    def test_issues_priority_sort_value(self):
        issue = _issue(priority=Priority.HIGH)
        html = issues_table([issue], t=get_translator("en"))
        # HIGH priority should have a numeric sort value
        assert 'data-sort-value="' in html

    def test_dependency_table_has_sort_attributes(self):
        dep = Dependency(
            source_key="A-1",
            target_key="A-2",
            link_type=LinkType.BLOCKS,
        )
        snap = _snapshot(dependencies=[dep])
        html = dependency_table(snap, t=get_translator("en"))
        assert 'data-sort-type="text"' in html
        assert 'data-sort-value="A-1"' in html
        assert 'data-sort-value="A-2"' in html


# ---------------------------------------------------------------------------
# Dependencies & Blockers Detail View Tests
# ---------------------------------------------------------------------------


class TestDepsBlockersDetail:
    """Verify the deps_blockers_detail component."""

    def test_empty_snapshot_shows_empty_state(self):
        snap = _snapshot()
        html = deps_blockers_detail(snap, t=get_translator("en"))
        assert "card-value" in html
        assert ">0<" in html  # Zero blocked items

    def test_summary_cards_present(self):
        snap = _snapshot()
        html = deps_blockers_detail(snap, t=get_translator("en"))
        assert "summary-card" in html
        assert "card-danger" in html
        assert "card-warning" in html
        assert "card-default" in html

    def test_blocked_issues_shown(self):
        blocked = _issue(
            key="BLK-1",
            summary="Blocked work",
            assignee=_person("Charlie"),
            blocked=True,
            age_days_approx=10,
            links=[],
        )
        snap = _snapshot(issues=[blocked])
        html = deps_blockers_detail(snap, t=get_translator("en"))
        assert "BLK-1" in html
        assert "Charlie" in html

    def test_cross_team_deps_counted(self):
        dep = Dependency(
            source_key="A-1",
            target_key="B-1",
            link_type=LinkType.BLOCKS,
        )
        issues = [
            _issue(key="A-1", components=["Frontend"]),
            _issue(key="B-1", components=["Backend"]),
        ]
        snap = _snapshot(issues=issues, dependencies=[dep])
        html = deps_blockers_detail(snap, t=get_translator("en"))
        # Cross-team count should be 1
        assert ">1<" in html

    def test_aging_blocked_count(self):
        blocked = _issue(
            key="OLD-1",
            blocked=True,
            age_days_approx=15,
        )
        snap = _snapshot(issues=[blocked])
        html = deps_blockers_detail(snap, t=get_translator("en"))
        # Aging card should show 1
        parts = html.split("card-danger")
        # At least 2 card-danger sections (blocked items + aging)
        assert len(parts) >= 3  # split produces n+1 parts for n occurrences

    def test_teams_waiting_chips(self):
        dep = Dependency(
            source_key="A-1",
            target_key="B-1",
            link_type=LinkType.BLOCKS,
        )
        issues = [
            _issue(key="A-1"),
            _issue(key="B-1", components=["Backend"]),
        ]
        snap = _snapshot(issues=issues, dependencies=[dep])
        html = deps_blockers_detail(snap, t=get_translator("en"))
        assert "Backend" in html
        assert "chip" in html

    def test_blocked_items_table_has_container(self):
        blocked = _issue(key="BLK-2", blocked=True)
        snap = _snapshot(issues=[blocked])
        html = deps_blockers_detail(snap, t=get_translator("en"))
        assert 'data-table-id="deps-blockers"' in html
        assert "fb-table-container" in html

    def test_age_highlighting_danger(self):
        blocked = _issue(key="OLD-2", blocked=True, age_days_approx=20)
        snap = _snapshot(issues=[blocked])
        html = deps_blockers_detail(snap, t=get_translator("en"))
        assert "color:var(--color-danger)" in html

    def test_age_highlighting_warning(self):
        blocked = _issue(key="MED-1", blocked=True, age_days_approx=10)
        snap = _snapshot(issues=[blocked])
        html = deps_blockers_detail(snap, t=get_translator("en"))
        assert "color:var(--color-warning)" in html

    def test_no_blocked_shows_empty_state(self):
        """When no issues are blocked, show empty state message."""
        snap = _snapshot(issues=[_issue(blocked=False)])
        html = deps_blockers_detail(snap, t=get_translator("en"))
        assert "empty-state" in html

    def test_polish_translation(self):
        snap = _snapshot()
        html = deps_blockers_detail(snap, t=get_translator("pl"))
        # Polish keys should be resolved
        assert "Zablokowane" in html or "blocked" not in html.lower()


# ---------------------------------------------------------------------------
# i18n Key Tests
# ---------------------------------------------------------------------------


class TestI18nNewKeys:
    """Verify all new i18n keys exist in both locales."""

    REQUIRED_KEYS: typing.ClassVar[list[str]] = [
        "ui.table_showing",
        "ui.table_of",
        "ui.table_all",
        "section.deps_blockers",
        "deps.blocked_items",
        "deps.blocking_deps",
        "deps.cross_team",
        "deps.aging_blocked",
        "deps.teams_waiting",
        "deps.blocked_items_detail",
        "deps.days_blocked",
        "deps.blocked_by",
    ]

    @pytest.fixture(scope="class")
    def en_data(self) -> dict:
        p = Path(__file__).resolve().parent.parent / "src" / "flowboard" / "i18n" / "en.json"
        return json.loads(p.read_text())

    @pytest.fixture(scope="class")
    def pl_data(self) -> dict:
        p = Path(__file__).resolve().parent.parent / "src" / "flowboard" / "i18n" / "pl.json"
        return json.loads(p.read_text())

    @pytest.mark.parametrize("key", REQUIRED_KEYS)
    def test_en_has_key(self, key: str, en_data: dict):
        assert key in en_data, f"Missing EN key: {key}"

    @pytest.mark.parametrize("key", REQUIRED_KEYS)
    def test_pl_has_key(self, key: str, pl_data: dict):
        assert key in pl_data, f"Missing PL key: {key}"

    def test_en_pl_parity_for_new_keys(self, en_data: dict, pl_data: dict):
        for key in self.REQUIRED_KEYS:
            assert key in en_data and key in pl_data, f"Missing parity for {key}"

    def test_pl_values_not_english(self, en_data: dict, pl_data: dict):
        """Polish values should differ from English (translation exists)."""
        different = sum(1 for k in self.REQUIRED_KEYS if en_data.get(k) != pl_data.get(k))
        assert different >= len(self.REQUIRED_KEYS) * 0.8, "Too many untranslated PL keys"


# ---------------------------------------------------------------------------
# Renderer Context Tests
# ---------------------------------------------------------------------------


def _render_html(snap: BoardSnapshot | None = None, locale: str = "en") -> str:
    """Render dashboard HTML using proper config."""
    from flowboard.infrastructure.config.loader import load_config_from_dict
    from flowboard.presentation.html.renderer import render_dashboard

    if snap is None:
        snap = _snapshot(issues=[_issue()])
    cfg = load_config_from_dict(
        {
            "jira": {"base_url": "https://test.atlassian.net"},
            "output": {"title": "Test Board"},
            "locale": locale,
        }
    )
    return render_dashboard(snap, cfg)


class TestRendererContext:
    """Verify the renderer includes new context variables."""

    def test_version_in_context(self):
        from flowboard import __version__

        html = _render_html()
        assert __version__ in html

    def test_deps_blockers_html_in_output(self):
        html = _render_html()
        assert "insightsDepsBlockers" in html

    def test_footer_has_brand(self):
        html = _render_html()
        assert "footer-brand" in html or "FlowBoard" in html


# ---------------------------------------------------------------------------
# Chart Theme Fix Tests
# ---------------------------------------------------------------------------


class TestChartThemeFix:
    """Verify chart theme-switch fix elements in rendered HTML."""

    def test_chart_instances_destroy_present(self):
        html = _render_html()
        assert "Chart.instances" in html

    def test_request_animation_frame_present(self):
        html = _render_html()
        assert "requestAnimationFrame" in html

    def test_no_max_height_on_chart_card(self):
        """Chart cards should not have max-height that causes clipping."""
        import re

        html = _render_html()
        chart_card_css = re.findall(r"\.chart-card\s*\{[^}]+\}", html)
        for block in chart_card_css:
            assert "max-height" not in block, f"chart-card still has max-height: {block}"


# ---------------------------------------------------------------------------
# CSS Animation Tests
# ---------------------------------------------------------------------------


class TestCSSAnimations:
    """Verify animation CSS is present and reduced-motion is respected."""

    def test_fade_slide_keyframes_present(self):
        html = _render_html()
        assert "fadeSlideIn" in html

    def test_reduced_motion_media_query(self):
        html = _render_html()
        assert "prefers-reduced-motion" in html


# ---------------------------------------------------------------------------
# Table Engine JS Tests
# ---------------------------------------------------------------------------


class TestTableEngineJS:
    """Verify table engine JavaScript is included."""

    def test_init_table_engine_present(self):
        html = _render_html()
        assert "initTableEngine" in html

    def test_table_sort_js_elements(self):
        html = _render_html()
        assert "sort-asc" in html
        assert "sort-desc" in html


# ---------------------------------------------------------------------------
# Footer Tests
# ---------------------------------------------------------------------------


class TestFooterRedesign:
    """Verify footer matches ReleaseBoard structure."""

    def test_footer_structure(self):
        html = _render_html()
        assert "app-footer" in html

    def test_footer_tools_section(self):
        html = _render_html()
        assert "app-footer-tools" in html

    def test_footer_version_displayed(self):
        from flowboard import __version__

        html = _render_html()
        assert f"v{__version__}" in html or __version__ in html
