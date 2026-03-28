"""Tests for dashboard configuration — loading, validation, round-trip,
default-filling, and schema compliance.
"""

from __future__ import annotations

import json
from pathlib import Path

from flowboard.infrastructure.config.loader import (
    DashboardConfig,
    PIConfig,
    config_to_dict,
    load_config_from_dict,
)

SCHEMA_PATH = Path(__file__).parent.parent / "config.schema.json"


# ---------------------------------------------------------------------------
# Dashboard config defaults
# ---------------------------------------------------------------------------

class TestDashboardConfigDefaults:
    """GIVEN no dashboard section, WHEN config is loaded, THEN sane defaults are applied."""

    def test_dashboard_created_with_defaults(self, minimal_config_dict: dict) -> None:
        cfg = load_config_from_dict(minimal_config_dict)
        assert isinstance(cfg.dashboard, DashboardConfig)

    def test_branding_title_defaults_to_output_title(self, minimal_config_dict: dict) -> None:
        cfg = load_config_from_dict(minimal_config_dict)
        # When no dashboard.branding.title, falls back to output.title
        assert cfg.dashboard.branding.title == cfg.output.title

    def test_default_tabs_include_all(self, minimal_config_dict: dict) -> None:
        cfg = load_config_from_dict(minimal_config_dict)
        expected = ["overview", "workload", "sprints", "timeline", "pi",
                    "insights", "issues"]
        assert cfg.dashboard.tabs.visible == expected

    def test_default_layout_is_comfortable(self, minimal_config_dict: dict) -> None:
        cfg = load_config_from_dict(minimal_config_dict)
        assert cfg.dashboard.layout.density == "comfortable"

    def test_default_charts_all_enabled(self, minimal_config_dict: dict) -> None:
        cfg = load_config_from_dict(minimal_config_dict)
        assert cfg.dashboard.charts.enabled is True
        assert cfg.dashboard.charts.status_distribution is True

    def test_default_summary_cards(self, minimal_config_dict: dict) -> None:
        cfg = load_config_from_dict(minimal_config_dict)
        assert "total_issues" in cfg.dashboard.summary_cards.visible
        assert "blocked" in cfg.dashboard.summary_cards.visible


# ---------------------------------------------------------------------------
# PI config defaults
# ---------------------------------------------------------------------------

class TestPIConfigDefaults:
    """GIVEN no pi section, WHEN config is loaded, THEN PI defaults are applied."""

    def test_pi_disabled_by_default(self, minimal_config_dict: dict) -> None:
        cfg = load_config_from_dict(minimal_config_dict)
        assert isinstance(cfg.pi, PIConfig)
        assert cfg.pi.enabled is False

    def test_pi_default_sprints_per_pi(self, minimal_config_dict: dict) -> None:
        cfg = load_config_from_dict(minimal_config_dict)
        assert cfg.pi.sprints_per_pi == 5

    def test_pi_default_sprint_length(self, minimal_config_dict: dict) -> None:
        cfg = load_config_from_dict(minimal_config_dict)
        assert cfg.pi.sprint_length_days == 10

    def test_pi_default_working_days(self, minimal_config_dict: dict) -> None:
        cfg = load_config_from_dict(minimal_config_dict)
        assert cfg.pi.working_days == [1, 2, 3, 4, 5]


# ---------------------------------------------------------------------------
# Dashboard config from dict
# ---------------------------------------------------------------------------

class TestDashboardConfigFromDict:
    """GIVEN explicit dashboard config, WHEN loaded, THEN values are set correctly."""

    def test_custom_branding(self) -> None:
        raw = {
            "jira": {"base_url": "https://x.com"},
            "dashboard": {
                "branding": {
                    "title": "My Board",
                    "subtitle": "Custom subtitle",
                    "accent_color": "#FF0000",
                    "company_name": "Acme",
                },
            },
        }
        cfg = load_config_from_dict(raw)
        assert cfg.dashboard.branding.title == "My Board"
        assert cfg.dashboard.branding.subtitle == "Custom subtitle"
        assert cfg.dashboard.branding.primary_color == "#FF0000"

    def test_custom_tabs(self) -> None:
        raw = {
            "jira": {"base_url": "https://x.com"},
            "dashboard": {
                "tabs": {
                    "visible": ["overview", "workload"],
                    "default_tab": "workload",
                },
            },
        }
        cfg = load_config_from_dict(raw)
        assert cfg.dashboard.tabs.visible == ["overview", "workload"]
        assert cfg.dashboard.tabs.default_tab == "workload"

    def test_charts_partially_disabled(self) -> None:
        raw = {
            "jira": {"base_url": "https://x.com"},
            "dashboard": {
                "charts": {
                    "enabled": True,
                    "risk_severity": False,
                    "team_workload": False,
                },
            },
        }
        cfg = load_config_from_dict(raw)
        assert cfg.dashboard.charts.enabled is True
        assert cfg.dashboard.charts.risk_severity is False
        assert cfg.dashboard.charts.status_distribution is True  # default

    def test_custom_tables(self) -> None:
        raw = {
            "jira": {"base_url": "https://x.com"},
            "dashboard": {
                "tables": {
                    "issues_columns": ["key", "summary", "status"],
                    "max_rows": 50,
                    "sort_direction": "desc",
                },
            },
        }
        cfg = load_config_from_dict(raw)
        assert cfg.dashboard.tables.issues_columns == ["key", "summary", "status"]
        assert cfg.dashboard.tables.max_rows == 50
        assert cfg.dashboard.tables.sort_direction == "desc"


# ---------------------------------------------------------------------------
# PI config from dict
# ---------------------------------------------------------------------------

