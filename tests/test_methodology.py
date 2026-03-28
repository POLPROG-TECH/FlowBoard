"""Methodology tests — configuration, presets, integration, i18n, detection, adaptive rendering."""

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
    def test_default_methodology_is_scrum(self):
        cfg = _make_config()
        assert cfg.methodology == "scrum"

    def test_kanban_methodology(self):
        cfg = _make_config("kanban")
        assert cfg.methodology == "kanban"

    def test_waterfall_methodology(self):
        cfg = _make_config("waterfall")
        assert cfg.methodology == "waterfall"

    def test_hybrid_methodology(self):
        cfg = _make_config("hybrid")
        assert cfg.methodology == "hybrid"

    def test_custom_methodology(self):
        cfg = _make_config("custom")
        assert cfg.methodology == "custom"

    def test_invalid_methodology_rejected_by_schema(self):
        from flowboard.infrastructure.config.validator import ConfigValidationError

        with pytest.raises(ConfigValidationError):
            _make_config("agile")

    def test_methodology_in_config_to_dict(self):
        cfg = _make_config("kanban")
        d = config_to_dict(cfg)
        assert d["methodology"] == "kanban"

    def test_supported_methodologies_constant(self):
        assert {"scrum", "kanban", "waterfall", "hybrid", "custom"} == SUPPORTED_METHODOLOGIES


class TestPresets:
    def test_scrum_preset_has_sprints_tab(self):
        preset = get_preset("scrum")
        tabs = preset["dashboard"]["tabs"]["visible"]
        assert "sprints" in tabs
        assert "flow" not in tabs

    def test_kanban_preset_has_flow_tab(self):
        preset = get_preset("kanban")
        tabs = preset["dashboard"]["tabs"]["visible"]
        assert "flow" in tabs
        assert "sprints" not in tabs

    def test_waterfall_preset_has_phases_tab(self):
        preset = get_preset("waterfall")
        tabs = preset["dashboard"]["tabs"]["visible"]
        assert "phases" in tabs
        assert "sprints" not in tabs

    def test_hybrid_preset_has_both(self):
        preset = get_preset("hybrid")
        tabs = preset["dashboard"]["tabs"]["visible"]
        assert "sprints" in tabs
        assert "flow" in tabs

    def test_custom_preset_is_empty(self):
        preset = get_preset("custom")
        assert preset == {}

    def test_unknown_preset_is_empty(self):
        preset = get_preset("unknown_xyz")
        assert preset == {}

    def test_apply_preset_user_overrides_win(self):
        user_raw = {
            "methodology": "kanban",
            "dashboard": {
                "tabs": {
                    "visible": ["overview", "issues"],
                },
            },
        }
        result = apply_preset(user_raw, "kanban")
        # User explicitly set tabs — should NOT be overridden
        assert result["dashboard"]["tabs"]["visible"] == ["overview", "issues"]

    def test_apply_preset_fills_missing(self):
        user_raw = {"methodology": "kanban"}
        result = apply_preset(user_raw, "kanban")
        # Preset should fill in tabs since user didn't specify
        assert "flow" in result["dashboard"]["tabs"]["visible"]


class TestPresetIntegration:
    def test_kanban_config_has_flow_tab(self):
        cfg = _make_config("kanban")
        assert "flow" in cfg.dashboard.tabs.visible
        assert "sprints" not in cfg.dashboard.tabs.visible

    def test_scrum_config_has_sprints_tab(self):
        cfg = _make_config("scrum")
        assert "sprints" in cfg.dashboard.tabs.visible

    def test_user_can_override_kanban_tabs(self):
        cfg = load_config_from_dict(
            {
                "jira": {"base_url": "https://test.atlassian.net"},
                "methodology": "kanban",
                "dashboard": {"tabs": {"visible": ["overview", "flow", "issues"]}},
            }
        )
        assert cfg.dashboard.tabs.visible == ["overview", "flow", "issues"]


# ===================================================================
# Phase 2: Kanban Analytics
# ===================================================================


class TestAdaptiveTabs:
    def test_scrum_renders_sprints_no_flow(self):
        html = _render("scrum")
        assert "tab-sprints" in html
        assert "tab-flow" not in html

    def test_kanban_renders_flow_no_sprints(self):
        html = _render("kanban")
        assert "tab-flow" in html
        assert "tab-sprints" not in html

    def test_hybrid_renders_both(self):
        html = _render("hybrid")
        assert "tab-sprints" in html
        assert "tab-flow" in html

    def test_custom_uses_default_tabs(self):
        cfg = _make_config("custom")
        # Custom preset is empty — falls through to hardcoded defaults
        assert len(cfg.dashboard.tabs.visible) > 0

    def test_flow_tab_has_kanban_content(self):
        html = _render("kanban")
        assert "kanban-metrics-grid" in html
        assert "Flow Metrics" in html or "flow-metrics" in html

    def test_nav_has_flow_button_for_kanban(self):
        html = _render("kanban")
        assert "tab-flow-btn" in html
        assert "📊" in html  # Flow tab emoji


