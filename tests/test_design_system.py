"""Tests for the CSS design system - typography scale tokens, section title borders,
card hover refinements, skip-link deduplication, copy button radius, footer
tokenization, button padding, settings heading hierarchy, table header styling,
dark theme tokens, wizard focus consistency, and full dashboard structure.
"""

from pathlib import Path

import pytest

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


# ---------------------------------------------------------------------------
# Helper: render full dashboard HTML for structural checks
# ---------------------------------------------------------------------------
def _render_full(locale: str = "en") -> str:
    """Render a complete dashboard and return HTML string."""
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
# 1. Typography Scale - harmonized 1.125 ratio
# ===================================================================
class TestTypographyScale:
    """Tests for typography scale."""

    """GIVEN typography scale and the scenario: text sm is 0 8125"""
    def test_text_sm_is_0_8125(self):
        """WHEN the code under test is exercised for: text sm is 0 8125"""
        css = _read("_styles_base.html")

        """THEN the expected behaviour holds: text sm is 0 8125"""
        assert "--text-sm: 0.8125rem;" in css

    """GIVEN typography scale and the scenario: text base is 0 875"""
    def test_text_base_is_0_875(self):
        """WHEN the code under test is exercised for: text base is 0 875"""
        css = _read("_styles_base.html")

        """THEN the expected behaviour holds: text base is 0 875"""
        assert "--text-base: 0.875rem;" in css

    """GIVEN typography scale and the scenario: text md is 0 9375"""
    def test_text_md_is_0_9375(self):
        """WHEN the code under test is exercised for: text md is 0 9375"""
        css = _read("_styles_base.html")

        """THEN the expected behaviour holds: text md is 0 9375"""
        assert "--text-md: 0.9375rem;" in css

    """GIVEN typography scale and the scenario: text lg is 1"""
    def test_text_lg_is_1(self):
        """WHEN the code under test is exercised for: text lg is 1"""
        css = _read("_styles_base.html")

        """THEN the expected behaviour holds: text lg is 1"""
        assert "--text-lg: 1rem;" in css

    """GIVEN typography scale and the scenario: text xl is 1 125"""
    def test_text_xl_is_1_125(self):
        """WHEN the code under test is exercised for: text xl is 1 125"""
        css = _read("_styles_base.html")

        """THEN the expected behaviour holds: text xl is 1 125"""
        assert "--text-xl: 1.125rem;" in css

    """GIVEN typography scale and the scenario: scale comment indicates ratio"""
    def test_scale_comment_indicates_ratio(self):
        """WHEN the code under test is exercised for: scale comment indicates ratio"""
        css = _read("_styles_base.html")

        """THEN the expected behaviour holds: scale comment indicates ratio"""
        assert "1.125 ratio" in css


# ===================================================================
# 2. Section Title Border Weight
# ===================================================================
class TestSectionTitleModernization:
    """Tests for section title modernization."""

    """GIVEN section title modernization and the scenario: section title uses 1px border"""
    def test_section_title_uses_1px_border(self):
        """WHEN the code under test is exercised for: section title uses 1px border"""
        css = _read("_styles_base.html")
        # After our fix, the section-title rule should have 1px border

        """THEN the expected behaviour holds: section title uses 1px border"""
        assert "border-bottom: 1px solid var(--border)" in css
        # And should NOT have 2px border anymore
        lines = css.split("\n")
        for line in lines:
            if ".section-title" in line and "border-bottom" in line:
                assert "2px" not in line


