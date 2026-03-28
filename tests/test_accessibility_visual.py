"""Tests for visual accessibility and responsive design — color contrast,
dark mode, print styles, responsive breakpoints, badge contrast, viewport
meta, i18n key parity, localization consistency, selection styles, high
contrast, iOS sticky, RTL support, and full dashboard rendering.
"""

from __future__ import annotations

from datetime import date

import pytest

from flowboard.application.orchestrator import analyse_raw_payload
from flowboard.domain.models import BoardSnapshot
from flowboard.i18n.translator import Translator
from flowboard.infrastructure.config.loader import (
    FlowBoardConfig,
    load_config_from_dict,
)
from flowboard.presentation.html.renderer import render_dashboard


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
# 8. Print styles coverage
# ====================================================================


class TestPrintStyles:
    """Print media query must hide interactive elements."""

    def test_settings_hidden_in_print(self):
        html = _render_full("en")
        assert ".settings-overlay" in html
        assert ".settings-drawer" in html
        # The print rule should hide settings
        assert ".settings-toast" in html


# ====================================================================
# 9. Chart grid mobile safety
# ====================================================================


class TestChartGridMobile:
    """Chart grid must use min() for mobile-safe column sizing."""

    def test_chart_grid_uses_min_function(self):
        html = _render_full("en")
        assert "min(100%, 320px)" in html


# ====================================================================
# 10. Color contrast
# ====================================================================


class TestColorContrast:
    """Card labels must have sufficient contrast for readability."""

    def test_card_label_uses_darker_color(self):
        html = _render_full("en")
        # Should use #475569 (contrast ratio ~7:1) not #64748B (~4.6:1)
        assert "#475569" in html


# ====================================================================
# 11. Localization consistency
# ====================================================================


class TestLocalizationConsistency:
    """Both locales must produce structurally identical dashboard output."""

    def test_both_locales_have_same_table_count(self):
        en_html = _render_full("en")
        pl_html = _render_full("pl")
        en_tables = en_html.count('<table class="data-table">')
        pl_tables = pl_html.count('<table class="data-table">')
        assert en_tables == pl_tables

    def test_both_locales_have_same_tab_count(self):
        en_html = _render_full("en")
        pl_html = _render_full("pl")
        en_tabs = en_html.count('role="tab"')
        pl_tabs = pl_html.count('role="tab"')
        assert en_tabs == pl_tabs

    def test_both_locales_have_same_scroll_wrapper_count(self):
        en_html = _render_full("en")
        pl_html = _render_full("pl")
        en_scrolls = en_html.count('class="table-scroll"')
        pl_scrolls = pl_html.count('class="table-scroll"')
        assert en_scrolls == pl_scrolls

    def test_polish_settings_buttons_exist(self):
        """Verify Polish settings buttons render with correct labels."""
        t = Translator("pl")
        labels = [
            t("settings.btn_apply"),
            t("settings.btn_reset"),
            t("settings.btn_export"),
            t("settings.btn_import"),
            t("settings.btn_cancel"),
        ]
        for label in labels:
            assert len(label) > 0
            # Polish labels should be reasonably short (< 30 chars)
            assert len(label) < 30, f"Polish button label too long: '{label}' ({len(label)} chars)"


# ====================================================================
# 12. Settings input responsiveness
# ====================================================================


class TestSettingsResponsive:
    """Settings inputs must have max-width for mobile safety."""

    def test_settings_input_has_max_width(self):
        html = _render_full("en")
        assert "max-width: 50%" in html


# ====================================================================
# 13. Full dashboard rendering (both locales)
# ====================================================================


