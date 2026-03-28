"""Tests for the CSS design system — typography scale tokens, section title borders,
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
# 1. Typography Scale — harmonized 1.125 ratio
# ===================================================================
class TestTypographyScale:
    """Typography tokens use harmonized 1.125-ratio scale."""

    def test_text_sm_is_0_8125(self):
        css = _read("_styles_base.html")
        assert "--text-sm: 0.8125rem;" in css

    def test_text_base_is_0_875(self):
        css = _read("_styles_base.html")
        assert "--text-base: 0.875rem;" in css

    def test_text_md_is_0_9375(self):
        css = _read("_styles_base.html")
        assert "--text-md: 0.9375rem;" in css

    def test_text_lg_is_1(self):
        css = _read("_styles_base.html")
        assert "--text-lg: 1rem;" in css

    def test_text_xl_is_1_125(self):
        css = _read("_styles_base.html")
        assert "--text-xl: 1.125rem;" in css

    def test_scale_comment_indicates_ratio(self):
        css = _read("_styles_base.html")
        assert "1.125 ratio" in css


# ===================================================================
# 2. Section Title Border Weight
# ===================================================================
class TestSectionTitleModernization:
    """Section titles use 1px border (not heavy 2px)."""

    def test_section_title_uses_1px_border(self):
        css = _read("_styles_base.html")
        # After our fix, the section-title rule should have 1px border
        assert "border-bottom: 1px solid var(--border)" in css
        # And should NOT have 2px border anymore
        lines = css.split("\n")
        for line in lines:
            if ".section-title" in line and "border-bottom" in line:
                assert "2px" not in line


# ===================================================================
# 3. Card Hover — subtler translateY(-1px)
# ===================================================================
class TestCardHoverRefinement:
    """Card hover uses translateY(-1px) for subtler micro-interaction."""

    def test_summary_card_hover_1px(self):
        css = _read("_styles_base.html")
        assert "summary-card:hover { transform: translateY(-1px)" in css

    def test_sprint_card_hover_1px(self):
        css = _read("_styles_base.html")
        assert "sprint-card:hover { transform: translateY(-1px)" in css

    def test_pi_sprint_slot_hover_1px(self):
        css = _read("_styles_base.html")
        assert "pi-sprint-slot:hover { transform: translateY(-1px)" in css

    def test_no_2px_hover_in_cards(self):
        """No card component should use translateY(-2px) hover anymore."""
        css = _read("_styles_base.html")
        for line in css.split("\n"):
            if ":hover" in line and "translateY(-2px)" in line:
                # Only timeline bars should still use larger hover
                assert "tl-bar" in line or "chart-card" not in line


# ===================================================================
# 4. Skip-Link Single Definition
# ===================================================================
class TestSkipLinkDeduplication:
    """Skip-link must be defined only in _styles_base.html, not duplicated."""

    def test_skip_link_in_base(self):
        css = _read("_styles_base.html")
        assert ".skip-link" in css
        assert ".skip-link:focus" in css

    def test_no_skip_link_in_features(self):
        """_styles_features.html must NOT contain skip-link rules."""
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
    """Copy button uses --radius-sm design token, not hardcoded 4px."""

    def test_copy_btn_uses_radius_token(self):
        css = _read("_styles_features.html")
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
    """Footer uses CSS custom properties instead of hardcoded px sizes."""

    def test_footer_uses_text_xs_token(self):
        css = _read("_styles_base.html")
        # Find the .app-footer line and check it uses tokens
        for line in css.split("\n"):
            if ".app-footer {" in line and "font-size" in line:
                assert "var(--text-xs" in line, f"Footer should use --text-xs token: {line}"

    def test_footer_copyright_uses_correct_size(self):
        css = _read("_styles_base.html")
        for line in css.split("\n"):
            if ".app-footer-copyright" in line and "font-size" in line:
                assert "13px" in line, f"Footer copyright should use 13px: {line}"

    def test_footer_tools_uses_correct_size(self):
        css = _read("_styles_base.html")
        for line in css.split("\n"):
            if ".app-footer-tools" in line and "font-size" in line:
                assert "12px" in line, f"Footer tools should use 12px: {line}"


# ===================================================================
# 7. Button Padding Standardization
# ===================================================================
class TestButtonPaddingConsistency:
    """Zoom button uses consistent 6px 12px padding, not 5px 10px."""

    def test_zoom_btn_padding_6_12(self):
        css = _read("_styles_base.html")
        for line in css.split("\n"):
            if ".zoom-btn" in line and "padding:" in line and "{" in line:
                assert "6px 12px" in line, f"zoom-btn should use 6px 12px: {line}"

    def test_zoom_btn_uses_text_xs_token(self):
        css = _read("_styles_base.html")
        for line in css.split("\n"):
            if ".zoom-btn" in line and "font-size" in line and "{" in line:
                assert "var(--text-xs" in line, f"zoom-btn should use --text-xs: {line}"


# ===================================================================
# 8. Settings Heading Hierarchy
# ===================================================================
class TestSettingsHeadingHierarchy:
    """Settings section h3 should not have redundant border-bottom."""

    def test_settings_section_h3_no_border(self):
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

    def test_settings_section_h3_weight_600(self):
        css = _read("_styles_base.html")
        # Should use 600 (not 700) for subordinate headings
        in_block = False
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
    """Table headers use sentence case (text-transform: none)."""

    def test_table_th_no_uppercase(self):
        css = _read("_styles_base.html")
        for line in css.split("\n"):
            if ".data-table th {" in line:
                assert "text-transform: none" in line, (
                    f"Table headers should not be uppercase: {line}"
                )


# ===================================================================
# 10. Dark Theme Token Consolidation
# ===================================================================
class TestDarkThemeTokens:
    """Dark theme defines chip/row colors as CSS custom properties."""

    def test_dark_theme_chip_tokens_defined(self):
        css = _read("_styles_features.html")
        assert "--chip-todo-bg: #334155" in css
        assert "--chip-todo-text: #CBD5E1" in css
        assert "--chip-inprogress-bg: #1E3A5F" in css
        assert "--chip-inprogress-text: #60A5FA" in css
        assert "--chip-done-bg: #064E3B" in css
        assert "--chip-done-text: #6EE7B7" in css

    def test_dark_theme_row_warn_token(self):
        css = _read("_styles_features.html")
        assert "--row-warn-bg: #422006" in css
        assert "--row-blocked-bg: #450A0A" in css

    def test_dark_chip_selectors_use_tokens(self):
        css = _read("_styles_features.html")
        assert "var(--chip-todo-bg)" in css
        assert "var(--chip-todo-text)" in css

    def test_dark_table_row_alt_token(self):
        css = _read("_styles_features.html")
        assert "--table-row-alt: rgba(255,255,255,.03)" in css


# ===================================================================
# 11. Wizard Focus Ring Consistency
# ===================================================================
class TestWizardFocusConsistency:
    """Wizard inputs have focus ring matching dashboard inputs."""

    def test_wizard_input_focus_has_box_shadow(self):
        html = _read("first_run.html")
        # Must have box-shadow focus ring like dashboard inputs
        assert "box-shadow: 0 0 0 3px" in html


# ===================================================================
# 12. Full Dashboard Render — Structural Integrity
# ===================================================================
class TestFullDashboardStructure:
    """Full rendered dashboard preserves correct structure after CSS changes."""

    def test_renders_without_error(self):
        html = _render_full("en")
        assert "<!DOCTYPE html>" in html
        assert "</html>" in html

    def test_typography_tokens_in_rendered_output(self):
        html = _render_full("en")
        assert "--text-sm: 0.8125rem" in html
        assert "--text-base: 0.875rem" in html

    def test_section_title_1px_in_rendered(self):
        html = _render_full("en")
        assert "border-bottom: 1px solid var(--border)" in html

    def test_polish_locale_renders(self):
        html = _render_full("pl")
        assert "<!DOCTYPE html>" in html
        assert 'lang="pl"' in html

    def test_dark_theme_tokens_in_rendered(self):
        html = _render_full("en")
        assert "--chip-todo-bg:" in html
        assert "--chip-done-text:" in html


# ===================================================================
# 13. Footer Structure Matches Design System
# ===================================================================
class TestFooterStructure:
    """Footer uses the two-line copyright + tools layout."""

    def test_footer_has_copyright_and_tools(self):
        css = _read("_styles_base.html")
        assert ".app-footer-copyright" in css, "Footer must have copyright line"
        assert ".app-footer-tools" in css, "Footer must have tools line"

    def test_footer_author_has_letter_spacing(self):
        css = _read("_styles_base.html")
        for line in css.split("\n"):
            if ".app-footer-author" in line and "letter-spacing" in line:
                assert "0.5px" in line
                return
        raise AssertionError("Footer author must have letter-spacing: 0.5px")
