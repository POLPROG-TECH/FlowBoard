"""Interactive accessibility tests - focus traps, keyboard navigation, ARIA widgets, heading hierarchy."""

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
# 42. Heading hierarchy correctness
# ====================================================================


class TestHeadingHierarchy:
    """Tests for heading hierarchy."""

    """GIVEN heading hierarchy and the scenario: no h4 in chart cards"""
    def test_no_h4_in_chart_cards(self):
        """WHEN the code under test is exercised for: no h4 in chart cards"""
        html = _render_full("en")
        import re

        h4_in_charts = re.findall(r'<div class="chart-card[^"]*">\s*<h4>', html)

        """THEN the expected behaviour holds: no h4 in chart cards"""
        assert len(h4_in_charts) == 0, f"Found h4 in chart cards: {h4_in_charts}"


# ====================================================================
# 43. Dark theme coverage for toggle/pi-sprint/btn-danger
# ====================================================================


class TestEmptyStateRole:
    """Tests for empty state role."""

    """GIVEN empty state role and the scenario: empty state role"""
    def test_empty_state_role(self):
        """WHEN the code under test is exercised for: empty state role"""
        html = _render_full("en")
        # Every empty-state should have role="status"
        import re

        empties = re.findall(r'class="empty-state"', html)
        empties_with_role = re.findall(r'class="empty-state" role="status"', html)

        """THEN the expected behaviour holds: empty state role"""
        assert len(empties) == len(empties_with_role)


# ====================================================================
# 47. Word-break on table cells
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
# 51. RTL support
# ====================================================================


class TestRTLSupport:
    """Tests for r t l support."""

    """GIVEN r t l support and the scenario: rtl dir attribute"""
    def test_rtl_dir_attribute(self):
        """WHEN the code under test is exercised for: rtl dir attribute"""
        html = _render_full("en")

        """THEN the expected behaviour holds: rtl dir attribute"""
        assert 'dir="ltr"' in html

    """GIVEN r t l support and the scenario: rtl css rules"""
    def test_rtl_css_rules(self):
        """WHEN the code under test is exercised for: rtl css rules"""
        html = _render_full("en")

        """THEN the expected behaviour holds: rtl css rules"""
        assert '[dir="rtl"]' in html
        assert '[dir="rtl"] .settings-drawer' in html


# ====================================================================
# 52. Timeline keyboard navigation
# ====================================================================


class TestTimelineKeyboard:
    """Tests for timeline keyboard."""

    """GIVEN timeline keyboard and the scenario: bar tabindex"""
    def test_bar_tabindex(self):
        """WHEN the code under test is exercised for: bar tabindex"""
        from pathlib import Path

        pkg = Path(__file__).parent.parent / "src" / "flowboard" / "presentation" / "html"
        src = "\n".join(p.read_text() for p in sorted(pkg.glob("components*.py")))

        """THEN the expected behaviour holds: bar tabindex"""
        assert 'tabindex="0"' in src

    """GIVEN timeline keyboard and the scenario: keyboard handler"""
    def test_keyboard_handler(self):
        """WHEN the code under test is exercised for: keyboard handler"""
        html = _render_full("en")

        """THEN the expected behaviour holds: keyboard handler"""
        assert "Enter" in html or "keydown" in html


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


# ====================================================================
# 56. Print styles
# ====================================================================