# ===================================================================
# Phase 7: Methodology i18n
# ===================================================================


class TestMethodologyI18n:
    def test_en_has_kanban_keys(self):
        t = Translator("en")
        assert t.has("kanban.avg_cycle_time")
        assert t.has("kanban.throughput")
        assert t.has("kanban.wip")
        assert t.has("kanban.flow_efficiency")
        assert t.has("kanban.cfd")
        assert t.has("tab.flow")

    def test_pl_has_kanban_keys(self):
        t = Translator("pl")
        assert t.has("kanban.avg_cycle_time")
        assert t.has("kanban.throughput")
        assert t.has("kanban.wip")
        assert t.has("tab.flow")

    def test_en_kanban_labels(self):
        t = Translator("en")
        assert t("kanban.avg_cycle_time") == "Avg Cycle Time"
        assert t("kanban.throughput") == "Throughput"
        assert t("tab.flow") == "📊 Flow"

    def test_pl_kanban_labels(self):
        t = Translator("pl")
        assert t("kanban.avg_cycle_time") == "Śr. Czas Cyklu"
        assert t("kanban.throughput") == "Przepustowość"
        assert t("tab.flow") == "📊 Przepływ"

    def test_kanban_render_in_polish(self):
        html = _render("kanban", "pl")
        assert "Przepływ" in html
        assert "Metryki Przepływu" in html

    def test_kanban_render_in_english(self):
        html = _render("kanban", "en")
        assert "Flow" in html
        assert "Flow Metrics" in html


# ===================================================================
# Phase 9: Scrum Backward Compatibility
# ===================================================================


class TestScrumBackwardCompat:
    def test_default_config_is_scrum(self):
        cfg = load_config_from_dict(
            {
                "jira": {"base_url": "https://test.atlassian.net"},
            }
        )
        assert cfg.methodology == "scrum"

    def test_scrum_tabs_unchanged(self):
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
        assert cfg.dashboard.tabs.visible == expected

    def test_scrum_render_has_sprint_health(self):
        html = _render("scrum")
        assert "tab-sprints" in html

    def test_no_flow_tab_in_scrum(self):
        html = _render("scrum")
        assert "tab-flow" not in html

    def test_en_render_produces_valid_html(self):
        html = _render("scrum", "en")
        assert "<!DOCTYPE html>" in html
        assert "</html>" in html

    def test_pl_render_produces_valid_html(self):
        html = _render("scrum", "pl")
        assert 'lang="pl"' in html
        assert "</html>" in html

    def test_kanban_insights_none_for_scrum(self):
        """When methodology is scrum, kanban_insights should be None."""
        cfg = _make_config("scrum")
        snap = BoardSnapshot(title="Test")
        html = render_dashboard(snap, cfg)
        # Flow tab should not appear
        assert "tab-flow" not in html


# ===================================================================
# BoardSnapshot Integration
# ===================================================================


class TestHybridPreset:
    def test_hybrid_has_both_sprint_and_flow(self):
        cfg = _make_config("hybrid")
        assert "sprints" in cfg.dashboard.tabs.visible
        assert "flow" in cfg.dashboard.tabs.visible

    def test_hybrid_renders_both_tabs(self):
        html = _render("hybrid")
        assert "tab-sprints" in html
        assert "tab-flow" in html


class TestCustomMethodology:
    def test_custom_gets_default_tabs(self):
        cfg = _make_config("custom")
        # Custom preset is empty — falls through to hardcoded defaults
        assert "overview" in cfg.dashboard.tabs.visible

    def test_custom_render_works(self):
        html = _render("custom")
        assert "<!DOCTYPE html>" in html


class TestMethodologyDetection:
    def test_detect_scrum(self):
        from flowboard.infrastructure.config.presets import detect_methodology

        assert detect_methodology(has_sprints=True, has_fix_versions=False) == "scrum"

    def test_detect_kanban(self):
        from flowboard.infrastructure.config.presets import detect_methodology

        assert detect_methodology(has_sprints=False, has_fix_versions=False) == "kanban"

    def test_detect_waterfall(self):
        from flowboard.infrastructure.config.presets import detect_methodology

        assert detect_methodology(has_sprints=False, has_fix_versions=True) == "waterfall"

    def test_detect_hybrid(self):
        from flowboard.infrastructure.config.presets import detect_methodology

        assert detect_methodology(has_sprints=True, has_fix_versions=True) == "hybrid"


# ===================================================================
# Methodology-adaptive rendering
# ===================================================================


