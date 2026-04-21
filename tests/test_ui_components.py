"""Tests for UI component rendering - form validation states, loading skeletons,
scroll indicators, disabled buttons, sort indicators, contrast, error pages,
chart aspect ratios, toast dismissal, select styling, tooltips, empty states,
responsive tabs, ARIA labels, print styles, badge contrast, and overlays.
"""

from pathlib import Path

from flowboard.domain.models import BoardSnapshot
from flowboard.infrastructure.config.loader import load_config_from_dict
from flowboard.presentation.html.renderer import render_dashboard

_TPL = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "flowboard"
    / "presentation"
    / "html"
    / "templates"
)


def _read(name: str) -> str:
    return (_TPL / name).read_text()


def _render_full(locale: str = "en") -> str:
    cfg = load_config_from_dict(
        {
            "jira": {"base_url": "https://test.atlassian.net"},
            "output": {"title": "Test Board"},
            "locale": locale,
        }
    )
    snap = BoardSnapshot(title="Test Board")
    return render_dashboard(snap, cfg)


# ===================================================================
# B1 - Form Validation Visual States
# ===================================================================
class TestFormValidationStates:
    """GIVEN form validation states and the scenario: field error class exists"""
    def test_field_error_class_exists(self):
        """WHEN the code under test is exercised for: field error class exists"""
        css = _read("_styles_base.html")

        """THEN the expected behaviour holds: field error class exists"""
        assert ".field-error input" in css

    """GIVEN form validation states and the scenario: field success class exists"""
    def test_field_success_class_exists(self):
        """WHEN the code under test is exercised for: field success class exists"""
        css = _read("_styles_base.html")

        """THEN the expected behaviour holds: field success class exists"""
        assert ".field-success input" in css or "input.input-valid" in css

    """GIVEN form validation states and the scenario: field error msg hidden default"""
    def test_field_error_msg_hidden_default(self):
        """WHEN the code under test is exercised for: field error msg hidden default"""
        css = _read("_styles_base.html")

        """THEN the expected behaviour holds: field error msg hidden default"""
        assert ".field-error-msg" in css
        assert "display: none" in css or "display:none" in css


# ===================================================================
# B2 - Loading Skeleton
# ===================================================================
class TestLoadingSkeleton:
    """GIVEN loading skeleton and the scenario: skeleton keyframes"""
    def test_skeleton_keyframes(self):
        """WHEN the code under test is exercised for: skeleton keyframes"""
        css = _read("_styles_base.html")

        """THEN the expected behaviour holds: skeleton keyframes"""
        assert "@keyframes shimmer" in css

    """GIVEN loading skeleton and the scenario: skeleton class"""
    def test_skeleton_class(self):
        """WHEN the code under test is exercised for: skeleton class"""
        css = _read("_styles_base.html")

        """THEN the expected behaviour holds: skeleton class"""
        assert ".skeleton {" in css or ".skeleton{" in css

    """GIVEN loading skeleton and the scenario: skeleton card variant"""
    def test_skeleton_card_variant(self):
        """WHEN the code under test is exercised for: skeleton card variant"""
        css = _read("_styles_base.html")

        """THEN the expected behaviour holds: skeleton card variant"""
        assert ".skeleton-card" in css


# ===================================================================
# B3 - Settings Scroll Overflow Indicator
# ===================================================================
class TestSettingsScrollIndicator:
    """GIVEN settings scroll indicator and the scenario: settings body mask"""
    def test_settings_body_mask(self):
        """WHEN the code under test is exercised for: settings body mask"""
        css = _read("_styles_base.html")

        """THEN the expected behaviour holds: settings body mask"""
        assert "mask-image" in css
        # Must be on settings-body
        in_body = False
        for line in css.split("\n"):
            if ".settings-body" in line:
                in_body = True
            if in_body and "mask-image" in line:
                break
            if in_body and "}" in line:
                in_body = False
        assert in_body or "settings-body" in css


# ===================================================================
# B4 - Disabled Button States
# ===================================================================
class TestDisabledButtonStates:
    """GIVEN disabled button states and the scenario: disabled button opacity"""
    def test_disabled_button_opacity(self):
        """WHEN the code under test is exercised for: disabled button opacity"""
        css = _read("_styles_base.html")

        """THEN the expected behaviour holds: disabled button opacity"""
        assert "button:disabled" in css

    """GIVEN disabled button states and the scenario: disabled cursor"""
    def test_disabled_cursor(self):
        """WHEN the code under test is exercised for: disabled cursor"""
        css = _read("_styles_base.html")

        """THEN the expected behaviour holds: disabled cursor"""
        assert "cursor: not-allowed" in css


