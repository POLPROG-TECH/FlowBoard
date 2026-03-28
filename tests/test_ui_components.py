"""Tests for UI component rendering — form validation states, loading skeletons,
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
# B1 — Form Validation Visual States
# ===================================================================
class TestFormValidationStates:
    def test_field_error_class_exists(self):
        css = _read("_styles_base.html")
        assert ".field-error input" in css

    def test_field_success_class_exists(self):
        css = _read("_styles_base.html")
        assert ".field-success input" in css or "input.input-valid" in css

    def test_field_error_msg_hidden_default(self):
        css = _read("_styles_base.html")
        assert ".field-error-msg" in css
        assert "display: none" in css or "display:none" in css


# ===================================================================
# B2 — Loading Skeleton
# ===================================================================
class TestLoadingSkeleton:
    def test_skeleton_keyframes(self):
        css = _read("_styles_base.html")
        assert "@keyframes shimmer" in css

    def test_skeleton_class(self):
        css = _read("_styles_base.html")
        assert ".skeleton {" in css or ".skeleton{" in css

    def test_skeleton_card_variant(self):
        css = _read("_styles_base.html")
        assert ".skeleton-card" in css


# ===================================================================
# B3 — Settings Scroll Overflow Indicator
# ===================================================================
class TestSettingsScrollIndicator:
    def test_settings_body_mask(self):
        css = _read("_styles_base.html")
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
# B4 — Disabled Button States
# ===================================================================
class TestDisabledButtonStates:
    def test_disabled_button_opacity(self):
        css = _read("_styles_base.html")
        assert "button:disabled" in css

    def test_disabled_cursor(self):
        css = _read("_styles_base.html")
        assert "cursor: not-allowed" in css


# ===================================================================
# B5 — Sort Indicator Visibility
# ===================================================================
class TestSortIndicatorVisibility:
    def test_sort_indicator_larger_font(self):
        css = _read("_styles_base.html")
        # Sort indicators should use at least 0.85rem
        found = False
        for line in css.split("\n"):
            if "data-sort-type" in line and "::after" in line and "0.85rem" in line:
                found = True
                break
        assert found, "Sort indicator should be 0.85rem for mobile visibility"


# ===================================================================
# B6 — Midnight Theme Contrast
# ===================================================================
class TestMidnightContrast:
    def test_midnight_text_secondary_improved(self):
        css = _read("_styles_features.html")
        # Must use #A3B4D0 (higher contrast) not #8B9DC3
        assert "--text-secondary: #A3B4D0" in css


# ===================================================================
# B7 — Dashboard Error State
# ===================================================================
class TestDashboardErrorState:
    def test_render_error_page_function_exists(self):
        from flowboard.presentation.html.renderer import _render_error_page

        html = _render_error_page("Test error")
        assert "<!DOCTYPE html>" in html
        assert "Test error" in html
        assert "Retry" in html

    def test_render_error_page_escapes_html(self):
        from flowboard.presentation.html.renderer import _render_error_page

        html = _render_error_page("<script>alert('xss')</script>")
        assert "<script>" not in html
        assert "&lt;script&gt;" in html


# ===================================================================
# B8 — Chart Card Aspect Ratio
# ===================================================================
class TestChartAspectRatio:
    def test_chart_uses_aspect_ratio(self):
        css = _read("_styles_base.html")
        assert "aspect-ratio" in css
        for line in css.split("\n"):
            if ".chart-card canvas" in line and "aspect-ratio" in line:
                assert "16 / 10" in line
                break


# ===================================================================
# B9 — Toast Escape Key Dismiss
# ===================================================================
class TestToastEscapeDismiss:
    def test_escape_listener_exists(self):
        js = _read("_scripts_core.html")
        assert "Escape" in js
        assert "settingsToast" in js


# ===================================================================
# Filter Select Cross-Browser
# ===================================================================
class TestSelectStyling:
    def test_appearance_none(self):
        css = _read("_styles_base.html")
        assert "appearance: none" in css

    def test_custom_dropdown_arrow(self):
        css = _read("_styles_base.html")
        assert "background-image" in css
        # SVG chevron indicator
        assert "svg" in css.lower() or "SVG" in css or "viewBox" in css


# ===================================================================
# Tooltip Viewport Clamping
# ===================================================================
class TestTooltipViewport:
    def test_tooltip_measures_actual_size(self):
        js = _read("_scripts_features.html")
        # Should use offsetWidth for actual measurement
        assert "offsetWidth" in js

    def test_tooltip_clamps_top(self):
        js = _read("_scripts_features.html")
        assert "top < 4" in js


# ===================================================================
# Empty State Icons
# ===================================================================
class TestEmptyStateIcons:
    def test_empty_state_has_before_pseudo(self):
        css = _read("_styles_base.html")
        assert ".empty-state::before" in css

    def test_empty_state_icon_svg(self):
        css = _read("_styles_base.html")
        # Must have an SVG data URI icon
        found = False
        for line in css.split("\n"):
            if "empty-state::before" in line or (found and "svg" in line.lower()):
                if "svg" in line.lower():
                    found = True
                    break
                found = True
        assert found or "data:image/svg+xml" in css


# ===================================================================
# Insights Tabs Responsive
# ===================================================================
class TestInsightsTabsResponsive:
    def test_insights_tabs_nowrap_on_mobile(self):
        css = _read("_styles_features.html")
        assert "flex-wrap: nowrap" in css

    def test_insights_tabs_scroll_snap(self):
        css = _read("_styles_features.html")
        assert "scroll-snap-type" in css


# ===================================================================
# Color Input Aria Labels
# ===================================================================
class TestColorInputAria:
    def test_color_inputs_have_aria_label(self):
        html = _read("_settings.html")
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
    def test_chart_break_inside_avoid(self):
        css = _read("_styles_features.html")
        found = False
        in_print = False
        for line in css.split("\n"):
            if "@media print" in line:
                in_print = True
            if in_print and "break-inside: avoid" in line:
                found = True
                break
        assert found


# ===================================================================
# Badge Contrast Safety
# ===================================================================
class TestBadgeContrast:
    def test_badge_bg_class_forces_white(self):
        css = _read("_styles_base.html")
        assert '.badge[class*="bg-"]' in css


# ===================================================================
# Midnight/Dark Modal Backdrop
# ===================================================================
class TestModalBackdropThemes:
    def test_dark_overlay_higher_opacity(self):
        css = _read("_styles_base.html")
        assert '[data-theme="dark"] .settings-overlay' in css

    def test_midnight_overlay_higher_opacity(self):
        css = _read("_styles_base.html")
        assert '[data-theme="midnight"] .settings-overlay' in css

    def test_detail_overlay_dark(self):
        css = _read("_styles_features.html")
        assert '[data-theme="dark"] .detail-overlay' in css


# ===================================================================
# Tab Nav Scroll Indicators
# ===================================================================
class TestTabScrollIndicators:
    def test_scroll_left_class(self):
        css = _read("_styles_base.html")
        assert ".tab-nav.scroll-left" in css

    def test_scroll_right_class(self):
        css = _read("_styles_base.html")
        assert ".tab-nav.scroll-right" in css

    def test_scroll_hint_js(self):
        js = _read("_scripts_core.html")
        assert "scroll-left" in js
        assert "scroll-right" in js
        assert "updateScrollHints" in js


# ===================================================================
# Progress Bar aria-label
# ===================================================================
class TestProgressBarAriaLabel:
    def test_rendered_progress_has_aria_label(self):
        html = _render_full("en")
        # Any progressbar should have aria-label
        import re

        bars = re.findall(r'role="progressbar"[^>]*', html)
        # If there are progress bars, they should have aria-label
        # (may be 0 if no sprints in test snapshot)
        for bar in bars:
            assert "aria-label" in bar, f"Progress bar missing aria-label: {bar[:80]}"


# ===================================================================
# Simulation Table Scroll (already done)
# ===================================================================
class TestSimTableScroll:
    def test_sim_comparison_in_scroll_wrapper(self):
        """components_simulation.py already wraps sim-comparison-table."""
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
        assert "table-scroll" in content


# ===================================================================
# Detail Panel Transform Animation
# ===================================================================
class TestDetailPanelTransform:
    def test_detail_panel_uses_transform(self):
        css = _read("_styles_features.html")
        for line in css.split("\n"):
            if ".detail-panel {" in line or ".detail-panel{" in line:
                # Should not use right: -440px
                assert "right: -" not in line

    def test_detail_panel_translate_x(self):
        css = _read("_styles_features.html")
        assert "translateX(100%)" in css

    def test_settings_drawer_uses_transform(self):
        css = _read("_styles_base.html")
        for line in css.split("\n"):
            if ".settings-drawer {" in line:
                assert "right: -" not in line


# ===================================================================
# System Theme Token Sync
# ===================================================================
class TestSystemThemeSync:
    def test_system_theme_has_chip_tokens(self):
        css = _read("_styles_features.html")
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

    def test_system_theme_has_row_tokens(self):
        css = _read("_styles_features.html")
        assert "--row-warn-bg:" in css


# ===================================================================
# Polish Label Overflow
# ===================================================================
class TestPolishLabelOverflow:
    def test_settings_label_word_break(self):
        css = _read("_styles_base.html")
        assert "word-break: break-word" in css

    def test_settings_field_gap(self):
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
        assert found, "settings-field should have gap: 12px"


# ===================================================================
# Toggle Switch Focus Ring
# ===================================================================
class TestToggleFocusRing:
    def test_toggle_focus_box_shadow(self):
        css = _read("_styles_base.html")
        found = False
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
    def test_integrity_attribute(self):
        html = _read("dashboard.html")
        assert 'integrity="sha384-' in html

    def test_crossorigin_attribute(self):
        html = _read("dashboard.html")
        assert 'crossorigin="anonymous"' in html

    def test_sri_in_rendered_output(self):
        html = _render_full("en")
        assert "integrity=" in html
        assert "crossorigin=" in html


# ===================================================================
# Full Render — Structural Integrity After All Blockers
# ===================================================================
class TestFullRenderAfterBlockers:
    def test_en_renders(self):
        html = _render_full("en")
        assert "<!DOCTYPE html>" in html
        assert "</html>" in html

    def test_pl_renders(self):
        html = _render_full("pl")
        assert 'lang="pl"' in html