class TestMethodologyAdaptiveRendering:
    """Verify dashboard content adapts to each methodology."""

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

    def test_scrum_shows_product_progress(self):
        html = self._render("scrum")
        assert (
            "scrum_product_progress" in html
            or "product-progress" in html
            or "Product Progress" in html
        )

    def test_scrum_shows_ceremonies(self):
        html = self._render("scrum")
        assert "Ceremony" in html

    def test_kanban_hides_product_progress(self):
        html = self._render("kanban")
        assert "scrum.product_progress" not in html
        assert "scrum.ceremonies" not in html

    def test_kanban_shows_flow_metrics(self):
        html = self._render("kanban")
        assert "kanban.flow_metrics" in html or "Flow Metrics" in html

    def test_waterfall_hides_scrum_sections(self):
        html = self._render("waterfall")
        assert "scrum.product_progress" not in html
        assert "scrum.ceremonies" not in html

    def test_waterfall_shows_phase_progress(self):
        html = self._render("waterfall")
        assert "Phase Progress" in html or "waterfall.phase_progress" in html

    def test_hybrid_shows_scrum_and_kanban(self):
        html = self._render("hybrid")
        # Scrum sections
        assert "Ceremony" in html
        # Kanban sections
        assert "kanban.flow_metrics" in html or "Flow Metrics" in html

    def test_kanban_no_sprints_tab(self):
        html = self._render("kanban")
        assert 'data-tab="sprints"' not in html

    def test_kanban_has_flow_tab(self):
        html = self._render("kanban")
        assert 'data-tab="flow"' in html

    def test_waterfall_has_phases_tab(self):
        html = self._render("waterfall")
        assert 'data-tab="phases"' in html

    def test_waterfall_no_sprints_tab(self):
        html = self._render("waterfall")
        assert 'data-tab="sprints"' not in html

    def test_scrum_no_flow_tab(self):
        html = self._render("scrum")
        assert 'data-tab="flow"' not in html

    def test_scrum_no_phases_tab(self):
        html = self._render("scrum")
        assert 'data-tab="phases"' not in html

    def test_hybrid_has_both_tabs(self):
        html = self._render("hybrid")
        assert 'data-tab="sprints"' in html
        assert 'data-tab="flow"' in html

    def test_kanban_insights_tab_no_blockers(self):
        html = self._render("kanban")
        assert 'id="insightsBlockers"' not in html

    def test_kanban_insights_tab_no_forecast(self):
        html = self._render("kanban")
        assert 'id="insightsForecast"' not in html

    def test_scrum_insights_tab_has_blockers(self):
        html = self._render("scrum")
        assert 'id="insightsBlockers"' in html

    def test_scrum_insights_tab_has_forecast(self):
        html = self._render("scrum")
        assert 'id="insightsForecast"' in html


class TestMethodologySummaryCards:
    """Verify summary cards adapt to methodology."""

    def test_kanban_card_defs_exist(self):
        from flowboard.presentation.html.components import _CARD_DEFS

        assert "avg_cycle_time" in _CARD_DEFS
        assert "throughput" in _CARD_DEFS
        assert "wip_violations" in _CARD_DEFS

    def test_waterfall_card_defs_exist(self):
        from flowboard.presentation.html.components import _CARD_DEFS

        assert "milestones_on_track" in _CARD_DEFS
        assert "phase_progress" in _CARD_DEFS

    def test_kanban_cards_render(self):
        from flowboard.domain.models import BoardSnapshot
        from flowboard.infrastructure.config.config_models import SummaryCardsConfig
        from flowboard.presentation.html.components import summary_cards

        snapshot = BoardSnapshot()
        cfg = SummaryCardsConfig(visible=["avg_cycle_time", "throughput", "wip_violations"])
        html = summary_cards(snapshot, cfg)
        assert "Avg Cycle Time" in html or "avg_cycle_time" in html.lower()
        assert "Throughput" in html or "throughput" in html.lower()

    def test_waterfall_cards_render(self):
        from flowboard.domain.models import BoardSnapshot
        from flowboard.infrastructure.config.config_models import SummaryCardsConfig
        from flowboard.presentation.html.components import summary_cards

        snapshot = BoardSnapshot()
        cfg = SummaryCardsConfig(visible=["milestones_on_track", "phase_progress"])
        html = summary_cards(snapshot, cfg)
        assert "Milestones" in html or "milestones" in html.lower()
        assert "Phase Progress" in html or "phase_progress" in html.lower()

    def test_card_i18n_en_keys(self):
        import json
        from pathlib import Path

        p = Path(__file__).resolve().parents[1] / "src" / "flowboard" / "i18n" / "en.json"
        d = json.loads(p.read_text())
        for key in [
            "card.avg_cycle_time",
            "card.throughput",
            "card.wip_violations",
            "card.milestones_on_track",
            "card.phase_progress",
        ]:
            assert key in d, f"Missing en.json key: {key}"

    def test_card_i18n_pl_keys(self):
        import json
        from pathlib import Path

        p = Path(__file__).resolve().parents[1] / "src" / "flowboard" / "i18n" / "pl.json"
        d = json.loads(p.read_text())
        for key in [
            "card.avg_cycle_time",
            "card.throughput",
            "card.wip_violations",
            "card.milestones_on_track",
            "card.phase_progress",
        ]:
            assert key in d, f"Missing pl.json key: {key}"