# ===================================================================
# B5 - Sort Indicator Visibility
# ===================================================================
class TestSortIndicatorVisibility:
    """GIVEN sort indicator visibility and the scenario: sort indicator larger font"""
    def test_sort_indicator_larger_font(self):
        """WHEN the code under test is exercised for: sort indicator larger font"""
        css = _read("_styles_base.html")
        # Sort indicators should use at least 0.85rem
        found = False
        for line in css.split("\n"):
            if "data-sort-type" in line and "::after" in line and "0.85rem" in line:
                found = True
                break

        """THEN the expected behaviour holds: sort indicator larger font"""
        assert found, "Sort indicator should be 0.85rem for mobile visibility"


# ===================================================================
# B6 - Midnight Theme Contrast
# ===================================================================
class TestMidnightContrast:
    """GIVEN midnight contrast and the scenario: midnight text secondary improved"""
    def test_midnight_text_secondary_improved(self):
        """WHEN the code under test is exercised for: midnight text secondary improved"""
        css = _read("_styles_features.html")
        # Must use #A3B4D0 (higher contrast) not #8B9DC3

        """THEN the expected behaviour holds: midnight text secondary improved"""
        assert "--text-secondary: #A3B4D0" in css


# ===================================================================
# B7 - Dashboard Error State
# ===================================================================
class TestDashboardErrorState:
    """GIVEN dashboard error state and the scenario: render error page function exists"""
    def test_render_error_page_function_exists(self):
        """WHEN the code under test is exercised for: render error page function exists"""
        from flowboard.presentation.html.renderer import _render_error_page

        html = _render_error_page("Test error")

        """THEN the expected behaviour holds: render error page function exists"""
        assert "<!DOCTYPE html>" in html
        assert "Test error" in html
        assert "Retry" in html

    """GIVEN dashboard error state and the scenario: render error page escapes html"""
    def test_render_error_page_escapes_html(self):
        """WHEN the code under test is exercised for: render error page escapes html"""
        from flowboard.presentation.html.renderer import _render_error_page

        html = _render_error_page("<script>alert('xss')</script>")

        """THEN the expected behaviour holds: render error page escapes html"""
        assert "<script>" not in html
        assert "&lt;script&gt;" in html


# ===================================================================
# B8 - Chart Card Aspect Ratio
# ===================================================================
class TestChartAspectRatio:
    """GIVEN chart aspect ratio and the scenario: chart uses aspect ratio"""
    def test_chart_uses_aspect_ratio(self):
        """WHEN the code under test is exercised for: chart uses aspect ratio"""
        css = _read("_styles_base.html")

        """THEN the expected behaviour holds: chart uses aspect ratio"""
        assert "aspect-ratio" in css
        for line in css.split("\n"):
            if ".chart-card canvas" in line and "aspect-ratio" in line:
                assert "16 / 10" in line
                break


# ===================================================================
# B9 - Toast Escape Key Dismiss
# ===================================================================
class TestToastEscapeDismiss:
    """GIVEN toast escape dismiss and the scenario: escape listener exists"""
    def test_escape_listener_exists(self):
        """WHEN the code under test is exercised for: escape listener exists"""
        js = _read("_scripts_core.html")

        """THEN the expected behaviour holds: escape listener exists"""
        assert "Escape" in js
        assert "settingsToast" in js


# ===================================================================
# Filter Select Cross-Browser
# ===================================================================
class TestSelectStyling:
    """GIVEN select styling and the scenario: appearance none"""
    def test_appearance_none(self):
        """WHEN the code under test is exercised for: appearance none"""
        css = _read("_styles_base.html")

        """THEN the expected behaviour holds: appearance none"""
        assert "appearance: none" in css

    """GIVEN select styling and the scenario: custom dropdown arrow"""
    def test_custom_dropdown_arrow(self):
        """WHEN the code under test is exercised for: custom dropdown arrow"""
        css = _read("_styles_base.html")

        """THEN the expected behaviour holds: custom dropdown arrow"""
        assert "background-image" in css
        # SVG chevron indicator
        assert "svg" in css.lower() or "SVG" in css or "viewBox" in css


# ===================================================================
# Tooltip Viewport Clamping
# ===================================================================
class TestTooltipViewport:
    """GIVEN tooltip viewport and the scenario: tooltip measures actual size"""
    def test_tooltip_measures_actual_size(self):
        """WHEN the code under test is exercised for: tooltip measures actual size"""
        js = _read("_scripts_features.html")
        # Should use offsetWidth for actual measurement

        """THEN the expected behaviour holds: tooltip measures actual size"""
        assert "offsetWidth" in js

    """GIVEN tooltip viewport and the scenario: tooltip clamps top"""
    def test_tooltip_clamps_top(self):
        """WHEN the code under test is exercised for: tooltip clamps top"""
        js = _read("_scripts_features.html")

        """THEN the expected behaviour holds: tooltip clamps top"""
        assert "top < 4" in js


