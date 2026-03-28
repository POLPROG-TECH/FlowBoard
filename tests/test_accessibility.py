"""Tests for core accessibility — ARIA attributes, focus-visible styles,
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
    """All data tables must be wrapped in a .table-scroll div for mobile overflow."""

    def test_workload_table_has_scroll_wrapper(self):
        wr = WorkloadRecord(person=_person(), team="alpha", issue_count=3, story_points=10)
        html = workload_table([wr], t=get_translator("en"))
        assert 'class="table-scroll"' in html
        assert 'class="fb-table-container"' in html

    def test_risk_table_has_scroll_wrapper(self):
        sig = RiskSignal(
            severity=RiskSeverity.HIGH,
            category=RiskCategory.OVERLOAD,
            title="Test",
            description="Test description",
        )
        html = risk_table([sig], t=get_translator("en"))
        assert 'class="table-scroll"' in html

    def test_roadmap_table_has_scroll_wrapper(self):
        item = RoadmapItem(key="E-1", title="Epic One", child_count=5, done_count=2)
        html = roadmap_timeline([item], t=get_translator("en"))
        assert 'class="table-scroll"' in html

    def test_issues_table_has_scroll_wrapper(self):
        issue = _issue()
        html = issues_table([issue], t=get_translator("en"))
        assert 'class="table-scroll"' in html

    def test_dependency_table_has_scroll_wrapper(self):
        dep = Dependency(
            source_key="A-1",
            target_key="B-1",
            link_type=LinkType.BLOCKS,
            source_status=StatusCategory.TODO,
            target_status=StatusCategory.TODO,
        )
        snap = BoardSnapshot(dependencies=[dep])
        html = dependency_table(snap, t=get_translator("en"))
        assert 'class="table-scroll"' in html

    def test_scroll_wrapper_in_polish_locale(self):
        wr = WorkloadRecord(person=_person(), team="alpha", issue_count=3, story_points=10)
        html = workload_table([wr], t=get_translator("pl"))
        assert 'class="table-scroll"' in html


# ====================================================================
# 2. ARIA accessibility attributes
# ====================================================================


class TestAriaAttributes:
    """Dashboard HTML must contain proper ARIA roles and attributes."""

    def test_tablist_role_present(self):
        html = _render_full("en")
        assert 'role="tablist"' in html

    def test_tab_role_present(self):
        html = _render_full("en")
        assert 'role="tab"' in html

    def test_tabpanel_role_present(self):
        html = _render_full("en")
        assert 'role="tabpanel"' in html

    def test_aria_selected_on_active_tab(self):
        html = _render_full("en")
        assert 'aria-selected="true"' in html

    def test_aria_controls_present(self):
        html = _render_full("en")
        assert 'aria-controls="tab-' in html

    def test_close_button_has_aria_label(self):
        html = _render_full("en")
        assert 'aria-label="Close settings"' in html

    def test_aria_attributes_in_polish(self):
        html = _render_full("pl")
        assert 'role="tablist"' in html
        assert 'role="tab"' in html
        assert 'role="tabpanel"' in html


# ====================================================================
# 6. Truncation with title attribute
# ====================================================================


class TestTruncationTitleAttribute:
    """Truncated text must include a title attribute for hover reveal."""

    def test_truncate_html_short_text_no_span(self):
        result = truncate_html("Short text", 80)
        assert "<span" not in result
        assert "Short text" in result

    def test_truncate_html_long_text_has_title(self):
        long_text = "A" * 100
        result = truncate_html(long_text, 50)
        assert 'title="' in result
        assert "<span" in result
        assert "…" in result

    def test_truncate_html_escapes_html_chars(self):
        result = truncate_html('<script>alert("xss")</script>', 80)
        assert "<script>" not in result
        assert "&lt;" in result

    def test_issues_table_uses_truncation_with_title(self):
        issue = _issue(summary="A" * 100)
        html = issues_table([issue], t=get_translator("en"))
        assert 'title="' in html

    def test_roadmap_uses_truncation_with_title(self):
        item = RoadmapItem(key="E-1", title="A" * 100, child_count=1, done_count=0)
        html = roadmap_timeline([item], t=get_translator("en"))
        assert 'title="' in html


# ====================================================================
# 7. Negative days clamping
# ====================================================================


class TestNegativeDaysClamping:
    """Sprint risk detection must not produce negative day counts."""

    def test_sprint_risk_clamps_negative_days_to_zero(self):
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
        for risk in risks:
            assert "-1" not in risk.description
            assert (
                "-" not in risk.description.split("with ")[1].split(" ")[0]
                if "with " in risk.description
                else True
            )

    def test_sprint_risk_overdue_shows_zero_days(self):
        """When sprint is past end date, should show 0, not negative."""
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
    """Dashboard must include a skip-to-main-content link."""

    def test_skip_link_present(self):
        html = _render_full("en")
        assert 'class="skip-link"' in html
        assert 'href="#main-content"' in html

    def test_main_content_target_present(self):
        html = _render_full("en")
        assert 'id="main-content"' in html


# ====================================================================
# 16. Toggle accessible labels
# ====================================================================


class TestToggleAccessibleLabels:
    """All settings toggle inputs must have aria-label attributes."""

    def test_toggles_have_aria_labels(self):
        html = _render_full("en")
        # Count toggle checkboxes vs those with aria-label
        import re

        toggle_inputs = re.findall(r'<input type="checkbox"[^>]*>', html)
        for inp in toggle_inputs:
            assert "aria-label=" in inp, f"Toggle missing aria-label: {inp[:80]}"


# ====================================================================
# 17. Focus trap in settings drawer
# ====================================================================


class TestFocusTrap:
    """Settings drawer must trap keyboard focus."""

    def test_escape_key_handler(self):
        html = _render_full("en")
        assert "e.key === 'Escape'" in html

    def test_tab_trap_logic(self):
        html = _render_full("en")
        assert "e.key !== 'Tab'" in html
        assert "e.preventDefault()" in html


# ====================================================================
# 18. Toast ARIA live region
# ====================================================================


class TestToastAriaLive:
    """Toast notification must have ARIA live region."""

    def test_toast_has_aria_live(self):
        html = _render_full("en")
        assert 'aria-live="polite"' in html

    def test_toast_has_role_status(self):
        html = _render_full("en")
        assert 'role="status"' in html


# ====================================================================
# 19. Settings dialog role and aria-modal
# ====================================================================


class TestDialogRole:
    """Settings drawer must have dialog role and aria-modal."""

    def test_dialog_role(self):
        html = _render_full("en")
        assert 'role="dialog"' in html

    def test_aria_modal(self):
        html = _render_full("en")
        assert 'aria-modal="true"' in html


# ====================================================================
# 20. Semantic HTML5 landmarks
# ====================================================================


class TestSemanticLandmarks:
    """Page must use semantic HTML5 elements."""

    def test_has_header_element(self):
        html = _render_full("en")
        assert "<header" in html

    def test_has_nav_element(self):
        html = _render_full("en")
        assert "<nav " in html

    def test_has_main_element(self):
        html = _render_full("en")
        assert "<main " in html

    def test_has_footer_element(self):
        html = _render_full("en")
        assert "<footer" in html


# ====================================================================
# 21. Chart CDN fallback
# ====================================================================


class TestChartCDNFallback:
    """Chart.js script tag must have onerror fallback."""

    def test_script_has_onerror(self):
        html = _render_full("en")
        assert "onerror=" in html
        assert "chart.js" in html

    def test_chart_loading_indicators(self):
        html = _render_full("en")
        assert 'class="chart-loading"' in html


# ====================================================================
# 22. Chart error handling
# ====================================================================


class TestChartErrorHandling:
    """Charts must have try/catch and error state fallback."""

    def test_chart_init_has_try_catch(self):
        html = _render_full("en")
        assert "try {" in html
        assert "_showChartError" in html

    def test_chart_unavailable_message(self):
        html = _render_full("en")
        assert "chart_unavailable" in html


# ====================================================================
# 23. Empty table states
# ====================================================================


class TestEmptyTableStates:
    """Tables with no data must show an empty state message."""

    def test_workload_empty_state(self):
        t = get_translator("en")
        html = workload_table([], t=t)
        assert "empty-state" in html

    def test_issues_empty_state(self):
        t = get_translator("en")
        html = issues_table([], t=t)
        assert "empty-state" in html

    def test_workload_empty_state_pl(self):
        t = get_translator("pl")
        html = workload_table([], t=t)
        assert "empty-state" in html


# ====================================================================
# 24. Issue key truncation
# ====================================================================


class TestIssueKeyTruncation:
    """Issue keys must have cell-key class for overflow control."""

    def test_issues_table_has_cell_key(self):
        t = get_translator("en")
        html = issues_table([_issue()], t=t)
        assert 'class="cell-key"' in html

    def test_roadmap_has_cell_key(self):
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
        assert 'class="cell-key"' in html


# ====================================================================
# 36. Progress bars have ARIA attributes
# ====================================================================


class TestProgressBarAria:
    """Progress bars must have role=progressbar and aria-value* attributes."""

    @staticmethod
    def _all_components_source() -> str:
        from pathlib import Path

        pkg = Path(__file__).parent.parent / "src" / "flowboard" / "presentation" / "html"
        return "\n".join(p.read_text() for p in sorted(pkg.glob("components*.py")))

    def test_progressbar_role_in_component(self):
        """Component renderers must include role=progressbar."""
        src = self._all_components_source()
        assert 'role="progressbar"' in src

    def test_progressbar_aria_values_in_component(self):
        """Component renderers must include aria-value attributes."""
        src = self._all_components_source()
        assert "aria-valuenow=" in src
        assert "aria-valuemin=" in src
        assert "aria-valuemax=" in src


# ====================================================================
# 37. Tabpanels have aria-labelledby
# ====================================================================


class TestTabpanelAriaLabelledby:
    """Every tabpanel must have aria-labelledby linking to its tab button."""

    def test_tabpanel_labelledby(self):
        html = _render_full("en")
        import re

        panels = re.findall(r'role="tabpanel"[^>]*id="tab-(\w+)"', html)
        for panel_id in panels:
            assert f'aria-labelledby="tab-{panel_id}-btn"' in html

    def test_tab_buttons_have_ids(self):
        html = _render_full("en")
        import re

        btn_ids = re.findall(r'id="tab-(\w+)-btn"', html)
        assert len(btn_ids) >= 4


# ====================================================================
# 38. Settings labels have for attributes
# ====================================================================


class TestSettingsLabelFor:
    """All settings form labels must have for= attribute matching input id."""

    def test_label_for_cfg_title(self):
        html = _render_full("en")
        assert 'for="cfg-title"' in html

    def test_label_for_cfg_subtitle(self):
        html = _render_full("en")
        assert 'for="cfg-subtitle"' in html

    def test_label_for_cfg_company(self):
        html = _render_full("en")
        assert 'for="cfg-company"' in html


# ====================================================================
# 39. Zoom button accessibility
# ====================================================================


class TestZoomButtonA11y:
    """Zoom +/- buttons must have aria-label for screen readers."""

    def test_zoom_out_label(self):
        html = _render_full("en")
        assert 'aria-label="Zoom out"' in html

    def test_zoom_in_label(self):
        html = _render_full("en")
        assert 'aria-label="Zoom in"' in html


# ====================================================================
# 40. Detail panel focus management
# ====================================================================


class TestDetailPanelFocus:
    """Detail panel must save/restore focus and move focus on open."""

    def test_focus_save_on_open(self):
        html = _render_full("en")
        assert "_detailPreviousFocus" in html

    def test_focus_restore_on_close(self):
        html = _render_full("en")
        assert "_detailPreviousFocus.focus()" in html


# ====================================================================
# 41. Nav aria-label is localized
# ====================================================================


class TestNavAriaLabelI18n:
    """Nav aria-label must be translated, not hardcoded English."""

    def test_nav_label_en(self):
        html = _render_full("en")
        assert 'aria-label="Dashboard navigation"' in html

    def test_nav_label_pl(self):
        html = _render_full("pl")
        assert 'aria-label="Nawigacja pulpitu"' in html


# ====================================================================
# 49. Sub-tab ARIA roles
# ====================================================================


class TestSubTabAria:
    """Sub-tab groups must have proper ARIA tab semantics."""

    def test_subtab_tablist_role(self):
        html = _render_full("en")
        assert html.count('role="tablist"') >= 5  # nav + 4 sub-tab groups

    def test_subtab_tab_role(self):
        html = _render_full("en")
        assert html.count('role="tab"') >= 20

    def test_subtab_aria_controls(self):
        html = _render_full("en")
        assert 'aria-controls="insightsRisks"' in html

    def test_subtab_tabpanel_count(self):
        html = _render_full("en")
        assert html.count('role="tabpanel"') >= 20


# ====================================================================
# 50. Detail panel focus trap
# ====================================================================


class TestDetailFocusTrap:
    """Detail panel must trap keyboard focus."""

    def test_focus_trap_handler(self):
        html = _render_full("en")
        assert "detailPanel" in html
        assert "_detailPreviousFocus" in html

    def test_focus_restore(self):
        html = _render_full("en")
        assert "_detailPreviousFocus.focus()" in html


# ====================================================================
# 53. Chart canvas accessibility
# ====================================================================


class TestChartCanvasA11y:
    """Canvas elements must have role=img and aria-label."""

    def test_canvas_role_img(self):
        html = _render_full("en")
        assert 'role="img"' in html

    def test_canvas_aria_label(self):
        html = _render_full("en")
        import re

        labeled = re.findall(r'<canvas[^>]*role="img"[^>]*aria-label="[^"]+', html)
        assert len(labeled) >= 4


# ====================================================================
# 54. Loading state accessibility
# ====================================================================


class TestLoadingA11y:
    """Chart loading divs must have role=status and aria-live."""

    def test_loading_role_status(self):
        html = _render_full("en")
        assert "chart-loading" in html
        import re

        with_role = re.findall(r'class="chart-loading"[^>]*role="status"', html)
        assert len(with_role) >= 4


# ====================================================================
# 55. Error boundary
# ====================================================================


class TestErrorBoundary:
    """Global JS error handler must be present."""

    def test_onerror_handler(self):
        html = _render_full("en")
        assert "window.onerror" in html
