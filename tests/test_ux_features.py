"""Tests for UX features - table sorting attributes, table container structure,
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
    """Tests for table container structure."""

    """GIVEN table container structure and the scenario: workload table container"""
    def test_workload_table_container(self):
        """WHEN the code under test is exercised for: workload table container"""
        wr = WorkloadRecord(person=_person(), team="alpha", issue_count=3, story_points=10)
        html = workload_table([wr], t=get_translator("en"))

        """THEN the expected behaviour holds: workload table container"""
        assert 'class="fb-table-container"' in html
        assert 'data-table-id="workload"' in html
        assert 'data-total-rows="1"' in html

    """GIVEN table container structure and the scenario: risk table container"""
    def test_risk_table_container(self):
        """WHEN the code under test is exercised for: risk table container"""
        sig = RiskSignal(
            severity=RiskSeverity.HIGH,
            category=RiskCategory.OVERLOAD,
            title="Test",
            description="Test desc",
        )
        html = risk_table([sig], t=get_translator("en"))

        """THEN the expected behaviour holds: risk table container"""
        assert 'class="fb-table-container"' in html
        assert 'data-table-id="risks"' in html
        assert 'data-total-rows="1"' in html

    """GIVEN table container structure and the scenario: issues table container"""
    def test_issues_table_container(self):
        """WHEN the code under test is exercised for: issues table container"""
        issue = _issue()
        html = issues_table([issue], t=get_translator("en"))

        """THEN the expected behaviour holds: issues table container"""
        assert 'class="fb-table-container"' in html
        assert 'data-table-id="issues"' in html
        assert 'data-total-rows="1"' in html

    """GIVEN table container structure and the scenario: dependency table container"""
    def test_dependency_table_container(self):
        """WHEN the code under test is exercised for: dependency table container"""
        dep = Dependency(
            source_key="A-1",
            target_key="A-2",
            link_type=LinkType.BLOCKS,
        )
        snap = _snapshot(dependencies=[dep])
        html = dependency_table(snap, t=get_translator("en"))

        """THEN the expected behaviour holds: dependency table container"""
        assert 'class="fb-table-container"' in html
        assert 'data-table-id="deps"' in html
        assert 'data-total-rows="1"' in html

    """GIVEN table container structure and the scenario: total rows matches record count"""
    def test_total_rows_matches_record_count(self):
        """WHEN the code under test is exercised for: total rows matches record count"""
        records = [
            WorkloadRecord(person=_person(f"P{i}"), team="t", issue_count=i, story_points=i)
            for i in range(1, 6)
        ]
        html = workload_table(records, t=get_translator("en"))

        """THEN the expected behaviour holds: total rows matches record count"""
        assert 'data-total-rows="5"' in html


# ---------------------------------------------------------------------------
# Table Sorting Attribute Tests
# ---------------------------------------------------------------------------


class TestTableSortAttributes:
    """Tests for table sort attributes."""

    """GIVEN table sort attributes and the scenario: workload header sort types"""
    def test_workload_header_sort_types(self):
        """WHEN the code under test is exercised for: workload header sort types"""
        wr = WorkloadRecord(person=_person(), team="alpha", issue_count=3, story_points=10)
        html = workload_table([wr], t=get_translator("en"))

        """THEN the expected behaviour holds: workload header sort types"""
        assert 'data-sort-type="text"' in html
        assert 'data-sort-type="num"' in html

    """GIVEN table sort attributes and the scenario: workload cell sort values"""
    def test_workload_cell_sort_values(self):
        """WHEN the code under test is exercised for: workload cell sort values"""
        wr = WorkloadRecord(person=_person("Bob"), team="alpha", issue_count=3, story_points=10)
        html = workload_table([wr], t=get_translator("en"))

        """THEN the expected behaviour holds: workload cell sort values"""
        assert 'data-sort-value="Bob"' in html
        assert 'data-sort-value="alpha"' in html
        assert 'data-sort-value="3"' in html
        assert 'data-sort-value="10"' in html

    """GIVEN table sort attributes and the scenario: risk header sort types"""
    def test_risk_header_sort_types(self):
        """WHEN the code under test is exercised for: risk header sort types"""
        sig = RiskSignal(
            severity=RiskSeverity.CRITICAL,
            category=RiskCategory.OVERLOAD,
            title="Test",
            description="Desc",
        )
        html = risk_table([sig], t=get_translator("en"))

        """THEN the expected behaviour holds: risk header sort types"""
        assert 'data-sort-type="num"' in html
        assert 'data-sort-type="text"' in html

    """GIVEN table sort attributes and the scenario: risk severity numeric sort value"""
    def test_risk_severity_numeric_sort_value(self):
        """WHEN the code under test is exercised for: risk severity numeric sort value"""
        sig = RiskSignal(
            severity=RiskSeverity.CRITICAL,
            category=RiskCategory.OVERLOAD,
            title="Critical Risk",
            description="Desc",
        )
        html = risk_table([sig], t=get_translator("en"))
        # Critical = 0 (highest priority, sorted first)

        """THEN the expected behaviour holds: risk severity numeric sort value"""
        assert 'data-sort-value="0"' in html

    """GIVEN table sort attributes and the scenario: issues priority sort value"""
    def test_issues_priority_sort_value(self):
        """WHEN the code under test is exercised for: issues priority sort value"""
        issue = _issue(priority=Priority.HIGH)
        html = issues_table([issue], t=get_translator("en"))
        # HIGH priority should have a numeric sort value

        """THEN the expected behaviour holds: issues priority sort value"""
        assert 'data-sort-value="' in html

    """GIVEN table sort attributes and the scenario: dependency table has sort attributes"""
    def test_dependency_table_has_sort_attributes(self):
        """WHEN the code under test is exercised for: dependency table has sort attributes"""
        dep = Dependency(
            source_key="A-1",
            target_key="A-2",
            link_type=LinkType.BLOCKS,
        )
        snap = _snapshot(dependencies=[dep])
        html = dependency_table(snap, t=get_translator("en"))

        """THEN the expected behaviour holds: dependency table has sort attributes"""
        assert 'data-sort-type="text"' in html
        assert 'data-sort-value="A-1"' in html
        assert 'data-sort-value="A-2"' in html


# ---------------------------------------------------------------------------
# Dependencies & Blockers Detail View Tests
# ---------------------------------------------------------------------------


class TestDepsBlockersDetail:
    """Tests for deps blockers detail."""

    """GIVEN deps blockers detail and the scenario: empty snapshot shows empty state"""
    def test_empty_snapshot_shows_empty_state(self):
        """WHEN the code under test is exercised for: empty snapshot shows empty state"""
        snap = _snapshot()
        html = deps_blockers_detail(snap, t=get_translator("en"))

        """THEN the expected behaviour holds: empty snapshot shows empty state"""
        assert "card-value" in html
        assert ">0<" in html  # Zero blocked items

    """GIVEN deps blockers detail and the scenario: summary cards present"""
    def test_summary_cards_present(self):
        """WHEN the code under test is exercised for: summary cards present"""
        snap = _snapshot()
        html = deps_blockers_detail(snap, t=get_translator("en"))

        """THEN the expected behaviour holds: summary cards present"""
        assert "summary-card" in html
        assert "card-danger" in html
        assert "card-warning" in html
        assert "card-default" in html

    """GIVEN deps blockers detail and the scenario: blocked issues shown"""
    def test_blocked_issues_shown(self):
        """WHEN the code under test is exercised for: blocked issues shown"""
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

        """THEN the expected behaviour holds: blocked issues shown"""
        assert "BLK-1" in html
        assert "Charlie" in html

    """GIVEN deps blockers detail and the scenario: cross team deps counted"""
    def test_cross_team_deps_counted(self):
        """WHEN the code under test is exercised for: cross team deps counted"""
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

        """THEN the expected behaviour holds: cross team deps counted"""
        assert ">1<" in html

    """GIVEN deps blockers detail and the scenario: aging blocked count"""
    def test_aging_blocked_count(self):
        """WHEN the code under test is exercised for: aging blocked count"""
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

        """THEN the expected behaviour holds: aging blocked count"""
        assert len(parts) >= 3  # split produces n+1 parts for n occurrences

    """GIVEN deps blockers detail and the scenario: teams waiting chips"""
    def test_teams_waiting_chips(self):
        """WHEN the code under test is exercised for: teams waiting chips"""
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

        """THEN the expected behaviour holds: teams waiting chips"""
        assert "Backend" in html
        assert "chip" in html

    """GIVEN deps blockers detail and the scenario: blocked items table has container"""
    def test_blocked_items_table_has_container(self):
        """WHEN the code under test is exercised for: blocked items table has container"""
        blocked = _issue(key="BLK-2", blocked=True)
        snap = _snapshot(issues=[blocked])
        html = deps_blockers_detail(snap, t=get_translator("en"))

        """THEN the expected behaviour holds: blocked items table has container"""
        assert 'data-table-id="deps-blockers"' in html
        assert "fb-table-container" in html

    """GIVEN deps blockers detail and the scenario: age highlighting danger"""
    def test_age_highlighting_danger(self):
        """WHEN the code under test is exercised for: age highlighting danger"""
        blocked = _issue(key="OLD-2", blocked=True, age_days_approx=20)
        snap = _snapshot(issues=[blocked])
        html = deps_blockers_detail(snap, t=get_translator("en"))

        """THEN the expected behaviour holds: age highlighting danger"""
        assert "color:var(--color-danger)" in html

    """GIVEN deps blockers detail and the scenario: age highlighting warning"""
    def test_age_highlighting_warning(self):
        """WHEN the code under test is exercised for: age highlighting warning"""
        blocked = _issue(key="MED-1", blocked=True, age_days_approx=10)
        snap = _snapshot(issues=[blocked])
        html = deps_blockers_detail(snap, t=get_translator("en"))

        """THEN the expected behaviour holds: age highlighting warning"""
        assert "color:var(--color-warning)" in html

    """GIVEN deps blockers detail and the scenario: no blocked shows empty state"""
    def test_no_blocked_shows_empty_state(self):
        """WHEN the code under test is exercised for: no blocked shows empty state"""
        snap = _snapshot(issues=[_issue(blocked=False)])
        html = deps_blockers_detail(snap, t=get_translator("en"))

        """THEN the expected behaviour holds: no blocked shows empty state"""
        assert "empty-state" in html

    """GIVEN deps blockers detail and the scenario: polish translation"""
    def test_polish_translation(self):
        """WHEN the code under test is exercised for: polish translation"""
        snap = _snapshot()
        html = deps_blockers_detail(snap, t=get_translator("pl"))
        # Polish keys should be resolved

        """THEN the expected behaviour holds: polish translation"""
        assert "Zablokowane" in html or "blocked" not in html.lower()


# ---------------------------------------------------------------------------
# i18n Key Tests
# ---------------------------------------------------------------------------


class TestI18nNewKeys:
    """Tests for i18n new keys."""

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

    """GIVEN i18n new keys and the scenario: en has key"""

    @pytest.mark.parametrize("key", REQUIRED_KEYS)
    def test_en_has_key(self, key: str, en_data: dict):
        """THEN the expected behaviour holds: en has key"""
        assert key in en_data, f"Missing EN key: {key}"

    """GIVEN i18n new keys and the scenario: pl has key"""

    @pytest.mark.parametrize("key", REQUIRED_KEYS)
    def test_pl_has_key(self, key: str, pl_data: dict):
        """THEN the expected behaviour holds: pl has key"""
        assert key in pl_data, f"Missing PL key: {key}"

    """GIVEN i18n new keys and the scenario: en pl parity for new keys"""
    def test_en_pl_parity_for_new_keys(self, en_data: dict, pl_data: dict):
        """THEN the expected behaviour holds: en pl parity for new keys"""
        for key in self.REQUIRED_KEYS:
            assert key in en_data and key in pl_data, f"Missing parity for {key}"

    """GIVEN i18n new keys and the scenario: pl values not english"""
    def test_pl_values_not_english(self, en_data: dict, pl_data: dict):
        """WHEN the code under test is exercised for: pl values not english"""
        different = sum(1 for k in self.REQUIRED_KEYS if en_data.get(k) != pl_data.get(k))

        """THEN the expected behaviour holds: pl values not english"""
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
    """Tests for renderer context."""

    """GIVEN renderer context and the scenario: version in context"""
    def test_version_in_context(self):
        """WHEN the code under test is exercised for: version in context"""
        from flowboard import __version__

        html = _render_html()

        """THEN the expected behaviour holds: version in context"""
        assert __version__ in html

    """GIVEN renderer context and the scenario: deps blockers html in output"""
    def test_deps_blockers_html_in_output(self):
        """WHEN the code under test is exercised for: deps blockers html in output"""
        html = _render_html()

        """THEN the expected behaviour holds: deps blockers html in output"""
        assert "insightsDepsBlockers" in html

    """GIVEN renderer context and the scenario: footer has brand"""
    def test_footer_has_brand(self):
        """WHEN the code under test is exercised for: footer has brand"""
        html = _render_html()

        """THEN the expected behaviour holds: footer has brand"""
        assert "footer-brand" in html or "FlowBoard" in html


# ---------------------------------------------------------------------------
# Chart Theme Fix Tests
# ---------------------------------------------------------------------------


class TestChartThemeFix:
    """Tests for chart theme fix."""

    """GIVEN chart theme fix and the scenario: chart instances destroy present"""
    def test_chart_instances_destroy_present(self):
        """WHEN the code under test is exercised for: chart instances destroy present"""
        html = _render_html()

        """THEN the expected behaviour holds: chart instances destroy present"""
        assert "Chart.instances" in html

    """GIVEN chart theme fix and the scenario: request animation frame present"""
    def test_request_animation_frame_present(self):
        """WHEN the code under test is exercised for: request animation frame present"""
        html = _render_html()

        """THEN the expected behaviour holds: request animation frame present"""
        assert "requestAnimationFrame" in html

    """GIVEN chart theme fix and the scenario: no max height on chart card"""
    def test_no_max_height_on_chart_card(self):
        """WHEN the code under test is exercised for: no max height on chart card"""
        import re

        html = _render_html()
        chart_card_css = re.findall(r"\.chart-card\s*\{[^}]+\}", html)

        """THEN the expected behaviour holds: no max height on chart card"""
        for block in chart_card_css:
            assert "max-height" not in block, f"chart-card still has max-height: {block}"


# ---------------------------------------------------------------------------
# CSS Animation Tests
# ---------------------------------------------------------------------------


class TestCSSAnimations:
    """Tests for c s s animations."""

    """GIVEN c s s animations and the scenario: fade slide keyframes present"""
    def test_fade_slide_keyframes_present(self):
        """WHEN the code under test is exercised for: fade slide keyframes present"""
        html = _render_html()

        """THEN the expected behaviour holds: fade slide keyframes present"""
        assert "fadeSlideIn" in html

    """GIVEN c s s animations and the scenario: reduced motion media query"""
    def test_reduced_motion_media_query(self):
        """WHEN the code under test is exercised for: reduced motion media query"""
        html = _render_html()

        """THEN the expected behaviour holds: reduced motion media query"""
        assert "prefers-reduced-motion" in html


# ---------------------------------------------------------------------------
# Table Engine JS Tests
# ---------------------------------------------------------------------------


class TestTableEngineJS:
    """Tests for table engine j s."""

    """GIVEN table engine j s and the scenario: init table engine present"""
    def test_init_table_engine_present(self):
        """WHEN the code under test is exercised for: init table engine present"""
        html = _render_html()

        """THEN the expected behaviour holds: init table engine present"""
        assert "initTableEngine" in html

    """GIVEN table engine j s and the scenario: table sort js elements"""
    def test_table_sort_js_elements(self):
        """WHEN the code under test is exercised for: table sort js elements"""
        html = _render_html()

        """THEN the expected behaviour holds: table sort js elements"""
        assert "sort-asc" in html
        assert "sort-desc" in html


# ---------------------------------------------------------------------------
# Footer Tests
# ---------------------------------------------------------------------------


class TestFooterRedesign:
    """Tests for footer redesign."""

    """GIVEN footer redesign and the scenario: footer structure"""
    def test_footer_structure(self):
        """WHEN the code under test is exercised for: footer structure"""
        html = _render_html()

        """THEN the expected behaviour holds: footer structure"""
        assert "app-footer" in html

    """GIVEN footer redesign and the scenario: footer tools section"""
    def test_footer_tools_section(self):
        """WHEN the code under test is exercised for: footer tools section"""
        html = _render_html()

        """THEN the expected behaviour holds: footer tools section"""
        assert "app-footer-tools" in html

    """GIVEN footer redesign and the scenario: footer version displayed"""
    def test_footer_version_displayed(self):
        """WHEN the code under test is exercised for: footer version displayed"""
        from flowboard import __version__

        html = _render_html()

        """THEN the expected behaviour holds: footer version displayed"""
        assert f"v{__version__}" in html or __version__ in html