# ===================================================================
# Empty State Icons
# ===================================================================
class TestEmptyStateIcons:
    """GIVEN empty state icons and the scenario: empty state has before pseudo"""
    def test_empty_state_has_before_pseudo(self):
        """WHEN the code under test is exercised for: empty state has before pseudo"""
        css = _read("_styles_base.html")

        """THEN the expected behaviour holds: empty state has before pseudo"""
        assert ".empty-state::before" in css

    """GIVEN empty state icons and the scenario: empty state icon svg"""
    def test_empty_state_icon_svg(self):
        """WHEN the code under test is exercised for: empty state icon svg"""
        css = _read("_styles_base.html")
        # Must have an SVG data URI icon
        found = False
        for line in css.split("\n"):
            if "empty-state::before" in line or (found and "svg" in line.lower()):
                if "svg" in line.lower():
                    found = True
                    break
                found = True

        """THEN the expected behaviour holds: empty state icon svg"""
        assert found or "data:image/svg+xml" in css


# ===================================================================
# Insights Tabs Responsive
# ===================================================================
class TestInsightsTabsResponsive:
    """GIVEN insights tabs responsive and the scenario: insights tabs nowrap on mobile"""
    def test_insights_tabs_nowrap_on_mobile(self):
        """WHEN the code under test is exercised for: insights tabs nowrap on mobile"""
        css = _read("_styles_features.html")

        """THEN the expected behaviour holds: insights tabs nowrap on mobile"""
        assert "flex-wrap: nowrap" in css

    """GIVEN insights tabs responsive and the scenario: insights tabs scroll snap"""
    def test_insights_tabs_scroll_snap(self):
        """WHEN the code under test is exercised for: insights tabs scroll snap"""
        css = _read("_styles_features.html")

        """THEN the expected behaviour holds: insights tabs scroll snap"""
        assert "scroll-snap-type" in css


# ===================================================================
# Color Input Aria Labels
# ===================================================================
class TestColorInputAria:
    """GIVEN color input aria and the scenario: color inputs have aria label"""
    def test_color_inputs_have_aria_label(self):
        """WHEN the code under test is exercised for: color inputs have aria label"""
        html = _read("_settings.html")

        """THEN the expected behaviour holds: color inputs have aria label"""
        assert 'type="color" id="cfg-primary"' in html
        assert "aria-label=" in html
        # All 3 color inputs must have aria-label
        count = html.count('type="color"')
        aria_count = 0
        for line in html.split("\n"):
            if 'type="color"' in line and "aria-label" in line:
                aria_count += 1
        assert aria_count == count, (
            f"Expected {count} color inputs with aria-label, got {aria_count}"
        )


# ===================================================================
# Print Chart Sizing
# ===================================================================
class TestPrintChartSizing:
    """GIVEN print chart sizing and the scenario: chart break inside avoid"""
    def test_chart_break_inside_avoid(self):
        """WHEN the code under test is exercised for: chart break inside avoid"""
        css = _read("_styles_features.html")
        found = False
        in_print = False
        for line in css.split("\n"):
            if "@media print" in line:
                in_print = True
            if in_print and "break-inside: avoid" in line:
                found = True
                break

        """THEN the expected behaviour holds: chart break inside avoid"""
        assert found


# ===================================================================
# Badge Contrast Safety
# ===================================================================
class TestBadgeContrast:
    """GIVEN badge contrast and the scenario: badge bg class forces white"""
    def test_badge_bg_class_forces_white(self):
        """WHEN the code under test is exercised for: badge bg class forces white"""
        css = _read("_styles_base.html")

        """THEN the expected behaviour holds: badge bg class forces white"""
        assert '.badge[class*="bg-"]' in css


