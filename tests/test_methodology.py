"""Methodology tests - configuration, presets, integration, i18n, detection, adaptive rendering."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from flowboard.domain.models import BoardSnapshot, Issue, Person
from flowboard.i18n.translator import Translator
from flowboard.infrastructure.config.config_models import SUPPORTED_METHODOLOGIES
from flowboard.infrastructure.config.loader import (
    config_to_dict,
    load_config_from_dict,
)
from flowboard.infrastructure.config.presets import apply_preset, get_preset
from flowboard.presentation.html.renderer import render_dashboard
from flowboard.shared.types import IssueStatus, StatusCategory

# ===================================================================
# Helpers
# ===================================================================


def _make_config(methodology: str = "scrum", locale: str = "en", **overrides):
    raw = {
        "jira": {"base_url": "https://test.atlassian.net"},
        "output": {"title": "Test Board"},
        "methodology": methodology,
        "locale": locale,
        **overrides,
    }
    return load_config_from_dict(raw)


def _make_issue(
    key: str,
    status_cat: StatusCategory = StatusCategory.TODO,
    created_days_ago: int = 10,
    resolved_days_ago: int | None = None,
    assignee_name: str = "Dev A",
    team: str = "Alpha",
    points: float = 3.0,
) -> Issue:
    now = datetime.now(tz=UTC)
    created = now - timedelta(days=created_days_ago)
    resolved = (now - timedelta(days=resolved_days_ago)) if resolved_days_ago is not None else None
    status = IssueStatus.DONE if status_cat == StatusCategory.DONE else IssueStatus.IN_PROGRESS
    return Issue(
        key=key,
        summary=f"Test issue {key}",
        status=status,
        status_category=status_cat,
        created=created,
        resolved=resolved,
        assignee=Person(
            account_id=f"acc-{assignee_name.lower().replace(' ', '-')}",
            display_name=assignee_name,
            team=team,
        ),
        story_points=points,
    )


def _render(methodology: str = "scrum", locale: str = "en") -> str:
    cfg = _make_config(methodology=methodology, locale=locale)
    snap = BoardSnapshot(title="Test Board")
    return render_dashboard(snap, cfg)


# ===================================================================
# Phase 1: Config & Presets
# ===================================================================


class TestMethodologyConfig:
    """GIVEN methodology config and the scenario: default methodology is scrum"""
    def test_default_methodology_is_scrum(self):
        """WHEN the code under test is exercised for: default methodology is scrum"""
        cfg = _make_config()

        """THEN the expected behaviour holds: default methodology is scrum"""
        assert cfg.methodology == "scrum"

    """GIVEN methodology config and the scenario: kanban methodology"""
    def test_kanban_methodology(self):
        """WHEN the code under test is exercised for: kanban methodology"""
        cfg = _make_config("kanban")

        """THEN the expected behaviour holds: kanban methodology"""
        assert cfg.methodology == "kanban"

    """GIVEN methodology config and the scenario: waterfall methodology"""
    def test_waterfall_methodology(self):
        """WHEN the code under test is exercised for: waterfall methodology"""
        cfg = _make_config("waterfall")

        """THEN the expected behaviour holds: waterfall methodology"""
        assert cfg.methodology == "waterfall"

    """GIVEN methodology config and the scenario: hybrid methodology"""
    def test_hybrid_methodology(self):
        """WHEN the code under test is exercised for: hybrid methodology"""
        cfg = _make_config("hybrid")

        """THEN the expected behaviour holds: hybrid methodology"""
        assert cfg.methodology == "hybrid"

    """GIVEN methodology config and the scenario: custom methodology"""
    def test_custom_methodology(self):
        """WHEN the code under test is exercised for: custom methodology"""
        cfg = _make_config("custom")

        """THEN the expected behaviour holds: custom methodology"""
        assert cfg.methodology == "custom"

    """GIVEN methodology config and the scenario: invalid methodology rejected by schema"""
    def test_invalid_methodology_rejected_by_schema(self):
        """WHEN the code under test is exercised for: invalid methodology rejected by schema"""
        from flowboard.infrastructure.config.validator import ConfigValidationError

        with pytest.raises(ConfigValidationError):
            _make_config("agile")

    """GIVEN methodology config and the scenario: methodology in config to dict"""
    def test_methodology_in_config_to_dict(self):
        """WHEN the code under test is exercised for: methodology in config to dict"""
        cfg = _make_config("kanban")
        d = config_to_dict(cfg)

        """THEN the expected behaviour holds: methodology in config to dict"""
        assert d["methodology"] == "kanban"

    """GIVEN methodology config and the scenario: supported methodologies constant"""
    def test_supported_methodologies_constant(self):
        """THEN the expected behaviour holds: supported methodologies constant"""
        assert {"scrum", "kanban", "waterfall", "hybrid", "custom"} == SUPPORTED_METHODOLOGIES


class TestPresets:
    """GIVEN presets and the scenario: scrum preset has sprints tab"""
    def test_scrum_preset_has_sprints_tab(self):
        """WHEN the code under test is exercised for: scrum preset has sprints tab"""
        preset = get_preset("scrum")
        tabs = preset["dashboard"]["tabs"]["visible"]

        """THEN the expected behaviour holds: scrum preset has sprints tab"""
        assert "sprints" in tabs
        assert "flow" not in tabs

    """GIVEN presets and the scenario: kanban preset has flow tab"""
    def test_kanban_preset_has_flow_tab(self):
        """WHEN the code under test is exercised for: kanban preset has flow tab"""
        preset = get_preset("kanban")
        tabs = preset["dashboard"]["tabs"]["visible"]

        """THEN the expected behaviour holds: kanban preset has flow tab"""
        assert "flow" in tabs
        assert "sprints" not in tabs

    """GIVEN presets and the scenario: waterfall preset has phases tab"""
    def test_waterfall_preset_has_phases_tab(self):
        """WHEN the code under test is exercised for: waterfall preset has phases tab"""
        preset = get_preset("waterfall")
        tabs = preset["dashboard"]["tabs"]["visible"]

        """THEN the expected behaviour holds: waterfall preset has phases tab"""
        assert "phases" in tabs
        assert "sprints" not in tabs

    """GIVEN presets and the scenario: hybrid preset has both"""
    def test_hybrid_preset_has_both(self):
        """WHEN the code under test is exercised for: hybrid preset has both"""
        preset = get_preset("hybrid")
        tabs = preset["dashboard"]["tabs"]["visible"]

        """THEN the expected behaviour holds: hybrid preset has both"""
        assert "sprints" in tabs
        assert "flow" in tabs

    """GIVEN presets and the scenario: custom preset is empty"""
    def test_custom_preset_is_empty(self):
        """WHEN the code under test is exercised for: custom preset is empty"""
        preset = get_preset("custom")

        """THEN the expected behaviour holds: custom preset is empty"""
        assert preset == {}

    """GIVEN presets and the scenario: unknown preset is empty"""
    def test_unknown_preset_is_empty(self):
        """WHEN the code under test is exercised for: unknown preset is empty"""
        preset = get_preset("unknown_xyz")

        """THEN the expected behaviour holds: unknown preset is empty"""
        assert preset == {}

    """GIVEN presets and the scenario: apply preset user overrides win"""
    def test_apply_preset_user_overrides_win(self):
        """WHEN the code under test is exercised for: apply preset user overrides win"""
        user_raw = {
            "methodology": "kanban",
            "dashboard": {
                "tabs": {
                    "visible": ["overview", "issues"],
                },
            },
        }
        result = apply_preset(user_raw, "kanban")
        # User explicitly set tabs - should NOT be overridden

        """THEN the expected behaviour holds: apply preset user overrides win"""
        assert result["dashboard"]["tabs"]["visible"] == ["overview", "issues"]

    """GIVEN presets and the scenario: apply preset fills missing"""
    def test_apply_preset_fills_missing(self):
        """WHEN the code under test is exercised for: apply preset fills missing"""
        user_raw = {"methodology": "kanban"}
        result = apply_preset(user_raw, "kanban")
        # Preset should fill in tabs since user didn't specify

        """THEN the expected behaviour holds: apply preset fills missing"""
        assert "flow" in result["dashboard"]["tabs"]["visible"]


class TestPresetIntegration:
    """GIVEN preset integration and the scenario: kanban config has flow tab"""
    def test_kanban_config_has_flow_tab(self):
        """WHEN the code under test is exercised for: kanban config has flow tab"""
        cfg = _make_config("kanban")

        """THEN the expected behaviour holds: kanban config has flow tab"""
        assert "flow" in cfg.dashboard.tabs.visible
        assert "sprints" not in cfg.dashboard.tabs.visible

    """GIVEN preset integration and the scenario: scrum config has sprints tab"""
    def test_scrum_config_has_sprints_tab(self):
        """WHEN the code under test is exercised for: scrum config has sprints tab"""
        cfg = _make_config("scrum")

        """THEN the expected behaviour holds: scrum config has sprints tab"""
        assert "sprints" in cfg.dashboard.tabs.visible

    """GIVEN preset integration and the scenario: user can override kanban tabs"""
    def test_user_can_override_kanban_tabs(self):
        """WHEN the code under test is exercised for: user can override kanban tabs"""
        cfg = load_config_from_dict(
            {
                "jira": {"base_url": "https://test.atlassian.net"},
                "methodology": "kanban",
                "dashboard": {"tabs": {"visible": ["overview", "flow", "issues"]}},
            }
        )

        """THEN the expected behaviour holds: user can override kanban tabs"""
        assert cfg.dashboard.tabs.visible == ["overview", "flow", "issues"]


# ===================================================================
# Phase 2: Kanban Analytics
# ===================================================================


class TestAdaptiveTabs:
    """GIVEN adaptive tabs and the scenario: scrum renders sprints no flow"""
    def test_scrum_renders_sprints_no_flow(self):
        """WHEN the code under test is exercised for: scrum renders sprints no flow"""
        html = _render("scrum")

        """THEN the expected behaviour holds: scrum renders sprints no flow"""
        assert "tab-sprints" in html
        assert "tab-flow" not in html

    """GIVEN adaptive tabs and the scenario: kanban renders flow no sprints"""
    def test_kanban_renders_flow_no_sprints(self):
        """WHEN the code under test is exercised for: kanban renders flow no sprints"""
        html = _render("kanban")

        """THEN the expected behaviour holds: kanban renders flow no sprints"""
        assert "tab-flow" in html
        assert "tab-sprints" not in html

    """GIVEN adaptive tabs and the scenario: hybrid renders both"""
    def test_hybrid_renders_both(self):
        """WHEN the code under test is exercised for: hybrid renders both"""
        html = _render("hybrid")

        """THEN the expected behaviour holds: hybrid renders both"""
        assert "tab-sprints" in html
        assert "tab-flow" in html

    """GIVEN adaptive tabs and the scenario: custom uses default tabs"""
    def test_custom_uses_default_tabs(self):
        """WHEN the code under test is exercised for: custom uses default tabs"""
        cfg = _make_config("custom")
        # Custom preset is empty - falls through to hardcoded defaults

        """THEN the expected behaviour holds: custom uses default tabs"""
        assert len(cfg.dashboard.tabs.visible) > 0

    """GIVEN adaptive tabs and the scenario: flow tab has kanban content"""
    def test_flow_tab_has_kanban_content(self):
        """WHEN the code under test is exercised for: flow tab has kanban content"""
        html = _render("kanban")

        """THEN the expected behaviour holds: flow tab has kanban content"""
        assert "kanban-metrics-grid" in html
        assert "Flow Metrics" in html or "flow-metrics" in html

    """GIVEN adaptive tabs and the scenario: nav has flow button for kanban"""
    def test_nav_has_flow_button_for_kanban(self):
        """WHEN the code under test is exercised for: nav has flow button for kanban"""
        html = _render("kanban")

        """THEN the expected behaviour holds: nav has flow button for kanban"""
        assert "tab-flow-btn" in html
        assert "📊" in html  # Flow tab emoji


# ===================================================================
# Phase 7: Methodology i18n
# ===================================================================


class TestMethodologyI18n:
    """GIVEN methodology i18n and the scenario: en has kanban keys"""
    def test_en_has_kanban_keys(self):
        """WHEN the code under test is exercised for: en has kanban keys"""
        t = Translator("en")

        """THEN the expected behaviour holds: en has kanban keys"""
        assert t.has("kanban.avg_cycle_time")
        assert t.has("kanban.throughput")
        assert t.has("kanban.wip")
        assert t.has("kanban.flow_efficiency")
        assert t.has("kanban.cfd")
        assert t.has("tab.flow")

    """GIVEN methodology i18n and the scenario: pl has kanban keys"""
    def test_pl_has_kanban_keys(self):
        """WHEN the code under test is exercised for: pl has kanban keys"""
        t = Translator("pl")

        """THEN the expected behaviour holds: pl has kanban keys"""
        assert t.has("kanban.avg_cycle_time")
        assert t.has("kanban.throughput")
        assert t.has("kanban.wip")
        assert t.has("tab.flow")

    """GIVEN methodology i18n and the scenario: en kanban labels"""
    def test_en_kanban_labels(self):
        """WHEN the code under test is exercised for: en kanban labels"""
        t = Translator("en")

        """THEN the expected behaviour holds: en kanban labels"""
        assert t("kanban.avg_cycle_time") == "Avg Cycle Time"
        assert t("kanban.throughput") == "Throughput"
        assert t("tab.flow") == "📊 Flow"

    """GIVEN methodology i18n and the scenario: pl kanban labels"""
    def test_pl_kanban_labels(self):
        """WHEN the code under test is exercised for: pl kanban labels"""
        t = Translator("pl")

        """THEN the expected behaviour holds: pl kanban labels"""
        assert t("kanban.avg_cycle_time") == "Śr. Czas Cyklu"
        assert t("kanban.throughput") == "Przepustowość"
        assert t("tab.flow") == "📊 Przepływ"

    """GIVEN methodology i18n and the scenario: kanban render in polish"""
    def test_kanban_render_in_polish(self):
        """WHEN the code under test is exercised for: kanban render in polish"""
        html = _render("kanban", "pl")

        """THEN the expected behaviour holds: kanban render in polish"""
        assert "Przepływ" in html
        assert "Metryki Przepływu" in html

    """GIVEN methodology i18n and the scenario: kanban render in english"""
    def test_kanban_render_in_english(self):
        """WHEN the code under test is exercised for: kanban render in english"""
        html = _render("kanban", "en")

        """THEN the expected behaviour holds: kanban render in english"""
        assert "Flow" in html
        assert "Flow Metrics" in html


# ===================================================================
# Phase 9: Scrum Backward Compatibility
# ===================================================================


class TestScrumBackwardCompat:
    """GIVEN scrum backward compat and the scenario: default config is scrum"""
    def test_default_config_is_scrum(self):
        """WHEN the code under test is exercised for: default config is scrum"""
        cfg = load_config_from_dict(
            {
                "jira": {"base_url": "https://test.atlassian.net"},
            }
        )

        """THEN the expected behaviour holds: default config is scrum"""
        assert cfg.methodology == "scrum"

    """GIVEN scrum backward compat and the scenario: scrum tabs unchanged"""
    def test_scrum_tabs_unchanged(self):
        """WHEN the code under test is exercised for: scrum tabs unchanged"""
        cfg = _make_config("scrum")
        expected = [
            "overview",
            "workload",
            "sprints",
            "timeline",
            "pi",
            "insights",
            "issues",
        ]

        """THEN the expected behaviour holds: scrum tabs unchanged"""
        assert cfg.dashboard.tabs.visible == expected

    """GIVEN scrum backward compat and the scenario: scrum render has sprint health"""
    def test_scrum_render_has_sprint_health(self):
        """WHEN the code under test is exercised for: scrum render has sprint health"""
        html = _render("scrum")

        """THEN the expected behaviour holds: scrum render has sprint health"""
        assert "tab-sprints" in html

    """GIVEN scrum backward compat and the scenario: no flow tab in scrum"""
    def test_no_flow_tab_in_scrum(self):
        """WHEN the code under test is exercised for: no flow tab in scrum"""
        html = _render("scrum")

        """THEN the expected behaviour holds: no flow tab in scrum"""
        assert "tab-flow" not in html

    """GIVEN scrum backward compat and the scenario: en render produces valid html"""
    def test_en_render_produces_valid_html(self):
        """WHEN the code under test is exercised for: en render produces valid html"""
        html = _render("scrum", "en")

        """THEN the expected behaviour holds: en render produces valid html"""
        assert "<!DOCTYPE html>" in html
        assert "</html>" in html

    """GIVEN scrum backward compat and the scenario: pl render produces valid html"""
    def test_pl_render_produces_valid_html(self):
        """WHEN the code under test is exercised for: pl render produces valid html"""
        html = _render("scrum", "pl")

        """THEN the expected behaviour holds: pl render produces valid html"""
        assert 'lang="pl"' in html
        assert "</html>" in html

    """GIVEN scrum backward compat and the scenario: kanban insights none for scrum"""
    def test_kanban_insights_none_for_scrum(self):
        """WHEN the code under test is exercised for: kanban insights none for scrum"""
        cfg = _make_config("scrum")
        snap = BoardSnapshot(title="Test")
        html = render_dashboard(snap, cfg)
        # Flow tab should not appear

        """THEN the expected behaviour holds: kanban insights none for scrum"""
        assert "tab-flow" not in html


# ===================================================================
# BoardSnapshot Integration
# ===================================================================


class TestHybridPreset:
    """GIVEN hybrid preset and the scenario: hybrid has both sprint and flow"""
    def test_hybrid_has_both_sprint_and_flow(self):
        """WHEN the code under test is exercised for: hybrid has both sprint and flow"""
        cfg = _make_config("hybrid")

        """THEN the expected behaviour holds: hybrid has both sprint and flow"""
        assert "sprints" in cfg.dashboard.tabs.visible
        assert "flow" in cfg.dashboard.tabs.visible

    """GIVEN hybrid preset and the scenario: hybrid renders both tabs"""
    def test_hybrid_renders_both_tabs(self):
        """WHEN the code under test is exercised for: hybrid renders both tabs"""
        html = _render("hybrid")

        """THEN the expected behaviour holds: hybrid renders both tabs"""
        assert "tab-sprints" in html
        assert "tab-flow" in html


class TestCustomMethodology:
    """GIVEN custom methodology and the scenario: custom gets default tabs"""
    def test_custom_gets_default_tabs(self):
        """WHEN the code under test is exercised for: custom gets default tabs"""
        cfg = _make_config("custom")
        # Custom preset is empty - falls through to hardcoded defaults

        """THEN the expected behaviour holds: custom gets default tabs"""
        assert "overview" in cfg.dashboard.tabs.visible

    """GIVEN custom methodology and the scenario: custom render works"""
    def test_custom_render_works(self):
        """WHEN the code under test is exercised for: custom render works"""
        html = _render("custom")

        """THEN the expected behaviour holds: custom render works"""
        assert "<!DOCTYPE html>" in html


class TestMethodologyDetection:
    """GIVEN methodology detection and the scenario: detect scrum"""
    def test_detect_scrum(self):
        """WHEN the code under test is exercised for: detect scrum"""
        from flowboard.infrastructure.config.presets import detect_methodology

        """THEN the expected behaviour holds: detect scrum"""
        assert detect_methodology(has_sprints=True, has_fix_versions=False) == "scrum"

    """GIVEN methodology detection and the scenario: detect kanban"""
    def test_detect_kanban(self):
        """WHEN the code under test is exercised for: detect kanban"""
        from flowboard.infrastructure.config.presets import detect_methodology

        """THEN the expected behaviour holds: detect kanban"""
        assert detect_methodology(has_sprints=False, has_fix_versions=False) == "kanban"

    """GIVEN methodology detection and the scenario: detect waterfall"""
    def test_detect_waterfall(self):
        """WHEN the code under test is exercised for: detect waterfall"""
        from flowboard.infrastructure.config.presets import detect_methodology

        """THEN the expected behaviour holds: detect waterfall"""
        assert detect_methodology(has_sprints=False, has_fix_versions=True) == "waterfall"

    """GIVEN methodology detection and the scenario: detect hybrid"""
    def test_detect_hybrid(self):
        """WHEN the code under test is exercised for: detect hybrid"""
        from flowboard.infrastructure.config.presets import detect_methodology

        """THEN the expected behaviour holds: detect hybrid"""
        assert detect_methodology(has_sprints=True, has_fix_versions=True) == "hybrid"


# ===================================================================
# Methodology-adaptive rendering
# ===================================================================


class TestMethodologyAdaptiveRendering:
    """Tests for methodology adaptive rendering."""

    def _render(self, methodology: str) -> str:
        from flowboard.domain.models import BoardSnapshot
        from flowboard.infrastructure.config.loader import load_config_from_dict
        from flowboard.presentation.html.renderer import render_dashboard

        cfg_dict = {
            "jira": {"base_url": "https://test.atlassian.net"},
            "methodology": methodology,
            "output": {"path": "test.html"},
        }
        cfg = load_config_from_dict(cfg_dict)
        snapshot = BoardSnapshot()
        return render_dashboard(snapshot, cfg)

    """GIVEN methodology adaptive rendering and the scenario: scrum shows product progress"""
    def test_scrum_shows_product_progress(self):
        """WHEN the code under test is exercised for: scrum shows product progress"""
        html = self._render("scrum")

        """THEN the expected behaviour holds: scrum shows product progress"""
        assert (
            "scrum_product_progress" in html
            or "product-progress" in html
            or "Product Progress" in html
        )

    """GIVEN methodology adaptive rendering and the scenario: scrum shows ceremonies"""
    def test_scrum_shows_ceremonies(self):
        """WHEN the code under test is exercised for: scrum shows ceremonies"""
        html = self._render("scrum")

        """THEN the expected behaviour holds: scrum shows ceremonies"""
        assert "Ceremony" in html

    """GIVEN methodology adaptive rendering and the scenario: kanban hides product progress"""
    def test_kanban_hides_product_progress(self):
        """WHEN the code under test is exercised for: kanban hides product progress"""
        html = self._render("kanban")

        """THEN the expected behaviour holds: kanban hides product progress"""
        assert "scrum.product_progress" not in html
        assert "scrum.ceremonies" not in html

    """GIVEN methodology adaptive rendering and the scenario: kanban shows flow metrics"""
    def test_kanban_shows_flow_metrics(self):
        """WHEN the code under test is exercised for: kanban shows flow metrics"""
        html = self._render("kanban")

        """THEN the expected behaviour holds: kanban shows flow metrics"""
        assert "kanban.flow_metrics" in html or "Flow Metrics" in html

    """GIVEN methodology adaptive rendering and the scenario: waterfall hides scrum sections"""
    def test_waterfall_hides_scrum_sections(self):
        """WHEN the code under test is exercised for: waterfall hides scrum sections"""
        html = self._render("waterfall")

        """THEN the expected behaviour holds: waterfall hides scrum sections"""
        assert "scrum.product_progress" not in html
        assert "scrum.ceremonies" not in html

    """GIVEN methodology adaptive rendering and the scenario: waterfall shows phase progress"""
    def test_waterfall_shows_phase_progress(self):
        """WHEN the code under test is exercised for: waterfall shows phase progress"""
        html = self._render("waterfall")

        """THEN the expected behaviour holds: waterfall shows phase progress"""
        assert "Phase Progress" in html or "waterfall.phase_progress" in html

    """GIVEN methodology adaptive rendering and the scenario: hybrid shows scrum and kanban"""
    def test_hybrid_shows_scrum_and_kanban(self):
        """WHEN the code under test is exercised for: hybrid shows scrum and kanban"""
        html = self._render("hybrid")
        # Scrum sections

        """THEN the expected behaviour holds: hybrid shows scrum and kanban"""
        assert "Ceremony" in html
        # Kanban sections
        assert "kanban.flow_metrics" in html or "Flow Metrics" in html

    """GIVEN methodology adaptive rendering and the scenario: kanban no sprints tab"""
    def test_kanban_no_sprints_tab(self):
        """WHEN the code under test is exercised for: kanban no sprints tab"""
        html = self._render("kanban")

        """THEN the expected behaviour holds: kanban no sprints tab"""
        assert 'data-tab="sprints"' not in html

    """GIVEN methodology adaptive rendering and the scenario: kanban has flow tab"""
    def test_kanban_has_flow_tab(self):
        """WHEN the code under test is exercised for: kanban has flow tab"""
        html = self._render("kanban")

        """THEN the expected behaviour holds: kanban has flow tab"""
        assert 'data-tab="flow"' in html

    """GIVEN methodology adaptive rendering and the scenario: waterfall has phases tab"""
    def test_waterfall_has_phases_tab(self):
        """WHEN the code under test is exercised for: waterfall has phases tab"""
        html = self._render("waterfall")

        """THEN the expected behaviour holds: waterfall has phases tab"""
        assert 'data-tab="phases"' in html

    """GIVEN methodology adaptive rendering and the scenario: waterfall no sprints tab"""
    def test_waterfall_no_sprints_tab(self):
        """WHEN the code under test is exercised for: waterfall no sprints tab"""
        html = self._render("waterfall")

        """THEN the expected behaviour holds: waterfall no sprints tab"""
        assert 'data-tab="sprints"' not in html

    """GIVEN methodology adaptive rendering and the scenario: scrum no flow tab"""
    def test_scrum_no_flow_tab(self):
        """WHEN the code under test is exercised for: scrum no flow tab"""
        html = self._render("scrum")

        """THEN the expected behaviour holds: scrum no flow tab"""
        assert 'data-tab="flow"' not in html

    """GIVEN methodology adaptive rendering and the scenario: scrum no phases tab"""
    def test_scrum_no_phases_tab(self):
        """WHEN the code under test is exercised for: scrum no phases tab"""
        html = self._render("scrum")

        """THEN the expected behaviour holds: scrum no phases tab"""
        assert 'data-tab="phases"' not in html

    """GIVEN methodology adaptive rendering and the scenario: hybrid has both tabs"""
    def test_hybrid_has_both_tabs(self):
        """WHEN the code under test is exercised for: hybrid has both tabs"""
        html = self._render("hybrid")

        """THEN the expected behaviour holds: hybrid has both tabs"""
        assert 'data-tab="sprints"' in html
        assert 'data-tab="flow"' in html

    """GIVEN methodology adaptive rendering and the scenario: kanban insights tab no blockers"""
    def test_kanban_insights_tab_no_blockers(self):
        """WHEN the code under test is exercised for: kanban insights tab no blockers"""
        html = self._render("kanban")

        """THEN the expected behaviour holds: kanban insights tab no blockers"""
        assert 'id="insightsBlockers"' not in html

    """GIVEN methodology adaptive rendering and the scenario: kanban insights tab no forecast"""
    def test_kanban_insights_tab_no_forecast(self):
        """WHEN the code under test is exercised for: kanban insights tab no forecast"""
        html = self._render("kanban")

        """THEN the expected behaviour holds: kanban insights tab no forecast"""
        assert 'id="insightsForecast"' not in html

    """GIVEN methodology adaptive rendering and the scenario: scrum insights tab has blockers"""
    def test_scrum_insights_tab_has_blockers(self):
        """WHEN the code under test is exercised for: scrum insights tab has blockers"""
        html = self._render("scrum")

        """THEN the expected behaviour holds: scrum insights tab has blockers"""
        assert 'id="insightsBlockers"' in html

    """GIVEN methodology adaptive rendering and the scenario: scrum insights tab has forecast"""
    def test_scrum_insights_tab_has_forecast(self):
        """WHEN the code under test is exercised for: scrum insights tab has forecast"""
        html = self._render("scrum")

        """THEN the expected behaviour holds: scrum insights tab has forecast"""
        assert 'id="insightsForecast"' in html


class TestMethodologySummaryCards:
    """Tests for methodology summary cards."""

    """GIVEN methodology summary cards and the scenario: kanban card defs exist"""
    def test_kanban_card_defs_exist(self):
        """WHEN the code under test is exercised for: kanban card defs exist"""
        from flowboard.presentation.html.components import _CARD_DEFS

        """THEN the expected behaviour holds: kanban card defs exist"""
        assert "avg_cycle_time" in _CARD_DEFS
        assert "throughput" in _CARD_DEFS
        assert "wip_violations" in _CARD_DEFS

    """GIVEN methodology summary cards and the scenario: waterfall card defs exist"""
    def test_waterfall_card_defs_exist(self):
        """WHEN the code under test is exercised for: waterfall card defs exist"""
        from flowboard.presentation.html.components import _CARD_DEFS

        """THEN the expected behaviour holds: waterfall card defs exist"""
        assert "milestones_on_track" in _CARD_DEFS
        assert "phase_progress" in _CARD_DEFS

    """GIVEN methodology summary cards and the scenario: kanban cards render"""
    def test_kanban_cards_render(self):
        """WHEN the code under test is exercised for: kanban cards render"""
        from flowboard.domain.models import BoardSnapshot
        from flowboard.infrastructure.config.config_models import SummaryCardsConfig
        from flowboard.presentation.html.components import summary_cards

        snapshot = BoardSnapshot()
        cfg = SummaryCardsConfig(visible=["avg_cycle_time", "throughput", "wip_violations"])
        html = summary_cards(snapshot, cfg)

        """THEN the expected behaviour holds: kanban cards render"""
        assert "Avg Cycle Time" in html or "avg_cycle_time" in html.lower()
        assert "Throughput" in html or "throughput" in html.lower()

    """GIVEN methodology summary cards and the scenario: waterfall cards render"""
    def test_waterfall_cards_render(self):
        """WHEN the code under test is exercised for: waterfall cards render"""
        from flowboard.domain.models import BoardSnapshot
        from flowboard.infrastructure.config.config_models import SummaryCardsConfig
        from flowboard.presentation.html.components import summary_cards

        snapshot = BoardSnapshot()
        cfg = SummaryCardsConfig(visible=["milestones_on_track", "phase_progress"])
        html = summary_cards(snapshot, cfg)

        """THEN the expected behaviour holds: waterfall cards render"""
        assert "Milestones" in html or "milestones" in html.lower()
        assert "Phase Progress" in html or "phase_progress" in html.lower()

    """GIVEN methodology summary cards and the scenario: card i18n en keys"""
    def test_card_i18n_en_keys(self):
        """WHEN the code under test is exercised for: card i18n en keys"""
        import json
        from pathlib import Path

        p = Path(__file__).resolve().parents[1] / "src" / "flowboard" / "i18n" / "en.json"
        d = json.loads(p.read_text())

        """THEN the expected behaviour holds: card i18n en keys"""
        for key in [
            "card.avg_cycle_time",
            "card.throughput",
            "card.wip_violations",
            "card.milestones_on_track",
            "card.phase_progress",
        ]:
            assert key in d, f"Missing en.json key: {key}"

    """GIVEN methodology summary cards and the scenario: card i18n pl keys"""
    def test_card_i18n_pl_keys(self):
        """WHEN the code under test is exercised for: card i18n pl keys"""
        import json
        from pathlib import Path

        p = Path(__file__).resolve().parents[1] / "src" / "flowboard" / "i18n" / "pl.json"
        d = json.loads(p.read_text())

        """THEN the expected behaviour holds: card i18n pl keys"""
        for key in [
            "card.avg_cycle_time",
            "card.throughput",
            "card.wip_violations",
            "card.milestones_on_track",
            "card.phase_progress",
        ]:
            assert key in d, f"Missing pl.json key: {key}"