# ===================================================================
# 3. Card Hover - subtler translateY(-1px)
# ===================================================================
class TestCardHoverRefinement:
    """Tests for card hover refinement."""

    """GIVEN card hover refinement and the scenario: summary card hover 1px"""
    def test_summary_card_hover_1px(self):
        """WHEN the code under test is exercised for: summary card hover 1px"""
        css = _read("_styles_base.html")

        """THEN the expected behaviour holds: summary card hover 1px"""
        assert "summary-card:hover { transform: translateY(-1px)" in css

    """GIVEN card hover refinement and the scenario: sprint card hover 1px"""
    def test_sprint_card_hover_1px(self):
        """WHEN the code under test is exercised for: sprint card hover 1px"""
        css = _read("_styles_base.html")

        """THEN the expected behaviour holds: sprint card hover 1px"""
        assert "sprint-card:hover { transform: translateY(-1px)" in css

    """GIVEN card hover refinement and the scenario: pi sprint slot hover 1px"""
    def test_pi_sprint_slot_hover_1px(self):
        """WHEN the code under test is exercised for: pi sprint slot hover 1px"""
        css = _read("_styles_base.html")

        """THEN the expected behaviour holds: pi sprint slot hover 1px"""
        assert "pi-sprint-slot:hover { transform: translateY(-1px)" in css

    """GIVEN card hover refinement and the scenario: no 2px hover in cards"""
    def test_no_2px_hover_in_cards(self):
        """WHEN the code under test is exercised for: no 2px hover in cards"""
        css = _read("_styles_base.html")

        """THEN the expected behaviour holds: no 2px hover in cards"""
        for line in css.split("\n"):
            if ":hover" in line and "translateY(-2px)" in line:
                # Only timeline bars should still use larger hover
                assert "tl-bar" in line or "chart-card" not in line


# ===================================================================
# 4. Skip-Link Single Definition
# ===================================================================
class TestSkipLinkDeduplication:
    """Tests for skip link deduplication."""

    """GIVEN skip link deduplication and the scenario: skip link in base"""
    def test_skip_link_in_base(self):
        """WHEN the code under test is exercised for: skip link in base"""
        css = _read("_styles_base.html")

        """THEN the expected behaviour holds: skip link in base"""
        assert ".skip-link" in css
        assert ".skip-link:focus" in css

    """GIVEN skip link deduplication and the scenario: no skip link in features"""
    def test_no_skip_link_in_features(self):
        """WHEN the code under test is exercised for: no skip link in features"""
        css = _read("_styles_features.html")
        # Should not have a .skip-link { ... } definition
        lines = css.split("\n")
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(".skip-link") and "{" in stripped:
                pytest.fail(f"Duplicate skip-link rule found in _styles_features.html: {stripped}")


# ===================================================================
# 5. Copy Button Radius Token
# ===================================================================
class TestCopyButtonRadius:
    """Tests for copy button radius."""

    """GIVEN copy button radius and the scenario: copy btn uses radius token"""
    def test_copy_btn_uses_radius_token(self):
        """WHEN the code under test is exercised for: copy btn uses radius token"""
        css = _read("_styles_features.html")

        """THEN the expected behaviour holds: copy btn uses radius token"""
        assert "copy-btn" in css
        # Must use the token
        lines = css.split("\n")
        for line in lines:
            if ".copy-btn" in line and "border-radius" in line:
                assert "var(--radius-sm" in line, f"copy-btn should use --radius-sm token: {line}"


# ===================================================================
# 6. Footer Typography Tokens
# ===================================================================
class TestFooterTokenization:
    """Tests for footer tokenization."""

    """GIVEN footer tokenization and the scenario: footer uses text xs token"""
    def test_footer_uses_text_xs_token(self):
        """WHEN the code under test is exercised for: footer uses text xs token"""
        css = _read("_styles_base.html")
        # Find the .app-footer line and check it uses tokens

        """THEN the expected behaviour holds: footer uses text xs token"""
        for line in css.split("\n"):
            if ".app-footer {" in line and "font-size" in line:
                assert "var(--text-xs" in line, f"Footer should use --text-xs token: {line}"

    """GIVEN footer tokenization and the scenario: footer copyright uses correct size"""
    def test_footer_copyright_uses_correct_size(self):
        """WHEN the code under test is exercised for: footer copyright uses correct size"""
        css = _read("_styles_base.html")

        """THEN the expected behaviour holds: footer copyright uses correct size"""
        for line in css.split("\n"):
            if ".app-footer-copyright" in line and "font-size" in line:
                assert "13px" in line, f"Footer copyright should use 13px: {line}"

    """GIVEN footer tokenization and the scenario: footer tools uses correct size"""
    def test_footer_tools_uses_correct_size(self):
        """WHEN the code under test is exercised for: footer tools uses correct size"""
        css = _read("_styles_base.html")

        """THEN the expected behaviour holds: footer tools uses correct size"""
        for line in css.split("\n"):
            if ".app-footer-tools" in line and "font-size" in line:
                assert "12px" in line, f"Footer tools should use 12px: {line}"