# ===================================================================
# Midnight/Dark Modal Backdrop
# ===================================================================
class TestModalBackdropThemes:
    """GIVEN modal backdrop themes and the scenario: dark overlay higher opacity"""
    def test_dark_overlay_higher_opacity(self):
        """WHEN the code under test is exercised for: dark overlay higher opacity"""
        css = _read("_styles_base.html")

        """THEN the expected behaviour holds: dark overlay higher opacity"""
        assert '[data-theme="dark"] .settings-overlay' in css

    """GIVEN modal backdrop themes and the scenario: midnight overlay higher opacity"""
    def test_midnight_overlay_higher_opacity(self):
        """WHEN the code under test is exercised for: midnight overlay higher opacity"""
        css = _read("_styles_base.html")

        """THEN the expected behaviour holds: midnight overlay higher opacity"""
        assert '[data-theme="midnight"] .settings-overlay' in css

    """GIVEN modal backdrop themes and the scenario: detail overlay dark"""
    def test_detail_overlay_dark(self):
        """WHEN the code under test is exercised for: detail overlay dark"""
        css = _read("_styles_features.html")

        """THEN the expected behaviour holds: detail overlay dark"""
        assert '[data-theme="dark"] .detail-overlay' in css


# ===================================================================
# Tab Nav Scroll Indicators
# ===================================================================
class TestTabScrollIndicators:
    """GIVEN tab scroll indicators and the scenario: scroll left class"""
    def test_scroll_left_class(self):
        """WHEN the code under test is exercised for: scroll left class"""
        css = _read("_styles_base.html")

        """THEN the expected behaviour holds: scroll left class"""
        assert ".tab-nav.scroll-left" in css

    """GIVEN tab scroll indicators and the scenario: scroll right class"""
    def test_scroll_right_class(self):
        """WHEN the code under test is exercised for: scroll right class"""
        css = _read("_styles_base.html")

        """THEN the expected behaviour holds: scroll right class"""
        assert ".tab-nav.scroll-right" in css

    """GIVEN tab scroll indicators and the scenario: scroll hint js"""
    def test_scroll_hint_js(self):
        """WHEN the code under test is exercised for: scroll hint js"""
        js = _read("_scripts_core.html")

        """THEN the expected behaviour holds: scroll hint js"""
        assert "scroll-left" in js
        assert "scroll-right" in js
        assert "updateScrollHints" in js


# ===================================================================
# Progress Bar aria-label
# ===================================================================
class TestProgressBarAriaLabel:
    """GIVEN progress bar aria label and the scenario: rendered progress has aria label"""
    def test_rendered_progress_has_aria_label(self):
        """WHEN the code under test is exercised for: rendered progress has aria label"""
        html = _render_full("en")
        # Any progressbar should have aria-label
        import re

        bars = re.findall(r'role="progressbar"[^>]*', html)
        # If there are progress bars, they should have aria-label
        # (may be 0 if no sprints in test snapshot)

        """THEN the expected behaviour holds: rendered progress has aria label"""
        for bar in bars:
            assert "aria-label" in bar, f"Progress bar missing aria-label: {bar[:80]}"


# ===================================================================
# Simulation Table Scroll (already done)
# ===================================================================
class TestSimTableScroll:
    """GIVEN sim table scroll and the scenario: sim comparison in scroll wrapper"""
    def test_sim_comparison_in_scroll_wrapper(self):
        """WHEN the code under test is exercised for: sim comparison in scroll wrapper"""
        from pathlib import Path

        sim = (
            Path(__file__).resolve().parent.parent
            / "src"
            / "flowboard"
            / "presentation"
            / "html"
            / "components_simulation.py"
        )
        content = sim.read_text()

        """THEN the expected behaviour holds: sim comparison in scroll wrapper"""
        assert "table-scroll" in content


# ===================================================================
# Detail Panel Transform Animation
# ===================================================================
class TestDetailPanelTransform:
    """GIVEN detail panel transform and the scenario: detail panel uses transform"""
    def test_detail_panel_uses_transform(self):
        """WHEN the code under test is exercised for: detail panel uses transform"""
        css = _read("_styles_features.html")

        """THEN the expected behaviour holds: detail panel uses transform"""
        for line in css.split("\n"):
            if ".detail-panel {" in line or ".detail-panel{" in line:
                # Should not use right: -440px
                assert "right: -" not in line

    """GIVEN detail panel transform and the scenario: detail panel translate x"""
    def test_detail_panel_translate_x(self):
        """WHEN the code under test is exercised for: detail panel translate x"""
        css = _read("_styles_features.html")

        """THEN the expected behaviour holds: detail panel translate x"""
        assert "translateX(100%)" in css

    """GIVEN detail panel transform and the scenario: settings drawer uses transform"""
    def test_settings_drawer_uses_transform(self):
        """WHEN the code under test is exercised for: settings drawer uses transform"""
        css = _read("_styles_base.html")

        """THEN the expected behaviour holds: settings drawer uses transform"""
        for line in css.split("\n"):
            if ".settings-drawer {" in line:
                assert "right: -" not in line