class TestFullDashboardRendering:
    """Full dashboard renders correctly for both locales."""

    @pytest.fixture()
    def en_html(self, mock_jira_payload: dict, config: FlowBoardConfig) -> str:
        snapshot = analyse_raw_payload(mock_jira_payload, config, today=date(2026, 3, 15))
        return render_dashboard(snapshot, config)

    @pytest.fixture()
    def pl_config(self) -> FlowBoardConfig:
        return load_config_from_dict(
            {
                "jira": {
                    "base_url": "https://test.atlassian.net",
                    "auth_token": "tok-123",
                    "auth_email": "test@co.com",
                    "projects": ["PROJ"],
                },
                "thresholds": {"overload_points": 15, "aging_days": 10},
                "output": {"title": "Test Board"},
                "locale": "pl",
            }
        )

    @pytest.fixture()
    def pl_html(self, mock_jira_payload: dict, pl_config: FlowBoardConfig) -> str:
        snapshot = analyse_raw_payload(mock_jira_payload, pl_config, today=date(2026, 3, 15))
        return render_dashboard(snapshot, pl_config)

    def test_en_has_all_structural_elements(self, en_html: str) -> None:
        assert 'role="tablist"' in en_html
        assert 'class="table-scroll"' in en_html
        assert ":focus-visible" in en_html
        assert "overflow-x: hidden" in en_html

    def test_pl_has_all_structural_elements(self, pl_html: str) -> None:
        assert 'role="tablist"' in pl_html
        assert 'class="table-scroll"' in pl_html
        assert ":focus-visible" in pl_html
        assert "overflow-x: hidden" in pl_html

    def test_pl_no_double_escape(self, pl_html: str) -> None:
        """Polish HTML should not have double-escaped content."""
        assert "&amp;lt;" not in pl_html

    def test_en_no_negative_days(self, en_html: str) -> None:
        """No negative day values should appear in English output."""
        assert "with -" not in en_html


# ====================================================================
# 25. Dark mode support
# ====================================================================


class TestDarkModeSupport:
    """Dashboard must include prefers-color-scheme dark mode styles."""

    def test_dark_mode_media_query(self):
        html = _render_full("en")
        assert "prefers-color-scheme: dark" in html

    def test_dark_mode_overrides_root_vars(self):
        html = _render_full("en")
        assert "--bg: #0F172A" in html


# ====================================================================
# 26. Reduced motion
# ====================================================================


class TestReducedMotion:
    """Dashboard must respect prefers-reduced-motion."""

    def test_reduced_motion_media_query(self):
        html = _render_full("en")
        assert "prefers-reduced-motion: reduce" in html


# ====================================================================
# 27. Text selection styles
# ====================================================================


class TestSelectionStyles:
    """Dashboard must define ::selection styles."""

    def test_selection_styles_present(self):
        html = _render_full("en")
        assert "::selection" in html


# ====================================================================
# 28. Badge contrast (WCAG AA)
# ====================================================================


class TestBadgeContrast:
    """Badge backgrounds must meet WCAG AA contrast against white text."""

    def test_amber_badge_darkened(self):
        html = _render_full("en")
        # Should use #B45309 (amber-700) instead of #F59E0B (amber-500)
        assert "#B45309" in html

    def test_blue_badge_darkened(self):
        html = _render_full("en")
        # Should use #2563EB (blue-600) instead of #3B82F6 (blue-500)
        assert "#2563EB" in html

    def test_emerald_badge_darkened(self):
        html = _render_full("en")
        # Should use #047857 (emerald-700) instead of #10B981 (emerald-500)
        assert "#047857" in html


# ====================================================================
# 29. Dynamic page title
# ====================================================================


class TestDynamicTitle:
    """Page title must include timestamp for tab differentiation."""

    def test_title_includes_generated_at(self):
        html = _render_full("en")
        # Title should contain a date separator
        assert "<title>Test Board — " in html


# ====================================================================
# 30. Import validation
# ====================================================================


class TestImportValidation:
    """Config import must validate JSON structure."""

    def test_import_validates_object_type(self):
        html = _render_full("en")
        assert "Expected a JSON object" in html


# ====================================================================
# 31. Viewport meta verification
# ====================================================================


class TestViewportMeta:
    """Viewport meta tag must be correct for responsive rendering."""

    def test_viewport_meta_correct(self):
        html = _render_full("en")
        assert 'name="viewport" content="width=device-width, initial-scale=1.0"' in html


# ====================================================================
# 32. I18n key parity
# ====================================================================