# ===================================================================
# 7. Button Padding Standardization
# ===================================================================
class TestButtonPaddingConsistency:
    """Tests for button padding consistency."""

    """GIVEN button padding consistency and the scenario: zoom btn padding 6 12"""
    def test_zoom_btn_padding_6_12(self):
        """WHEN the code under test is exercised for: zoom btn padding 6 12"""
        css = _read("_styles_base.html")

        """THEN the expected behaviour holds: zoom btn padding 6 12"""
        for line in css.split("\n"):
            if ".zoom-btn" in line and "padding:" in line and "{" in line:
                assert "6px 12px" in line, f"zoom-btn should use 6px 12px: {line}"

    """GIVEN button padding consistency and the scenario: zoom btn uses text xs token"""
    def test_zoom_btn_uses_text_xs_token(self):
        """WHEN the code under test is exercised for: zoom btn uses text xs token"""
        css = _read("_styles_base.html")

        """THEN the expected behaviour holds: zoom btn uses text xs token"""
        for line in css.split("\n"):
            if ".zoom-btn" in line and "font-size" in line and "{" in line:
                assert "var(--text-xs" in line, f"zoom-btn should use --text-xs: {line}"


# ===================================================================
# 8. Settings Heading Hierarchy
# ===================================================================
class TestSettingsHeadingHierarchy:
    """Tests for settings heading hierarchy."""

    """GIVEN settings heading hierarchy and the scenario: settings section h3 no border"""
    def test_settings_section_h3_no_border(self):
        """WHEN the code under test is exercised for: settings section h3 no border"""
        css = _read("_styles_base.html")
        in_settings_section_h3 = False
        for line in css.split("\n"):
            if ".settings-section h3" in line:
                in_settings_section_h3 = True
            if in_settings_section_h3:
                if "border-bottom" in line:
                    pytest.fail("settings-section h3 should not have border-bottom")
                if "}" in line:
                    break

    """GIVEN settings heading hierarchy and the scenario: settings section h3 weight 600"""
    def test_settings_section_h3_weight_600(self):
        """WHEN the code under test is exercised for: settings section h3 weight 600"""
        css = _read("_styles_base.html")
        # Should use 600 (not 700) for subordinate headings
        in_block = False

        """THEN the expected behaviour holds: settings section h3 weight 600"""
        for line in css.split("\n"):
            if ".settings-section h3" in line:
                in_block = True
            if in_block:
                if "font-weight" in line:
                    assert "600" in line
                    break
                if "}" in line:
                    break


# ===================================================================
# 9. Table Header Modernization
# ===================================================================
class TestTableHeaderModernization:
    """Tests for table header modernization."""

    """GIVEN table header modernization and the scenario: table th no uppercase"""
    def test_table_th_no_uppercase(self):
        """WHEN the code under test is exercised for: table th no uppercase"""
        css = _read("_styles_base.html")

        """THEN the expected behaviour holds: table th no uppercase"""
        for line in css.split("\n"):
            if ".data-table th {" in line:
                assert "text-transform: none" in line, (
                    f"Table headers should not be uppercase: {line}"
                )


# ===================================================================
# 10. Dark Theme Token Consolidation
# ===================================================================
class TestDarkThemeTokens:
    """Tests for dark theme tokens."""

    """GIVEN dark theme tokens and the scenario: dark theme chip tokens defined"""
    def test_dark_theme_chip_tokens_defined(self):
        """WHEN the code under test is exercised for: dark theme chip tokens defined"""
        css = _read("_styles_features.html")

        """THEN the expected behaviour holds: dark theme chip tokens defined"""
        assert "--chip-todo-bg: #334155" in css
        assert "--chip-todo-text: #CBD5E1" in css
        assert "--chip-inprogress-bg: #1E3A5F" in css
        assert "--chip-inprogress-text: #60A5FA" in css
        assert "--chip-done-bg: #064E3B" in css
        assert "--chip-done-text: #6EE7B7" in css

    """GIVEN dark theme tokens and the scenario: dark theme row warn token"""
    def test_dark_theme_row_warn_token(self):
        """WHEN the code under test is exercised for: dark theme row warn token"""
        css = _read("_styles_features.html")

        """THEN the expected behaviour holds: dark theme row warn token"""
        assert "--row-warn-bg: #422006" in css
        assert "--row-blocked-bg: #450A0A" in css

    """GIVEN dark theme tokens and the scenario: dark chip selectors use tokens"""
    def test_dark_chip_selectors_use_tokens(self):
        """WHEN the code under test is exercised for: dark chip selectors use tokens"""
        css = _read("_styles_features.html")

        """THEN the expected behaviour holds: dark chip selectors use tokens"""
        assert "var(--chip-todo-bg)" in css
        assert "var(--chip-todo-text)" in css

    """GIVEN dark theme tokens and the scenario: dark table row alt token"""
    def test_dark_table_row_alt_token(self):
        """WHEN the code under test is exercised for: dark table row alt token"""
        css = _read("_styles_features.html")

        """THEN the expected behaviour holds: dark table row alt token"""
        assert "--table-row-alt: rgba(255,255,255,.03)" in css