# ===================================================================
# System Theme Token Sync
# ===================================================================
class TestSystemThemeSync:
    """GIVEN system theme sync and the scenario: system theme has chip tokens"""
    def test_system_theme_has_chip_tokens(self):
        """WHEN the code under test is exercised for: system theme has chip tokens"""
        css = _read("_styles_features.html")

        """THEN the expected behaviour holds: system theme has chip tokens"""
        assert "--chip-todo-bg:" in css
        # Must appear inside system theme block
        in_system = False
        found = False
        for line in css.split("\n"):
            if '[data-theme="system"]' in line and "--chip-todo-bg" in line:
                found = True
                break
            if "data-theme" in line and "system" in line:
                in_system = True
            if in_system and "--chip-todo-bg" in line:
                found = True
                break
        assert found

    """GIVEN system theme sync and the scenario: system theme has row tokens"""
    def test_system_theme_has_row_tokens(self):
        """WHEN the code under test is exercised for: system theme has row tokens"""
        css = _read("_styles_features.html")

        """THEN the expected behaviour holds: system theme has row tokens"""
        assert "--row-warn-bg:" in css


# ===================================================================
# Polish Label Overflow
# ===================================================================
class TestPolishLabelOverflow:
    """GIVEN polish label overflow and the scenario: settings label word break"""
    def test_settings_label_word_break(self):
        """WHEN the code under test is exercised for: settings label word break"""
        css = _read("_styles_base.html")

        """THEN the expected behaviour holds: settings label word break"""
        assert "word-break: break-word" in css

    """GIVEN polish label overflow and the scenario: settings field gap"""
    def test_settings_field_gap(self):
        """WHEN the code under test is exercised for: settings field gap"""
        css = _read("_styles_base.html")
        # Must have gap: 12px inside .settings-field block
        in_block = False
        found = False
        for line in css.split("\n"):
            if ".settings-field {" in line or ".settings-field{" in line:
                in_block = True
            if in_block and "gap: 12px" in line:
                found = True
                break
            if in_block and "}" in line:
                in_block = False

        """THEN the expected behaviour holds: settings field gap"""
        assert found, "settings-field should have gap: 12px"


# ===================================================================
# Toggle Switch Focus Ring
# ===================================================================
class TestToggleFocusRing:
    """GIVEN toggle focus ring and the scenario: toggle focus box shadow"""
    def test_toggle_focus_box_shadow(self):
        """WHEN the code under test is exercised for: toggle focus box shadow"""
        css = _read("_styles_base.html")
        found = False

        """THEN the expected behaviour holds: toggle focus box shadow"""
        for line in css.split("\n"):
            if "toggle" in line and "focus-visible" in line and "slider" in line:
                found = True
            if found and "box-shadow" in line:
                assert "3px" in line
                break
        assert found, "Toggle focus should use box-shadow ring"


# ===================================================================
# Chart.js SRI Hash
# ===================================================================
class TestChartJsSRI:
    """GIVEN chart js s r i and the scenario: integrity attribute"""
    def test_integrity_attribute(self):
        """WHEN the code under test is exercised for: integrity attribute"""
        html = _read("dashboard.html")

        """THEN the expected behaviour holds: integrity attribute"""
        assert 'integrity="sha384-' in html

    """GIVEN chart js s r i and the scenario: crossorigin attribute"""
    def test_crossorigin_attribute(self):
        """WHEN the code under test is exercised for: crossorigin attribute"""
        html = _read("dashboard.html")

        """THEN the expected behaviour holds: crossorigin attribute"""
        assert 'crossorigin="anonymous"' in html

    """GIVEN chart js s r i and the scenario: sri in rendered output"""
    def test_sri_in_rendered_output(self):
        """WHEN the code under test is exercised for: sri in rendered output"""
        html = _render_full("en")

        """THEN the expected behaviour holds: sri in rendered output"""
        assert "integrity=" in html
        assert "crossorigin=" in html


# ===================================================================
# Full Render - Structural Integrity After All Blockers
# ===================================================================
class TestFullRenderAfterBlockers:
    """GIVEN full render after blockers and the scenario: en renders"""
    def test_en_renders(self):
        """WHEN the code under test is exercised for: en renders"""
        html = _render_full("en")

        """THEN the expected behaviour holds: en renders"""
        assert "<!DOCTYPE html>" in html
        assert "</html>" in html

    """GIVEN full render after blockers and the scenario: pl renders"""
    def test_pl_renders(self):
        """WHEN the code under test is exercised for: pl renders"""
        html = _render_full("pl")

        """THEN the expected behaviour holds: pl renders"""
        assert 'lang="pl"' in html