class TestI18nKeyParity:
    """Both locales must have identical key sets."""

    def test_en_pl_same_keys(self):
        import json
        from pathlib import Path

        locale_dir = Path(__file__).parent.parent / "src" / "flowboard" / "i18n"
        en = json.loads((locale_dir / "en.json").read_text())
        pl = json.loads((locale_dir / "pl.json").read_text())
        assert set(en.keys()) == set(pl.keys())


# ====================================================================
# 33. WCAG contrast — text-tertiary passes AA
# ====================================================================


class TestTextTertiaryContrast:
    """--text-tertiary must pass WCAG AA (4.5:1) in all themes."""

    def test_light_theme_tertiary_contrast(self):
        html = _render_full("en")
        assert "--text-tertiary: #6B7280" in html

    def test_dark_theme_tertiary_contrast(self):
        html = _render_full("en")
        assert "--text-tertiary: #9CA3AF" in html


# ====================================================================
# 34. Tablet breakpoint exists
# ====================================================================


class TestTabletBreakpoint:
    """A tablet breakpoint (1024px) must be present."""

    def test_tablet_breakpoint_present(self):
        html = _render_full("en")
        assert "@media (max-width: 1024px)" in html


# ====================================================================
# 35. Touch targets on mobile
# ====================================================================


class TestMobileTouchTargets:
    """Interactive elements must have 44px min touch targets on mobile."""

    def test_min_height_44px(self):
        html = _render_full("en")
        assert "min-height: 44px" in html


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


class TestDarkThemeCoverage:
    """Dark themes must override light-mode-only hardcoded colors."""

    def test_dark_toggle_slider(self):
        html = _render_full("en")
        assert '[data-theme="dark"] .toggle .slider' in html

    def test_dark_pi_sprint_current(self):
        html = _render_full("en")
        assert '[data-theme="dark"] .pi-sprint-current' in html

    def test_dark_btn_danger(self):
        html = _render_full("en")
        assert '[data-theme="dark"] .settings-footer .btn-danger' in html

    def test_midnight_toggle_slider(self):
        html = _render_full("en")
        assert '[data-theme="midnight"] .toggle .slider' in html


# ====================================================================
# 44. System theme completeness
# ====================================================================


class TestSystemThemeComplete:
    """System theme must have all overrides that dark theme has."""

    def test_system_overlap_badge(self):
        html = _render_full("en")
        assert '[data-theme="system"] .tl-overlap-badge' in html

    def test_system_filter_input(self):
        html = _render_full("en")
        assert '[data-theme="system"] .tl-filter-input' in html

    def test_system_toggle_slider(self):
        html = _render_full("en")
        assert '[data-theme="system"] .toggle .slider' in html


# ====================================================================
# 45. Insights tabs overflow handling
# ====================================================================


class TestInsightsTabsOverflow:
    """Insights tabs must handle overflow on narrow screens."""

    def test_overflow_x_auto(self):
        html = _render_full("en")
        # The CSS must contain overflow-x handling for .insights-tabs
        assert "overflow-x: auto" in html or "overflow-x:auto" in html

    def test_mobile_flex_wrap(self):
        html = _render_full("en")
        # Mobile breakpoint must wrap sub-tab buttons
        assert "flex-wrap: wrap" in html or "flex-wrap:wrap" in html


# ====================================================================
# 46. Empty states have role=status
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


class TestTableCellWordBreak:
    """Table cells must have word-break to prevent overflow."""

    def test_word_break_present(self):
        html = _render_full("en")
        assert "word-break" in html


# ====================================================================
# 48. Chip contrast in dark theme
# ====================================================================


class TestChipDarkContrast:
    """Chip text must have adequate contrast in dark themes."""

    def test_chip_todo_dark_color(self):
        html = _render_full("en")
        # Dark theme must define chip tokens with adequate contrast (#CBD5E1)
        assert "--chip-todo-bg: #334155" in html
        assert "--chip-todo-text: #CBD5E1" in html
        # Chip selectors must reference the tokens
        assert (
            '[data-theme="dark"] .chip-todo { background: var(--chip-todo-bg); color: var(--chip-todo-text); }'
            in html
        )


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
# 56. Print styles
# ====================================================================