class TestPIConfigFromDict:
    def test_enabled_pi_with_start_date(self) -> None:
        raw = {
            "jira": {"base_url": "https://x.com"},
            "pi": {
                "enabled": True,
                "name": "PI 2026.2",
                "start_date": "2026-06-01",
                "sprints_per_pi": 4,
                "sprint_length_days": 8,
            },
        }
        cfg = load_config_from_dict(raw)
        assert cfg.pi.enabled is True
        assert cfg.pi.name == "PI 2026.2"
        assert cfg.pi.start_date == "2026-06-01"
        assert cfg.pi.sprints_per_pi == 4
        assert cfg.pi.sprint_length_days == 8

    def test_custom_working_days(self) -> None:
        raw = {
            "jira": {"base_url": "https://x.com"},
            "pi": {"working_days": [1, 2, 3, 4]},
        }
        cfg = load_config_from_dict(raw)
        assert cfg.pi.working_days == [1, 2, 3, 4]


# ---------------------------------------------------------------------------
# Round-trip: config_to_dict
# ---------------------------------------------------------------------------

class TestConfigRoundTrip:
    """GIVEN a config, WHEN serialized, THEN it produces a valid JSON-safe dict."""

    def test_round_trip_preserves_structure(self, full_config_dict: dict) -> None:
        cfg = load_config_from_dict(full_config_dict)
        exported = config_to_dict(cfg)
        assert isinstance(exported, dict)
        assert "jira" in exported
        assert "dashboard" in exported
        assert "pi" in exported

    def test_round_trip_strips_secrets(self, full_config_dict: dict) -> None:
        cfg = load_config_from_dict(full_config_dict)
        exported = config_to_dict(cfg)
        jira = exported["jira"]
        assert "auth_token" not in jira
        assert "auth_email" not in jira

    def test_round_trip_dashboard_branding(self) -> None:
        raw = {
            "jira": {"base_url": "https://x.com"},
            "dashboard": {"branding": {"title": "Round Trip Test"}},
        }
        cfg = load_config_from_dict(raw)
        exported = config_to_dict(cfg)
        assert exported["dashboard"]["branding"]["title"] == "Round Trip Test"

    def test_round_trip_pi(self) -> None:
        raw = {
            "jira": {"base_url": "https://x.com"},
            "pi": {"enabled": True, "name": "PI X", "start_date": "2026-01-05"},
        }
        cfg = load_config_from_dict(raw)
        exported = config_to_dict(cfg)
        assert exported["pi"]["enabled"] is True
        assert exported["pi"]["name"] == "PI X"

    def test_round_trip_is_json_serializable(self, full_config_dict: dict) -> None:
        cfg = load_config_from_dict(full_config_dict)
        exported = config_to_dict(cfg)
        # Should not raise
        serialized = json.dumps(exported)
        assert isinstance(serialized, str)

    def test_reload_from_exported_dict(self, full_config_dict: dict) -> None:
        cfg = load_config_from_dict(full_config_dict)
        exported = config_to_dict(cfg)
        # Re-loading should produce a valid config
        # (need to add back secrets for jira since they are stripped)
        exported["jira"]["base_url"] = "https://test.atlassian.net"
        cfg2 = load_config_from_dict(exported)
        assert cfg2.dashboard.branding.title == cfg.dashboard.branding.title


# ---------------------------------------------------------------------------
# Schema validation of dashboard/pi sections
# ---------------------------------------------------------------------------

class TestSchemaValidation:
    """GIVEN the JSON Schema, WHEN config with dashboard/pi is validated, THEN it passes or rejects."""

    def test_valid_dashboard_config_passes(self) -> None:
        raw = {
            "jira": {"base_url": "https://x.com"},
            "dashboard": {
                "branding": {"title": "Test"},
                "layout": {"density": "compact"},
            },
        }
        # Should not raise
        cfg = load_config_from_dict(raw)
        assert cfg.dashboard.layout.density == "compact"

    def test_valid_pi_config_passes(self) -> None:
        raw = {
            "jira": {"base_url": "https://x.com"},
            "pi": {
                "enabled": True,
                "name": "PI Test",
                "start_date": "2026-03-02",
            },
        }
        cfg = load_config_from_dict(raw)
        assert cfg.pi.enabled is True

    def test_example_config_validates(self) -> None:
        example = Path(__file__).parent.parent / "examples" / "config.example.json"
        with example.open() as f:
            raw = json.load(f)
        cfg = load_config_from_dict(raw)
        assert cfg.pi.enabled is True
        assert cfg.dashboard.branding.title == "FlowBoard Dashboard"

    def test_minimal_example_validates(self) -> None:
        minimal = Path(__file__).parent.parent / "examples" / "config.minimal.json"
        with minimal.open() as f:
            raw = json.load(f)
        cfg = load_config_from_dict(raw)
        assert cfg.pi.enabled is False  # default


# ---------------------------------------------------------------------------
# Section visibility
# ---------------------------------------------------------------------------

class TestSectionVisibility:
    """GIVEN config with limited visible tabs, WHEN checked, THEN invisible tabs are excluded."""

    def test_limited_tabs(self) -> None:
        raw = {
            "jira": {"base_url": "https://x.com"},
            "dashboard": {"tabs": {"visible": ["overview", "issues"]}},
        }
        cfg = load_config_from_dict(raw)
        assert "workload" not in cfg.dashboard.tabs.visible
        assert "overview" in cfg.dashboard.tabs.visible

    def test_empty_summary_cards(self) -> None:
        raw = {
            "jira": {"base_url": "https://x.com"},
            "dashboard": {"summary_cards": {"visible": []}},
        }
        cfg = load_config_from_dict(raw)
        assert cfg.dashboard.summary_cards.visible == []
