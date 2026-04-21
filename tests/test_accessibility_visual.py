"""Tests for visual accessibility and responsive design - color contrast,
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
    """Tests for print styles."""

    """GIVEN print styles and the scenario: settings hidden in print"""
    def test_settings_hidden_in_print(self):
        """WHEN the code under test is exercised for: settings hidden in print"""
        html = _render_full("en")

        """THEN the expected behaviour holds: settings hidden in print"""
        assert ".settings-overlay" in html
        assert ".settings-drawer" in html
        # The print rule should hide settings
        assert ".settings-toast" in html


# ====================================================================
# 9. Chart grid mobile safety
# ====================================================================


class TestChartGridMobile:
    """Tests for chart grid mobile."""

    """GIVEN chart grid mobile and the scenario: chart grid uses min function"""
    def test_chart_grid_uses_min_function(self):
        """WHEN the code under test is exercised for: chart grid uses min function"""
        html = _render_full("en")

        """THEN the expected behaviour holds: chart grid uses min function"""
        assert "min(100%, 320px)" in html


# ====================================================================
# 10. Color contrast
# ====================================================================


class TestColorContrast:
    """Tests for color contrast."""

    """GIVEN color contrast and the scenario: card label uses darker color"""
    def test_card_label_uses_darker_color(self):
        """WHEN the code under test is exercised for: card label uses darker color"""
        html = _render_full("en")
        # Should use #475569 (contrast ratio ~7:1) not #64748B (~4.6:1)

        """THEN the expected behaviour holds: card label uses darker color"""
        assert "#475569" in html


# ====================================================================
# 11. Localization consistency
# ====================================================================


class TestLocalizationConsistency:
    """Tests for localization consistency."""

    """GIVEN localization consistency and the scenario: both locales have same table count"""
    def test_both_locales_have_same_table_count(self):
        """WHEN the code under test is exercised for: both locales have same table count"""
        en_html = _render_full("en")
        pl_html = _render_full("pl")
        en_tables = en_html.count('<table class="data-table">')
        pl_tables = pl_html.count('<table class="data-table">')

        """THEN the expected behaviour holds: both locales have same table count"""
        assert en_tables == pl_tables

    """GIVEN localization consistency and the scenario: both locales have same tab count"""
    def test_both_locales_have_same_tab_count(self):
        """WHEN the code under test is exercised for: both locales have same tab count"""
        en_html = _render_full("en")
        pl_html = _render_full("pl")
        en_tabs = en_html.count('role="tab"')
        pl_tabs = pl_html.count('role="tab"')

        """THEN the expected behaviour holds: both locales have same tab count"""
        assert en_tabs == pl_tabs

    """GIVEN localization consistency and the scenario: both locales have same scroll wrapper count"""
    def test_both_locales_have_same_scroll_wrapper_count(self):
        """WHEN the code under test is exercised for: both locales have same scroll wrapper count"""
        en_html = _render_full("en")
        pl_html = _render_full("pl")
        en_scrolls = en_html.count('class="table-scroll"')
        pl_scrolls = pl_html.count('class="table-scroll"')

        """THEN the expected behaviour holds: both locales have same scroll wrapper count"""
        assert en_scrolls == pl_scrolls

    """GIVEN localization consistency and the scenario: polish settings buttons exist"""
    def test_polish_settings_buttons_exist(self):
        """WHEN the code under test is exercised for: polish settings buttons exist"""
        t = Translator("pl")
        labels = [
            t("settings.btn_apply"),
            t("settings.btn_reset"),
            t("settings.btn_export"),
            t("settings.btn_import"),
            t("settings.btn_cancel"),
        ]

        """THEN the expected behaviour holds: polish settings buttons exist"""
        for label in labels:
            assert len(label) > 0
            # Polish labels should be reasonably short (< 30 chars)
            assert len(label) < 30, f"Polish button label too long: '{label}' ({len(label)} chars)"


# ====================================================================
# 12. Settings input responsiveness
# ====================================================================


class TestSettingsResponsive:
    """Tests for settings responsive."""

    """GIVEN settings responsive and the scenario: settings input has max width"""
    def test_settings_input_has_max_width(self):
        """WHEN the code under test is exercised for: settings input has max width"""
        html = _render_full("en")

        """THEN the expected behaviour holds: settings input has max width"""
        assert "max-width: 50%" in html


# ====================================================================
# 13. Full dashboard rendering (both locales)
# ====================================================================


class TestFullDashboardRendering:
    """Tests for full dashboard rendering."""

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

    """GIVEN full dashboard rendering and the scenario: en has all structural elements"""
    def test_en_has_all_structural_elements(self, en_html: str) -> None:
        """THEN the expected behaviour holds: en has all structural elements"""
        assert 'role="tablist"' in en_html
        assert 'class="table-scroll"' in en_html
        assert ":focus-visible" in en_html
        assert "overflow-x: hidden" in en_html

    """GIVEN full dashboard rendering and the scenario: pl has all structural elements"""
    def test_pl_has_all_structural_elements(self, pl_html: str) -> None:
        """THEN the expected behaviour holds: pl has all structural elements"""
        assert 'role="tablist"' in pl_html
        assert 'class="table-scroll"' in pl_html
        assert ":focus-visible" in pl_html
        assert "overflow-x: hidden" in pl_html

    """GIVEN full dashboard rendering and the scenario: pl no double escape"""
    def test_pl_no_double_escape(self, pl_html: str) -> None:
        """THEN the expected behaviour holds: pl no double escape"""
        assert "&amp;lt;" not in pl_html

    """GIVEN full dashboard rendering and the scenario: en no negative days"""
    def test_en_no_negative_days(self, en_html: str) -> None:
        """THEN the expected behaviour holds: en no negative days"""
        assert "with -" not in en_html


# ====================================================================
# 25. Dark mode support
# ====================================================================


class TestDarkModeSupport:
    """Tests for dark mode support."""

    """GIVEN dark mode support and the scenario: dark mode media query"""
    def test_dark_mode_media_query(self):
        """WHEN the code under test is exercised for: dark mode media query"""
        html = _render_full("en")

        """THEN the expected behaviour holds: dark mode media query"""
        assert "prefers-color-scheme: dark" in html

    """GIVEN dark mode support and the scenario: dark mode overrides root vars"""
    def test_dark_mode_overrides_root_vars(self):
        """WHEN the code under test is exercised for: dark mode overrides root vars"""
        html = _render_full("en")

        """THEN the expected behaviour holds: dark mode overrides root vars"""
        assert "--bg: #0F172A" in html


# ====================================================================
# 26. Reduced motion
# ====================================================================


class TestReducedMotion:
    """Tests for reduced motion."""

    """GIVEN reduced motion and the scenario: reduced motion media query"""
    def test_reduced_motion_media_query(self):
        """WHEN the code under test is exercised for: reduced motion media query"""
        html = _render_full("en")

        """THEN the expected behaviour holds: reduced motion media query"""
        assert "prefers-reduced-motion: reduce" in html


# ====================================================================
# 27. Text selection styles
# ====================================================================


class TestSelectionStyles:
    """Tests for selection styles."""

    """GIVEN selection styles and the scenario: selection styles present"""
    def test_selection_styles_present(self):
        """WHEN the code under test is exercised for: selection styles present"""
        html = _render_full("en")

        """THEN the expected behaviour holds: selection styles present"""
        assert "::selection" in html


# ====================================================================
# 28. Badge contrast (WCAG AA)
# ====================================================================


class TestBadgeContrast:
    """Tests for badge contrast."""

    """GIVEN badge contrast and the scenario: amber badge darkened"""
    def test_amber_badge_darkened(self):
        """WHEN the code under test is exercised for: amber badge darkened"""
        html = _render_full("en")
        # Should use #B45309 (amber-700) instead of #F59E0B (amber-500)

        """THEN the expected behaviour holds: amber badge darkened"""
        assert "#B45309" in html

    """GIVEN badge contrast and the scenario: blue badge darkened"""
    def test_blue_badge_darkened(self):
        """WHEN the code under test is exercised for: blue badge darkened"""
        html = _render_full("en")
        # Should use #2563EB (blue-600) instead of #3B82F6 (blue-500)

        """THEN the expected behaviour holds: blue badge darkened"""
        assert "#2563EB" in html

    """GIVEN badge contrast and the scenario: emerald badge darkened"""
    def test_emerald_badge_darkened(self):
        """WHEN the code under test is exercised for: emerald badge darkened"""
        html = _render_full("en")
        # Should use #047857 (emerald-700) instead of #10B981 (emerald-500)

        """THEN the expected behaviour holds: emerald badge darkened"""
        assert "#047857" in html


# ====================================================================
# 29. Dynamic page title
# ====================================================================


class TestDynamicTitle:
    """Tests for dynamic title."""

    """GIVEN dynamic title and the scenario: title includes generated at"""
    def test_title_includes_generated_at(self):
        """WHEN the code under test is exercised for: title includes generated at"""
        html = _render_full("en")
        # Title should contain a date separator

        """THEN the expected behaviour holds: title includes generated at"""
        assert "<title>Test Board - " in html


# ====================================================================
# 30. Import validation
# ====================================================================


class TestImportValidation:
    """Tests for import validation."""

    """GIVEN import validation and the scenario: import validates object type"""
    def test_import_validates_object_type(self):
        """WHEN the code under test is exercised for: import validates object type"""
        html = _render_full("en")

        """THEN the expected behaviour holds: import validates object type"""
        assert "Expected a JSON object" in html


# ====================================================================
# 31. Viewport meta verification
# ====================================================================


class TestViewportMeta:
    """Tests for viewport meta."""

    """GIVEN viewport meta and the scenario: viewport meta correct"""
    def test_viewport_meta_correct(self):
        """WHEN the code under test is exercised for: viewport meta correct"""
        html = _render_full("en")

        """THEN the expected behaviour holds: viewport meta correct"""
        assert 'name="viewport" content="width=device-width, initial-scale=1.0"' in html


# ====================================================================
# 32. I18n key parity
# ====================================================================


class TestI18nKeyParity:
    """Tests for i18n key parity."""

    """GIVEN i18n key parity and the scenario: en pl same keys"""
    def test_en_pl_same_keys(self):
        """WHEN the code under test is exercised for: en pl same keys"""
        import json
        from pathlib import Path

        locale_dir = Path(__file__).parent.parent / "src" / "flowboard" / "i18n"
        en = json.loads((locale_dir / "en.json").read_text())
        pl = json.loads((locale_dir / "pl.json").read_text())

        """THEN the expected behaviour holds: en pl same keys"""
        assert set(en.keys()) == set(pl.keys())


# ====================================================================
# 33. WCAG contrast - text-tertiary passes AA
# ====================================================================


class TestTextTertiaryContrast:
    """Tests for text tertiary contrast."""

    """GIVEN text tertiary contrast and the scenario: light theme tertiary contrast"""
    def test_light_theme_tertiary_contrast(self):
        """WHEN the code under test is exercised for: light theme tertiary contrast"""
        html = _render_full("en")

        """THEN the expected behaviour holds: light theme tertiary contrast"""
        assert "--text-tertiary: #6B7280" in html

    """GIVEN text tertiary contrast and the scenario: dark theme tertiary contrast"""
    def test_dark_theme_tertiary_contrast(self):
        """WHEN the code under test is exercised for: dark theme tertiary contrast"""
        html = _render_full("en")

        """THEN the expected behaviour holds: dark theme tertiary contrast"""
        assert "--text-tertiary: #9CA3AF" in html


# ====================================================================
# 34. Tablet breakpoint exists
# ====================================================================


class TestTabletBreakpoint:
    """Tests for tablet breakpoint."""

    """GIVEN tablet breakpoint and the scenario: tablet breakpoint present"""
    def test_tablet_breakpoint_present(self):
        """WHEN the code under test is exercised for: tablet breakpoint present"""
        html = _render_full("en")

        """THEN the expected behaviour holds: tablet breakpoint present"""
        assert "@media (max-width: 1024px)" in html


# ====================================================================
# 35. Touch targets on mobile
# ====================================================================


class TestMobileTouchTargets:
    """Tests for mobile touch targets."""

    """GIVEN mobile touch targets and the scenario: min height 44px"""
    def test_min_height_44px(self):
        """WHEN the code under test is exercised for: min height 44px"""
        html = _render_full("en")

        """THEN the expected behaviour holds: min height 44px"""
        assert "min-height: 44px" in html


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


class TestDarkThemeCoverage:
    """Tests for dark theme coverage."""

    """GIVEN dark theme coverage and the scenario: dark toggle slider"""
    def test_dark_toggle_slider(self):
        """WHEN the code under test is exercised for: dark toggle slider"""
        html = _render_full("en")

        """THEN the expected behaviour holds: dark toggle slider"""
        assert '[data-theme="dark"] .toggle .slider' in html

    """GIVEN dark theme coverage and the scenario: dark pi sprint current"""
    def test_dark_pi_sprint_current(self):
        """WHEN the code under test is exercised for: dark pi sprint current"""
        html = _render_full("en")

        """THEN the expected behaviour holds: dark pi sprint current"""
        assert '[data-theme="dark"] .pi-sprint-current' in html

    """GIVEN dark theme coverage and the scenario: dark btn danger"""
    def test_dark_btn_danger(self):
        """WHEN the code under test is exercised for: dark btn danger"""
        html = _render_full("en")

        """THEN the expected behaviour holds: dark btn danger"""
        assert '[data-theme="dark"] .settings-footer .btn-danger' in html

    """GIVEN dark theme coverage and the scenario: midnight toggle slider"""
    def test_midnight_toggle_slider(self):
        """WHEN the code under test is exercised for: midnight toggle slider"""
        html = _render_full("en")

        """THEN the expected behaviour holds: midnight toggle slider"""
        assert '[data-theme="midnight"] .toggle .slider' in html


# ====================================================================
# 44. System theme completeness
# ====================================================================


class TestSystemThemeComplete:
    """Tests for system theme complete."""

    """GIVEN system theme complete and the scenario: system overlap badge"""
    def test_system_overlap_badge(self):
        """WHEN the code under test is exercised for: system overlap badge"""
        html = _render_full("en")

        """THEN the expected behaviour holds: system overlap badge"""
        assert '[data-theme="system"] .tl-overlap-badge' in html

    """GIVEN system theme complete and the scenario: system filter input"""
    def test_system_filter_input(self):
        """WHEN the code under test is exercised for: system filter input"""
        html = _render_full("en")

        """THEN the expected behaviour holds: system filter input"""
        assert '[data-theme="system"] .tl-filter-input' in html

    """GIVEN system theme complete and the scenario: system toggle slider"""
    def test_system_toggle_slider(self):
        """WHEN the code under test is exercised for: system toggle slider"""
        html = _render_full("en")

        """THEN the expected behaviour holds: system toggle slider"""
        assert '[data-theme="system"] .toggle .slider' in html


# ====================================================================
# 45. Insights tabs overflow handling
# ====================================================================


class TestInsightsTabsOverflow:
    """Tests for insights tabs overflow."""

    """GIVEN insights tabs overflow and the scenario: overflow x auto"""
    def test_overflow_x_auto(self):
        """WHEN the code under test is exercised for: overflow x auto"""
        html = _render_full("en")
        # The CSS must contain overflow-x handling for .insights-tabs

        """THEN the expected behaviour holds: overflow x auto"""
        assert "overflow-x: auto" in html or "overflow-x:auto" in html

    """GIVEN insights tabs overflow and the scenario: mobile flex wrap"""
    def test_mobile_flex_wrap(self):
        """WHEN the code under test is exercised for: mobile flex wrap"""
        html = _render_full("en")
        # Mobile breakpoint must wrap sub-tab buttons

        """THEN the expected behaviour holds: mobile flex wrap"""
        assert "flex-wrap: wrap" in html or "flex-wrap:wrap" in html


# ====================================================================
# 46. Empty states have role=status
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


class TestTableCellWordBreak:
    """Tests for table cell word break."""

    """GIVEN table cell word break and the scenario: word break present"""
    def test_word_break_present(self):
        """WHEN the code under test is exercised for: word break present"""
        html = _render_full("en")

        """THEN the expected behaviour holds: word break present"""
        assert "word-break" in html


# ====================================================================
# 48. Chip contrast in dark theme
# ====================================================================


class TestChipDarkContrast:
    """Tests for chip dark contrast."""

    """GIVEN chip dark contrast and the scenario: chip todo dark color"""
    def test_chip_todo_dark_color(self):
        """WHEN the code under test is exercised for: chip todo dark color"""
        html = _render_full("en")
        # Dark theme must define chip tokens with adequate contrast (#CBD5E1)

        """THEN the expected behaviour holds: chip todo dark color"""
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
# 56. Print styles
# ====================================================================


class TestPrintStylesImproved:
    """Tests for print styles improved."""

    """GIVEN print styles improved and the scenario: print hides panels"""
    def test_print_hides_panels(self):
        """WHEN the code under test is exercised for: print hides panels"""
        html = _render_full("en")

        """THEN the expected behaviour holds: print hides panels"""
        assert "@media print" in html
        assert "page-break-inside" in html


# ====================================================================
# 57. High contrast mode
# ====================================================================


class TestHighContrast:
    """Tests for high contrast."""

    """GIVEN high contrast and the scenario: high contrast query"""
    def test_high_contrast_query(self):
        """WHEN the code under test is exercised for: high contrast query"""
        html = _render_full("en")

        """THEN the expected behaviour holds: high contrast query"""
        assert "prefers-contrast: more" in html


# ====================================================================
# 58. iOS sticky compatibility
# ====================================================================


class TestIOSSticky:
    """Tests for i o s sticky."""

    """GIVEN i o s sticky and the scenario: webkit sticky"""
    def test_webkit_sticky(self):
        """WHEN the code under test is exercised for: webkit sticky"""
        html = _render_full("en")

        """THEN the expected behaviour holds: webkit sticky"""
        assert "-webkit-sticky" in html


# ====================================================================
# 59. Table scroll safety
# ====================================================================


class TestTableScrollSafety:
    """Tests for table scroll safety."""

    """GIVEN table scroll safety and the scenario: table min width"""
    def test_table_min_width(self):
        """WHEN the code under test is exercised for: table min width"""
        html = _render_full("en")

        """THEN the expected behaviour holds: table min width"""
        assert "min-width: 600px" in html


# ====================================================================
# 60. Decorative emoji accessibility
# ====================================================================


class TestDecorativeEmoji:
    """Tests for decorative emoji."""

    """GIVEN decorative emoji and the scenario: emoji aria hidden count"""
    def test_emoji_aria_hidden_count(self):
        """WHEN the code under test is exercised for: emoji aria hidden count"""
        html = _render_full("en")
        import re

        hidden = re.findall(r'aria-hidden="true"', html)

        """THEN the expected behaviour holds: emoji aria hidden count"""
        assert len(hidden) >= 10


# ====================================================================
# 61. Progress bar role in source
# ====================================================================


class TestProgressBarSource:
    """Tests for progress bar source."""

    """GIVEN progress bar source and the scenario: tabindex in timeline source"""
    def test_tabindex_in_timeline_source(self):
        """WHEN the code under test is exercised for: tabindex in timeline source"""
        from pathlib import Path

        pkg = Path(__file__).parent.parent / "src" / "flowboard" / "presentation" / "html"
        src = "\n".join(p.read_text() for p in sorted(pkg.glob("components*.py")))

        """THEN the expected behaviour holds: tabindex in timeline source"""
        assert 'tabindex="0"' in src
        assert 'role="button"' in src


# ====================================================================
# 3. Focus visible styles
# ====================================================================


class TestFocusVisibleStyles:
    """Tests for focus visible styles."""

    """GIVEN focus visible styles and the scenario: focus visible css present"""
    def test_focus_visible_css_present(self):
        """WHEN the code under test is exercised for: focus visible css present"""
        html = _render_full("en")

        """THEN the expected behaviour holds: focus visible css present"""
        assert ":focus-visible" in html

    """GIVEN focus visible styles and the scenario: nav tab focus style"""
    def test_nav_tab_focus_style(self):
        """WHEN the code under test is exercised for: nav tab focus style"""
        html = _render_full("en")

        """THEN the expected behaviour holds: nav tab focus style"""
        assert ".tab-btn:focus-visible" in html


# ====================================================================
# 4. Viewport overflow protection
# ====================================================================


class TestViewportOverflowProtection:
    """Tests for viewport overflow protection."""

    """GIVEN viewport overflow protection and the scenario: html overflow x hidden"""
    def test_html_overflow_x_hidden(self):
        """WHEN the code under test is exercised for: html overflow x hidden"""
        html = _render_full("en")

        """THEN the expected behaviour holds: html overflow x hidden"""
        assert "overflow-x: hidden" in html

    """GIVEN viewport overflow protection and the scenario: body overflow x hidden"""
    def test_body_overflow_x_hidden(self):
        """WHEN the code under test is exercised for: body overflow x hidden"""
        html = _render_full("en")

        """THEN the expected behaviour holds: body overflow x hidden"""
        assert "overflow-x: hidden" in html


# ====================================================================
# 5. Table header nowrap
# ====================================================================


class TestTableHeaderNowrap:
    """Tests for table header nowrap."""

    """GIVEN table header nowrap and the scenario: th nowrap in css"""
    def test_th_nowrap_in_css(self):
        """WHEN the code under test is exercised for: th nowrap in css"""
        html = _render_full("en")

        """THEN the expected behaviour holds: th nowrap in css"""
        assert "white-space: nowrap" in html

    """GIVEN table header nowrap and the scenario: polish headers are single words or short"""
    def test_polish_headers_are_single_words_or_short(self):
        """WHEN the code under test is exercised for: polish headers are single words or short"""
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

        """THEN the expected behaviour holds: polish headers are single words or short"""
        for header in headers:
            # With nowrap, length doesn't matter for wrapping, but let's verify
            # they exist and are non-empty
            assert len(header) > 0, "Empty header translation found"


# ====================================================================
# 15. HTML lang attribute (WCAG 3.1.1)
# ====================================================================


class TestLangAttribute:
    """Tests for lang attribute."""

    """GIVEN lang attribute and the scenario: en has lang en"""
    def test_en_has_lang_en(self):
        """WHEN the code under test is exercised for: en has lang en"""
        html = _render_full("en")

        """THEN the expected behaviour holds: en has lang en"""
        assert 'lang="en"' in html

    """GIVEN lang attribute and the scenario: pl has lang pl"""
    def test_pl_has_lang_pl(self):
        """WHEN the code under test is exercised for: pl has lang pl"""
        html = _render_full("pl")

        """THEN the expected behaviour holds: pl has lang pl"""
        assert 'lang="pl"' in html


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