# ===================================================================
# 11. Wizard Focus Ring Consistency
# ===================================================================
class TestWizardFocusConsistency:
    """Tests for wizard focus consistency."""

    """GIVEN wizard focus consistency and the scenario: wizard input focus has box shadow"""
    def test_wizard_input_focus_has_box_shadow(self):
        """WHEN the code under test is exercised for: wizard input focus has box shadow"""
        html = _read("first_run.html")
        # Must have box-shadow focus ring like dashboard inputs

        """THEN the expected behaviour holds: wizard input focus has box shadow"""
        assert "box-shadow: 0 0 0 3px" in html


# ===================================================================
# 12. Full Dashboard Render - Structural Integrity
# ===================================================================
class TestFullDashboardStructure:
    """Tests for full dashboard structure."""

    """GIVEN full dashboard structure and the scenario: renders without error"""
    def test_renders_without_error(self):
        """WHEN the code under test is exercised for: renders without error"""
        html = _render_full("en")

        """THEN the expected behaviour holds: renders without error"""
        assert "<!DOCTYPE html>" in html
        assert "</html>" in html

    """GIVEN full dashboard structure and the scenario: typography tokens in rendered output"""
    def test_typography_tokens_in_rendered_output(self):
        """WHEN the code under test is exercised for: typography tokens in rendered output"""
        html = _render_full("en")

        """THEN the expected behaviour holds: typography tokens in rendered output"""
        assert "--text-sm: 0.8125rem" in html
        assert "--text-base: 0.875rem" in html

    """GIVEN full dashboard structure and the scenario: section title 1px in rendered"""
    def test_section_title_1px_in_rendered(self):
        """WHEN the code under test is exercised for: section title 1px in rendered"""
        html = _render_full("en")

        """THEN the expected behaviour holds: section title 1px in rendered"""
        assert "border-bottom: 1px solid var(--border)" in html

    """GIVEN full dashboard structure and the scenario: polish locale renders"""
    def test_polish_locale_renders(self):
        """WHEN the code under test is exercised for: polish locale renders"""
        html = _render_full("pl")

        """THEN the expected behaviour holds: polish locale renders"""
        assert "<!DOCTYPE html>" in html
        assert 'lang="pl"' in html

    """GIVEN full dashboard structure and the scenario: dark theme tokens in rendered"""
    def test_dark_theme_tokens_in_rendered(self):
        """WHEN the code under test is exercised for: dark theme tokens in rendered"""
        html = _render_full("en")

        """THEN the expected behaviour holds: dark theme tokens in rendered"""
        assert "--chip-todo-bg:" in html
        assert "--chip-done-text:" in html


# ===================================================================
# 13. Footer Structure Matches Design System
# ===================================================================
class TestFooterStructure:
    """Tests for footer structure."""

    """GIVEN footer structure and the scenario: footer has copyright and tools"""
    def test_footer_has_copyright_and_tools(self):
        """WHEN the code under test is exercised for: footer has copyright and tools"""
        css = _read("_styles_base.html")

        """THEN the expected behaviour holds: footer has copyright and tools"""
        assert ".app-footer-copyright" in css, "Footer must have copyright line"
        assert ".app-footer-tools" in css, "Footer must have tools line"

    """GIVEN footer structure and the scenario: footer author has letter spacing"""
    def test_footer_author_has_letter_spacing(self):
        """WHEN the code under test is exercised for: footer author has letter spacing"""
        css = _read("_styles_base.html")

        """THEN the expected behaviour holds: footer author has letter spacing"""
        for line in css.split("\n"):
            if ".app-footer-author" in line and "letter-spacing" in line:
                assert "0.5px" in line
                return
        raise AssertionError("Footer author must have letter-spacing: 0.5px")
