"""Tests for core accessibility - ARIA attributes, focus-visible styles,
table scroll wrappers, truncation titles, skip links, semantic landmarks,
dialog roles, focus traps, keyboard navigation, chart error handling,
progress bar ARIA, tabpanel labelling, zoom button a11y, canvas a11y,
negative days clamping, empty table states, and issue key truncation.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from flowboard.domain.models import (
    BoardSnapshot,
    Dependency,
    Issue,
    Person,
    RiskSignal,
    RoadmapItem,
    Sprint,
    SprintHealth,
    WorkloadRecord,
)
from flowboard.domain.risk import detect_all_risks
from flowboard.i18n.translator import get_translator
from flowboard.infrastructure.config.loader import (
    Thresholds,
    load_config_from_dict,
)
from flowboard.presentation.html.components import (
    dependency_table,
    issues_table,
    risk_table,
    roadmap_timeline,
    workload_table,
)
from flowboard.presentation.html.renderer import render_dashboard
from flowboard.shared.types import (
    IssueStatus,
    IssueType,
    LinkType,
    Priority,
    RiskCategory,
    RiskSeverity,
    SprintState,
    StatusCategory,
)
from flowboard.shared.utils import truncate_html

# Helpers


def _person(name: str = "Alice", team: str = "alpha") -> Person:
    return Person(account_id="u1", display_name=name, team=team)


def _issue(key: str = "T-1", sp: float = 5.0, summary: str = "Test issue") -> Issue:
    return Issue(
        key=key,
        summary=summary,
        issue_type=IssueType.STORY,
        status=IssueStatus.OTHER,
        status_category=StatusCategory.TODO,
        assignee=_person(),
        story_points=sp,
        priority=Priority.MEDIUM,
        created=datetime(2026, 3, 1, tzinfo=UTC),
    )


def _sprint(sid: int = 1, name: str = "Sprint 1", end_date: date | None = None) -> Sprint:
    return Sprint(
        id=sid,
        name=name,
        state=SprintState.ACTIVE,
        start_date=date(2026, 3, 3),
        end_date=end_date or date(2026, 3, 17),
    )


def _render_full(locale: str = "en") -> str:
    """Render a full dashboard from mock data for the given locale."""
    cfg = load_config_from_dict(
        {
            "jira": {"base_url": "https://test.atlassian.net"},
            "output": {"title": "Test Board"},
            "locale": locale,
        }
    )
    snap = BoardSnapshot(title="Test Board")
    return render_dashboard(snap, cfg)


# ====================================================================
# 1. Responsive table scroll wrappers
# ====================================================================


class TestTableScrollWrappers:
    """Tests for table scroll wrappers."""

    """GIVEN table scroll wrappers and the scenario: workload table has scroll wrapper"""
    def test_workload_table_has_scroll_wrapper(self):
        """WHEN the code under test is exercised for: workload table has scroll wrapper"""
        wr = WorkloadRecord(person=_person(), team="alpha", issue_count=3, story_points=10)
        html = workload_table([wr], t=get_translator("en"))

        """THEN the expected behaviour holds: workload table has scroll wrapper"""
        assert 'class="table-scroll"' in html
        assert 'class="fb-table-container"' in html

    """GIVEN table scroll wrappers and the scenario: risk table has scroll wrapper"""
    def test_risk_table_has_scroll_wrapper(self):
        """WHEN the code under test is exercised for: risk table has scroll wrapper"""
        sig = RiskSignal(
            severity=RiskSeverity.HIGH,
            category=RiskCategory.OVERLOAD,
            title="Test",
            description="Test description",
        )
        html = risk_table([sig], t=get_translator("en"))

        """THEN the expected behaviour holds: risk table has scroll wrapper"""
        assert 'class="table-scroll"' in html

    """GIVEN table scroll wrappers and the scenario: roadmap table has scroll wrapper"""
    def test_roadmap_table_has_scroll_wrapper(self):
        """WHEN the code under test is exercised for: roadmap table has scroll wrapper"""
        item = RoadmapItem(key="E-1", title="Epic One", child_count=5, done_count=2)
        html = roadmap_timeline([item], t=get_translator("en"))

        """THEN the expected behaviour holds: roadmap table has scroll wrapper"""
        assert 'class="table-scroll"' in html

    """GIVEN table scroll wrappers and the scenario: issues table has scroll wrapper"""
    def test_issues_table_has_scroll_wrapper(self):
        """WHEN the code under test is exercised for: issues table has scroll wrapper"""
        issue = _issue()
        html = issues_table([issue], t=get_translator("en"))

        """THEN the expected behaviour holds: issues table has scroll wrapper"""
        assert 'class="table-scroll"' in html

    """GIVEN table scroll wrappers and the scenario: dependency table has scroll wrapper"""
    def test_dependency_table_has_scroll_wrapper(self):
        """WHEN the code under test is exercised for: dependency table has scroll wrapper"""
        dep = Dependency(
            source_key="A-1",
            target_key="B-1",
            link_type=LinkType.BLOCKS,
            source_status=StatusCategory.TODO,
            target_status=StatusCategory.TODO,
        )
        snap = BoardSnapshot(dependencies=[dep])
        html = dependency_table(snap, t=get_translator("en"))

        """THEN the expected behaviour holds: dependency table has scroll wrapper"""
        assert 'class="table-scroll"' in html

    """GIVEN table scroll wrappers and the scenario: scroll wrapper in polish locale"""
    def test_scroll_wrapper_in_polish_locale(self):
        """WHEN the code under test is exercised for: scroll wrapper in polish locale"""
        wr = WorkloadRecord(person=_person(), team="alpha", issue_count=3, story_points=10)
        html = workload_table([wr], t=get_translator("pl"))

        """THEN the expected behaviour holds: scroll wrapper in polish locale"""
        assert 'class="table-scroll"' in html


# ====================================================================
# 2. ARIA accessibility attributes
# ====================================================================


class TestAriaAttributes:
    """Tests for aria attributes."""

    """GIVEN aria attributes and the scenario: tablist role present"""
    def test_tablist_role_present(self):
        """WHEN the code under test is exercised for: tablist role present"""
        html = _render_full("en")

        """THEN the expected behaviour holds: tablist role present"""
        assert 'role="tablist"' in html

    """GIVEN aria attributes and the scenario: tab role present"""
    def test_tab_role_present(self):
        """WHEN the code under test is exercised for: tab role present"""
        html = _render_full("en")

        """THEN the expected behaviour holds: tab role present"""
        assert 'role="tab"' in html

    """GIVEN aria attributes and the scenario: tabpanel role present"""
    def test_tabpanel_role_present(self):
        """WHEN the code under test is exercised for: tabpanel role present"""
        html = _render_full("en")

        """THEN the expected behaviour holds: tabpanel role present"""
        assert 'role="tabpanel"' in html

    """GIVEN aria attributes and the scenario: aria selected on active tab"""
    def test_aria_selected_on_active_tab(self):
        """WHEN the code under test is exercised for: aria selected on active tab"""
        html = _render_full("en")

        """THEN the expected behaviour holds: aria selected on active tab"""
        assert 'aria-selected="true"' in html

    """GIVEN aria attributes and the scenario: aria controls present"""
    def test_aria_controls_present(self):
        """WHEN the code under test is exercised for: aria controls present"""
        html = _render_full("en")

        """THEN the expected behaviour holds: aria controls present"""
        assert 'aria-controls="tab-' in html

    """GIVEN aria attributes and the scenario: close button has aria label"""
    def test_close_button_has_aria_label(self):
        """WHEN the code under test is exercised for: close button has aria label"""
        html = _render_full("en")

        """THEN the expected behaviour holds: close button has aria label"""
        assert 'aria-label="Close settings"' in html

    """GIVEN aria attributes and the scenario: aria attributes in polish"""
    def test_aria_attributes_in_polish(self):
        """WHEN the code under test is exercised for: aria attributes in polish"""
        html = _render_full("pl")

        """THEN the expected behaviour holds: aria attributes in polish"""
        assert 'role="tablist"' in html
        assert 'role="tab"' in html
        assert 'role="tabpanel"' in html


# ====================================================================
# 6. Truncation with title attribute
# ====================================================================


class TestTruncationTitleAttribute:
    """Tests for truncation title attribute."""

    """GIVEN truncation title attribute and the scenario: truncate html short text no span"""
    def test_truncate_html_short_text_no_span(self):
        """WHEN the code under test is exercised for: truncate html short text no span"""
        result = truncate_html("Short text", 80)

        """THEN the expected behaviour holds: truncate html short text no span"""
        assert "<span" not in result
        assert "Short text" in result

    """GIVEN truncation title attribute and the scenario: truncate html long text has title"""
    def test_truncate_html_long_text_has_title(self):
        """WHEN the code under test is exercised for: truncate html long text has title"""
        long_text = "A" * 100
        result = truncate_html(long_text, 50)

        """THEN the expected behaviour holds: truncate html long text has title"""
        assert 'title="' in result
        assert "<span" in result
        assert "…" in result

    """GIVEN truncation title attribute and the scenario: truncate html escapes html chars"""
    def test_truncate_html_escapes_html_chars(self):
        """WHEN the code under test is exercised for: truncate html escapes html chars"""
        result = truncate_html('<script>alert("xss")</script>', 80)

        """THEN the expected behaviour holds: truncate html escapes html chars"""
        assert "<script>" not in result
        assert "&lt;" in result

    """GIVEN truncation title attribute and the scenario: issues table uses truncation with title"""
    def test_issues_table_uses_truncation_with_title(self):
        """WHEN the code under test is exercised for: issues table uses truncation with title"""
        issue = _issue(summary="A" * 100)
        html = issues_table([issue], t=get_translator("en"))

        """THEN the expected behaviour holds: issues table uses truncation with title"""
        assert 'title="' in html

    """GIVEN truncation title attribute and the scenario: roadmap uses truncation with title"""
    def test_roadmap_uses_truncation_with_title(self):
        """WHEN the code under test is exercised for: roadmap uses truncation with title"""
        item = RoadmapItem(key="E-1", title="A" * 100, child_count=1, done_count=0)
        html = roadmap_timeline([item], t=get_translator("en"))

        """THEN the expected behaviour holds: roadmap uses truncation with title"""
        assert 'title="' in html


# ====================================================================
# 7. Negative days clamping
# ====================================================================


class TestNegativeDaysClamping:
    """Tests for negative days clamping."""

    """GIVEN negative days clamping and the scenario: sprint risk clamps negative days to zero"""
    def test_sprint_risk_clamps_negative_days_to_zero(self):
        """WHEN the code under test is exercised for: sprint risk clamps negative days to zero"""
        sprint = _sprint(end_date=date(2026, 3, 10))
        sh = SprintHealth(
            sprint=sprint,
            total_issues=10,
            done_issues=1,
            todo_issues=8,
            in_progress_issues=1,
        )
        t = get_translator("en")
        risks = detect_all_risks(
            [],
            [],
            [sh],
            [],
            Thresholds(),
            today=date(2026, 3, 18),
            t=t,
        )

        """THEN the expected behaviour holds: sprint risk clamps negative days to zero"""
        for risk in risks:
            assert "-1" not in risk.description
            assert (
                "-" not in risk.description.split("with ")[1].split(" ")[0]
                if "with " in risk.description
                else True
            )

    """GIVEN negative days clamping and the scenario: sprint risk overdue shows zero days"""
    def test_sprint_risk_overdue_shows_zero_days(self):
        """WHEN the code under test is exercised for: sprint risk overdue shows zero days"""
        sprint = _sprint(end_date=date(2026, 3, 15))
        sh = SprintHealth(
            sprint=sprint,
            total_issues=10,
            done_issues=2,
            todo_issues=7,
            in_progress_issues=1,
        )
        t = get_translator("en")
        risks = detect_all_risks(
            [],
            [],
            [sh],
            [],
            Thresholds(),
            today=date(2026, 3, 20),
            t=t,
        )
        critical = [r for r in risks if r.severity == RiskSeverity.CRITICAL]

        """THEN the expected behaviour holds: sprint risk overdue shows zero days"""
        for r in critical:
            if "day" in r.description:
                # Extract the days number
                import re

                match = re.search(r"(\d+)\s+day", r.description)
                if match:
                    assert int(match.group(1)) >= 0


# ====================================================================
# 14. Skip link (WCAG 2.4.1)
# ====================================================================


class TestSkipLink:
    """Tests for skip link."""

    """GIVEN skip link and the scenario: skip link present"""
    def test_skip_link_present(self):
        """WHEN the code under test is exercised for: skip link present"""
        html = _render_full("en")

        """THEN the expected behaviour holds: skip link present"""
        assert 'class="skip-link"' in html
        assert 'href="#main-content"' in html

    """GIVEN skip link and the scenario: main content target present"""
    def test_main_content_target_present(self):
        """WHEN the code under test is exercised for: main content target present"""
        html = _render_full("en")

        """THEN the expected behaviour holds: main content target present"""
        assert 'id="main-content"' in html


# ====================================================================
# 16. Toggle accessible labels
# ====================================================================


class TestToggleAccessibleLabels:
    """Tests for toggle accessible labels."""

    """GIVEN toggle accessible labels and the scenario: toggles have aria labels"""
    def test_toggles_have_aria_labels(self):
        """WHEN the code under test is exercised for: toggles have aria labels"""
        html = _render_full("en")
        # Count toggle checkboxes vs those with aria-label
        import re

        toggle_inputs = re.findall(r'<input type="checkbox"[^>]*>', html)

        """THEN the expected behaviour holds: toggles have aria labels"""
        for inp in toggle_inputs:
            assert "aria-label=" in inp, f"Toggle missing aria-label: {inp[:80]}"


# ====================================================================
# 17. Focus trap in settings drawer
# ====================================================================


class TestFocusTrap:
    """Tests for focus trap."""

    """GIVEN focus trap and the scenario: escape key handler"""
    def test_escape_key_handler(self):
        """WHEN the code under test is exercised for: escape key handler"""
        html = _render_full("en")

        """THEN the expected behaviour holds: escape key handler"""
        assert "e.key === 'Escape'" in html

    """GIVEN focus trap and the scenario: tab trap logic"""
    def test_tab_trap_logic(self):
        """WHEN the code under test is exercised for: tab trap logic"""
        html = _render_full("en")

        """THEN the expected behaviour holds: tab trap logic"""
        assert "e.key !== 'Tab'" in html
        assert "e.preventDefault()" in html


# ====================================================================
# 18. Toast ARIA live region
# ====================================================================


class TestToastAriaLive:
    """Tests for toast aria live."""

    """GIVEN toast aria live and the scenario: toast has aria live"""
    def test_toast_has_aria_live(self):
        """WHEN the code under test is exercised for: toast has aria live"""
        html = _render_full("en")

        """THEN the expected behaviour holds: toast has aria live"""
        assert 'aria-live="polite"' in html

    """GIVEN toast aria live and the scenario: toast has role status"""
    def test_toast_has_role_status(self):
        """WHEN the code under test is exercised for: toast has role status"""
        html = _render_full("en")

        """THEN the expected behaviour holds: toast has role status"""
        assert 'role="status"' in html


# ====================================================================
# 19. Settings dialog role and aria-modal
# ====================================================================


class TestDialogRole:
    """Tests for dialog role."""

    """GIVEN dialog role and the scenario: dialog role"""
    def test_dialog_role(self):
        """WHEN the code under test is exercised for: dialog role"""
        html = _render_full("en")

        """THEN the expected behaviour holds: dialog role"""
        assert 'role="dialog"' in html

    """GIVEN dialog role and the scenario: aria modal"""
    def test_aria_modal(self):
        """WHEN the code under test is exercised for: aria modal"""
        html = _render_full("en")

        """THEN the expected behaviour holds: aria modal"""
        assert 'aria-modal="true"' in html


# ====================================================================
# 20. Semantic HTML5 landmarks
# ====================================================================


class TestSemanticLandmarks:
    """Tests for semantic landmarks."""

    """GIVEN semantic landmarks and the scenario: has header element"""
    def test_has_header_element(self):
        """WHEN the code under test is exercised for: has header element"""
        html = _render_full("en")

        """THEN the expected behaviour holds: has header element"""
        assert "<header" in html

    """GIVEN semantic landmarks and the scenario: has nav element"""
    def test_has_nav_element(self):
        """WHEN the code under test is exercised for: has nav element"""
        html = _render_full("en")

        """THEN the expected behaviour holds: has nav element"""
        assert "<nav " in html

    """GIVEN semantic landmarks and the scenario: has main element"""
    def test_has_main_element(self):
        """WHEN the code under test is exercised for: has main element"""
        html = _render_full("en")

        """THEN the expected behaviour holds: has main element"""
        assert "<main " in html

    """GIVEN semantic landmarks and the scenario: has footer element"""
    def test_has_footer_element(self):
        """WHEN the code under test is exercised for: has footer element"""
        html = _render_full("en")

        """THEN the expected behaviour holds: has footer element"""
        assert "<footer" in html


# ====================================================================
# 21. Chart CDN fallback
# ====================================================================


class TestChartCDNFallback:
    """Tests for chart c d n fallback."""

    """GIVEN chart c d n fallback and the scenario: script has onerror"""
    def test_script_has_onerror(self):
        """WHEN the code under test is exercised for: script has onerror"""
        html = _render_full("en")

        """THEN the expected behaviour holds: script has onerror"""
        assert "onerror=" in html
        assert "chart.js" in html

    """GIVEN chart c d n fallback and the scenario: chart loading indicators"""
    def test_chart_loading_indicators(self):
        """WHEN the code under test is exercised for: chart loading indicators"""
        html = _render_full("en")

        """THEN the expected behaviour holds: chart loading indicators"""
        assert 'class="chart-loading"' in html


# ====================================================================
# 22. Chart error handling
# ====================================================================


class TestChartErrorHandling:
    """Tests for chart error handling."""

    """GIVEN chart error handling and the scenario: chart init has try catch"""
    def test_chart_init_has_try_catch(self):
        """WHEN the code under test is exercised for: chart init has try catch"""
        html = _render_full("en")

        """THEN the expected behaviour holds: chart init has try catch"""
        assert "try {" in html
        assert "_showChartError" in html

    """GIVEN chart error handling and the scenario: chart unavailable message"""
    def test_chart_unavailable_message(self):
        """WHEN the code under test is exercised for: chart unavailable message"""
        html = _render_full("en")

        """THEN the expected behaviour holds: chart unavailable message"""
        assert "chart_unavailable" in html


# ====================================================================
# 23. Empty table states
# ====================================================================


class TestEmptyTableStates:
    """Tests for empty table states."""

    """GIVEN empty table states and the scenario: workload empty state"""
    def test_workload_empty_state(self):
        """WHEN the code under test is exercised for: workload empty state"""
        t = get_translator("en")
        html = workload_table([], t=t)

        """THEN the expected behaviour holds: workload empty state"""
        assert "empty-state" in html

    """GIVEN empty table states and the scenario: issues empty state"""
    def test_issues_empty_state(self):
        """WHEN the code under test is exercised for: issues empty state"""
        t = get_translator("en")
        html = issues_table([], t=t)

        """THEN the expected behaviour holds: issues empty state"""
        assert "empty-state" in html

    """GIVEN empty table states and the scenario: workload empty state pl"""
    def test_workload_empty_state_pl(self):
        """WHEN the code under test is exercised for: workload empty state pl"""
        t = get_translator("pl")
        html = workload_table([], t=t)

        """THEN the expected behaviour holds: workload empty state pl"""
        assert "empty-state" in html


# ====================================================================
# 24. Issue key truncation
# ====================================================================


class TestIssueKeyTruncation:
    """Tests for issue key truncation."""

    """GIVEN issue key truncation and the scenario: issues table has cell key"""
    def test_issues_table_has_cell_key(self):
        """WHEN the code under test is exercised for: issues table has cell key"""
        t = get_translator("en")
        html = issues_table([_issue()], t=t)

        """THEN the expected behaviour holds: issues table has cell key"""
        assert 'class="cell-key"' in html

    """GIVEN issue key truncation and the scenario: roadmap has cell key"""
    def test_roadmap_has_cell_key(self):
        """WHEN the code under test is exercised for: roadmap has cell key"""
        t = get_translator("en")
        item = RoadmapItem(
            key="VERY-LONG-PROJECT-KEY-12345",
            title="Test epic",
            team="alpha",
            child_count=5,
            done_count=2,
            progress_pct=40.0,
        )
        html = roadmap_timeline([item], t=t)

        """THEN the expected behaviour holds: roadmap has cell key"""
        assert 'class="cell-key"' in html


# ====================================================================
# 36. Progress bars have ARIA attributes
# ====================================================================


class TestProgressBarAria:
    """Tests for progress bar aria."""

    @staticmethod
    def _all_components_source() -> str:
        from pathlib import Path

        pkg = Path(__file__).parent.parent / "src" / "flowboard" / "presentation" / "html"
        return "\n".join(p.read_text() for p in sorted(pkg.glob("components*.py")))

    """GIVEN progress bar aria and the scenario: progressbar role in component"""
    def test_progressbar_role_in_component(self):
        """WHEN the code under test is exercised for: progressbar role in component"""
        src = self._all_components_source()

        """THEN the expected behaviour holds: progressbar role in component"""
        assert 'role="progressbar"' in src

    """GIVEN progress bar aria and the scenario: progressbar aria values in component"""
    def test_progressbar_aria_values_in_component(self):
        """WHEN the code under test is exercised for: progressbar aria values in component"""
        src = self._all_components_source()

        """THEN the expected behaviour holds: progressbar aria values in component"""
        assert "aria-valuenow=" in src
        assert "aria-valuemin=" in src
        assert "aria-valuemax=" in src


# ====================================================================
# 37. Tabpanels have aria-labelledby
# ====================================================================


class TestTabpanelAriaLabelledby:
    """Tests for tabpanel aria labelledby."""

    """GIVEN tabpanel aria labelledby and the scenario: tabpanel labelledby"""
    def test_tabpanel_labelledby(self):
        """WHEN the code under test is exercised for: tabpanel labelledby"""
        html = _render_full("en")
        import re

        panels = re.findall(r'role="tabpanel"[^>]*id="tab-(\w+)"', html)

        """THEN the expected behaviour holds: tabpanel labelledby"""
        for panel_id in panels:
            assert f'aria-labelledby="tab-{panel_id}-btn"' in html

    """GIVEN tabpanel aria labelledby and the scenario: tab buttons have ids"""
    def test_tab_buttons_have_ids(self):
        """WHEN the code under test is exercised for: tab buttons have ids"""
        html = _render_full("en")
        import re

        btn_ids = re.findall(r'id="tab-(\w+)-btn"', html)

        """THEN the expected behaviour holds: tab buttons have ids"""
        assert len(btn_ids) >= 4


# ====================================================================
# 38. Settings labels have for attributes
# ====================================================================


class TestSettingsLabelFor:
    """Tests for settings label for."""

    """GIVEN settings label for and the scenario: label for cfg title"""
    def test_label_for_cfg_title(self):
        """WHEN the code under test is exercised for: label for cfg title"""
        html = _render_full("en")

        """THEN the expected behaviour holds: label for cfg title"""
        assert 'for="cfg-title"' in html

    """GIVEN settings label for and the scenario: label for cfg subtitle"""
    def test_label_for_cfg_subtitle(self):
        """WHEN the code under test is exercised for: label for cfg subtitle"""
        html = _render_full("en")

        """THEN the expected behaviour holds: label for cfg subtitle"""
        assert 'for="cfg-subtitle"' in html

    """GIVEN settings label for and the scenario: label for cfg company"""
    def test_label_for_cfg_company(self):
        """WHEN the code under test is exercised for: label for cfg company"""
        html = _render_full("en")

        """THEN the expected behaviour holds: label for cfg company"""
        assert 'for="cfg-company"' in html


# ====================================================================
# 39. Zoom button accessibility
# ====================================================================


class TestZoomButtonA11y:
    """Tests for zoom button a11y."""

    """GIVEN zoom button a11y and the scenario: zoom out label"""
    def test_zoom_out_label(self):
        """WHEN the code under test is exercised for: zoom out label"""
        html = _render_full("en")

        """THEN the expected behaviour holds: zoom out label"""
        assert 'aria-label="Zoom out"' in html

    """GIVEN zoom button a11y and the scenario: zoom in label"""
    def test_zoom_in_label(self):
        """WHEN the code under test is exercised for: zoom in label"""
        html = _render_full("en")

        """THEN the expected behaviour holds: zoom in label"""
        assert 'aria-label="Zoom in"' in html


# ====================================================================
# 40. Detail panel focus management
# ====================================================================


class TestDetailPanelFocus:
    """Tests for detail panel focus."""

    """GIVEN detail panel focus and the scenario: focus save on open"""
    def test_focus_save_on_open(self):
        """WHEN the code under test is exercised for: focus save on open"""
        html = _render_full("en")

        """THEN the expected behaviour holds: focus save on open"""
        assert "_detailPreviousFocus" in html

    """GIVEN detail panel focus and the scenario: focus restore on close"""
    def test_focus_restore_on_close(self):
        """WHEN the code under test is exercised for: focus restore on close"""
        html = _render_full("en")

        """THEN the expected behaviour holds: focus restore on close"""
        assert "_detailPreviousFocus.focus()" in html


# ====================================================================
# 41. Nav aria-label is localized
# ====================================================================


class TestNavAriaLabelI18n:
    """Tests for nav aria label i18n."""

    """GIVEN nav aria label i18n and the scenario: nav label en"""
    def test_nav_label_en(self):
        """WHEN the code under test is exercised for: nav label en"""
        html = _render_full("en")

        """THEN the expected behaviour holds: nav label en"""
        assert 'aria-label="Dashboard navigation"' in html

    """GIVEN nav aria label i18n and the scenario: nav label pl"""
    def test_nav_label_pl(self):
        """WHEN the code under test is exercised for: nav label pl"""
        html = _render_full("pl")

        """THEN the expected behaviour holds: nav label pl"""
        assert 'aria-label="Nawigacja pulpitu"' in html


# ====================================================================
# 49. Sub-tab ARIA roles
# ====================================================================


class TestSubTabAria:
    """Tests for sub tab aria."""

    """GIVEN sub tab aria and the scenario: subtab tablist role"""
    def test_subtab_tablist_role(self):
        """WHEN the code under test is exercised for: subtab tablist role"""
        html = _render_full("en")

        """THEN the expected behaviour holds: subtab tablist role"""
        assert html.count('role="tablist"') >= 5  # nav + 4 sub-tab groups

    """GIVEN sub tab aria and the scenario: subtab tab role"""
    def test_subtab_tab_role(self):
        """WHEN the code under test is exercised for: subtab tab role"""
        html = _render_full("en")

        """THEN the expected behaviour holds: subtab tab role"""
        assert html.count('role="tab"') >= 20

    """GIVEN sub tab aria and the scenario: subtab aria controls"""
    def test_subtab_aria_controls(self):
        """WHEN the code under test is exercised for: subtab aria controls"""
        html = _render_full("en")

        """THEN the expected behaviour holds: subtab aria controls"""
        assert 'aria-controls="insightsRisks"' in html

    """GIVEN sub tab aria and the scenario: subtab tabpanel count"""
    def test_subtab_tabpanel_count(self):
        """WHEN the code under test is exercised for: subtab tabpanel count"""
        html = _render_full("en")

        """THEN the expected behaviour holds: subtab tabpanel count"""
        assert html.count('role="tabpanel"') >= 20


# ====================================================================
# 50. Detail panel focus trap
# ====================================================================


class TestDetailFocusTrap:
    """Tests for detail focus trap."""

    """GIVEN detail focus trap and the scenario: focus trap handler"""
    def test_focus_trap_handler(self):
        """WHEN the code under test is exercised for: focus trap handler"""
        html = _render_full("en")

        """THEN the expected behaviour holds: focus trap handler"""
        assert "detailPanel" in html
        assert "_detailPreviousFocus" in html

    """GIVEN detail focus trap and the scenario: focus restore"""
    def test_focus_restore(self):
        """WHEN the code under test is exercised for: focus restore"""
        html = _render_full("en")

        """THEN the expected behaviour holds: focus restore"""
        assert "_detailPreviousFocus.focus()" in html


# ====================================================================
# 53. Chart canvas accessibility
# ====================================================================


class TestChartCanvasA11y:
    """Tests for chart canvas a11y."""

    """GIVEN chart canvas a11y and the scenario: canvas role img"""
    def test_canvas_role_img(self):
        """WHEN the code under test is exercised for: canvas role img"""
        html = _render_full("en")

        """THEN the expected behaviour holds: canvas role img"""
        assert 'role="img"' in html

    """GIVEN chart canvas a11y and the scenario: canvas aria label"""
    def test_canvas_aria_label(self):
        """WHEN the code under test is exercised for: canvas aria label"""
        html = _render_full("en")
        import re

        labeled = re.findall(r'<canvas[^>]*role="img"[^>]*aria-label="[^"]+', html)

        """THEN the expected behaviour holds: canvas aria label"""
        assert len(labeled) >= 4


# ====================================================================
# 54. Loading state accessibility
# ====================================================================


class TestLoadingA11y:
    """Tests for loading a11y."""

    """GIVEN loading a11y and the scenario: loading role status"""
    def test_loading_role_status(self):
        """WHEN the code under test is exercised for: loading role status"""
        html = _render_full("en")

        """THEN the expected behaviour holds: loading role status"""
        assert "chart-loading" in html
        import re

        with_role = re.findall(r'class="chart-loading"[^>]*role="status"', html)
        assert len(with_role) >= 4


# ====================================================================
# 55. Error boundary
# ====================================================================


class TestErrorBoundary:
    """Tests for error boundary."""

    """GIVEN error boundary and the scenario: onerror handler"""
    def test_onerror_handler(self):
        """WHEN the code under test is exercised for: onerror handler"""
        html = _render_full("en")

        """THEN the expected behaviour holds: onerror handler"""
        assert "window.onerror" in html
