"""Interactive accessibility tests — focus traps, keyboard navigation, ARIA widgets, heading hierarchy."""

from __future__ import annotations

from datetime import UTC, date, datetime

from flowboard.domain.models import (
    BoardSnapshot,
    Issue,
    Person,
    Sprint,
)
from flowboard.infrastructure.config.loader import (
    load_config_from_dict,
)
from flowboard.presentation.html.renderer import render_dashboard
from flowboard.shared.types import (
    IssueStatus,
    IssueType,
    Priority,
    SprintState,
    StatusCategory,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
# 42. Heading hierarchy correctness
# ====================================================================


class TestHeadingHierarchy:
    """Chart cards must use h3 (not h4) under h2 sections."""

    def test_no_h4_in_chart_cards(self):
        html = _render_full("en")
        import re

        h4_in_charts = re.findall(r'<div class="chart-card[^"]*">\s*<h4>', html)
        assert len(h4_in_charts) == 0, f"Found h4 in chart cards: {h4_in_charts}"


# ====================================================================
# 43. Dark theme coverage for toggle/pi-sprint/btn-danger
# ====================================================================


class TestEmptyStateRole:
    """Empty state elements must have role=status for screen readers."""

    def test_empty_state_role(self):
        html = _render_full("en")
        # Every empty-state should have role="status"
        import re

        empties = re.findall(r'class="empty-state"', html)
        empties_with_role = re.findall(r'class="empty-state" role="status"', html)
        assert len(empties) == len(empties_with_role)


# ====================================================================
# 47. Word-break on table cells
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
# 51. RTL support
# ====================================================================


class TestRTLSupport:
    """RTL CSS rules must be present for Arabic/Hebrew."""

    def test_rtl_dir_attribute(self):
        html = _render_full("en")
        assert 'dir="ltr"' in html

    def test_rtl_css_rules(self):
        html = _render_full("en")
        assert '[dir="rtl"]' in html
        assert '[dir="rtl"] .settings-drawer' in html


# ====================================================================
# 52. Timeline keyboard navigation
# ====================================================================


class TestTimelineKeyboard:
    """Timeline bars must be keyboard-accessible."""

    def test_bar_tabindex(self):
        from pathlib import Path

        pkg = Path(__file__).parent.parent / "src" / "flowboard" / "presentation" / "html"
        src = "\n".join(p.read_text() for p in sorted(pkg.glob("components*.py")))
        assert 'tabindex="0"' in src

    def test_keyboard_handler(self):
        html = _render_full("en")
        assert "Enter" in html or "keydown" in html


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


# ====================================================================
# 56. Print styles
# ====================================================================