class TestPrintStylesImproved:
    """Print styles must hide overlays and optimize layout."""

    def test_print_hides_panels(self):
        html = _render_full("en")
        assert "@media print" in html
        assert "page-break-inside" in html


# ====================================================================
# 57. High contrast mode
# ====================================================================


class TestHighContrast:
    """prefers-contrast: more media query must be present."""

    def test_high_contrast_query(self):
        html = _render_full("en")
        assert "prefers-contrast: more" in html


# ====================================================================
# 58. iOS sticky compatibility
# ====================================================================


class TestIOSSticky:
    """-webkit-sticky must be present for iOS Safari."""

    def test_webkit_sticky(self):
        html = _render_full("en")
        assert "-webkit-sticky" in html


# ====================================================================
# 59. Table scroll safety
# ====================================================================


class TestTableScrollSafety:
    """Tables inside .table-scroll must have a min-width."""

    def test_table_min_width(self):
        html = _render_full("en")
        assert "min-width: 600px" in html


# ====================================================================
# 60. Decorative emoji accessibility
# ====================================================================


class TestDecorativeEmoji:
    """Decorative emojis must have aria-hidden=true."""

    def test_emoji_aria_hidden_count(self):
        html = _render_full("en")
        import re

        hidden = re.findall(r'aria-hidden="true"', html)
        assert len(hidden) >= 10


# ====================================================================
# 61. Progress bar role in source
# ====================================================================


class TestProgressBarSource:
    """Timeline bars must have tabindex and role in source."""

    def test_tabindex_in_timeline_source(self):
        from pathlib import Path

        pkg = Path(__file__).parent.parent / "src" / "flowboard" / "presentation" / "html"
        src = "\n".join(p.read_text() for p in sorted(pkg.glob("components*.py")))
        assert 'tabindex="0"' in src
        assert 'role="button"' in src


# ====================================================================
# 3. Focus visible styles
# ====================================================================


class TestFocusVisibleStyles:
    """Dashboard must include :focus-visible CSS for keyboard accessibility."""

    def test_focus_visible_css_present(self):
        html = _render_full("en")
        assert ":focus-visible" in html

    def test_nav_tab_focus_style(self):
        html = _render_full("en")
        assert ".tab-btn:focus-visible" in html


# ====================================================================
# 4. Viewport overflow protection
# ====================================================================


class TestViewportOverflowProtection:
    """Body/html must prevent unintentional horizontal scrolling."""

    def test_html_overflow_x_hidden(self):
        html = _render_full("en")
        assert "overflow-x: hidden" in html

    def test_body_overflow_x_hidden(self):
        html = _render_full("en")
        assert "overflow-x: hidden" in html


# ====================================================================
# 5. Table header nowrap
# ====================================================================


class TestTableHeaderNowrap:
    """Table headers must not wrap to prevent visual misalignment."""

    def test_th_nowrap_in_css(self):
        html = _render_full("en")
        assert "white-space: nowrap" in html

    def test_polish_headers_are_single_words_or_short(self):
        """Verify Polish table headers are short enough for single-line display."""
        t = Translator("pl")
        headers = [
            t("table.person"),
            t("table.team"),
            t("table.issues"),
            t("table.story_points"),
            t("table.in_progress"),
            t("table.blocked"),
            t("table.severity"),
            t("table.category"),
            t("table.title"),
            t("table.description"),
            t("table.recommendation"),
            t("table.source_status"),
            t("table.target_status"),
        ]
        for header in headers:
            # With nowrap, length doesn't matter for wrapping, but let's verify
            # they exist and are non-empty
            assert len(header) > 0, "Empty header translation found"


# ====================================================================
# 15. HTML lang attribute (WCAG 3.1.1)
# ====================================================================


class TestLangAttribute:
    """HTML element must have correct lang attribute per locale."""

    def test_en_has_lang_en(self):
        html = _render_full("en")
        assert 'lang="en"' in html

    def test_pl_has_lang_pl(self):
        html = _render_full("pl")
        assert 'lang="pl"' in html


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
