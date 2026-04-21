"""Tests for dashboard configuration - loading, validation, round-trip,
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
    """Tests for dashboard config defaults."""

    """GIVEN dashboard config defaults and the scenario: dashboard created with defaults"""
    def test_dashboard_created_with_defaults(self, minimal_config_dict: dict) -> None:
        """WHEN the code under test is exercised for: dashboard created with defaults"""
        cfg = load_config_from_dict(minimal_config_dict)

        """THEN the expected behaviour holds: dashboard created with defaults"""
        assert isinstance(cfg.dashboard, DashboardConfig)

    """GIVEN dashboard config defaults and the scenario: branding title defaults to output title"""
    def test_branding_title_defaults_to_output_title(self, minimal_config_dict: dict) -> None:
        """WHEN the code under test is exercised for: branding title defaults to output title"""
        cfg = load_config_from_dict(minimal_config_dict)
        # When no dashboard.branding.title, falls back to output.title

        """THEN the expected behaviour holds: branding title defaults to output title"""
        assert cfg.dashboard.branding.title == cfg.output.title

    """GIVEN dashboard config defaults and the scenario: default tabs include all"""
    def test_default_tabs_include_all(self, minimal_config_dict: dict) -> None:
        """WHEN the code under test is exercised for: default tabs include all"""
        cfg = load_config_from_dict(minimal_config_dict)
        expected = ["overview", "workload", "sprints", "timeline", "pi", "insights", "issues"]

        """THEN the expected behaviour holds: default tabs include all"""
        assert cfg.dashboard.tabs.visible == expected

    """GIVEN dashboard config defaults and the scenario: default layout is comfortable"""
    def test_default_layout_is_comfortable(self, minimal_config_dict: dict) -> None:
        """WHEN the code under test is exercised for: default layout is comfortable"""
        cfg = load_config_from_dict(minimal_config_dict)

        """THEN the expected behaviour holds: default layout is comfortable"""
        assert cfg.dashboard.layout.density == "comfortable"

    """GIVEN dashboard config defaults and the scenario: default charts all enabled"""
    def test_default_charts_all_enabled(self, minimal_config_dict: dict) -> None:
        """WHEN the code under test is exercised for: default charts all enabled"""
        cfg = load_config_from_dict(minimal_config_dict)

        """THEN the expected behaviour holds: default charts all enabled"""
        assert cfg.dashboard.charts.enabled is True
        assert cfg.dashboard.charts.status_distribution is True

    """GIVEN dashboard config defaults and the scenario: default summary cards"""
    def test_default_summary_cards(self, minimal_config_dict: dict) -> None:
        """WHEN the code under test is exercised for: default summary cards"""
        cfg = load_config_from_dict(minimal_config_dict)

        """THEN the expected behaviour holds: default summary cards"""
        assert "total_issues" in cfg.dashboard.summary_cards.visible
        assert "blocked" in cfg.dashboard.summary_cards.visible


# ---------------------------------------------------------------------------
# PI config defaults
# ---------------------------------------------------------------------------


class TestPIConfigDefaults:
    """Tests for p i config defaults."""

    """GIVEN p i config defaults and the scenario: pi disabled by default"""
    def test_pi_disabled_by_default(self, minimal_config_dict: dict) -> None:
        """WHEN the code under test is exercised for: pi disabled by default"""
        cfg = load_config_from_dict(minimal_config_dict)

        """THEN the expected behaviour holds: pi disabled by default"""
        assert isinstance(cfg.pi, PIConfig)
        assert cfg.pi.enabled is False

    """GIVEN p i config defaults and the scenario: pi default sprints per pi"""
    def test_pi_default_sprints_per_pi(self, minimal_config_dict: dict) -> None:
        """WHEN the code under test is exercised for: pi default sprints per pi"""
        cfg = load_config_from_dict(minimal_config_dict)

        """THEN the expected behaviour holds: pi default sprints per pi"""
        assert cfg.pi.sprints_per_pi == 5

    """GIVEN p i config defaults and the scenario: pi default sprint length"""
    def test_pi_default_sprint_length(self, minimal_config_dict: dict) -> None:
        """WHEN the code under test is exercised for: pi default sprint length"""
        cfg = load_config_from_dict(minimal_config_dict)

        """THEN the expected behaviour holds: pi default sprint length"""
        assert cfg.pi.sprint_length_days == 10

    """GIVEN p i config defaults and the scenario: pi default working days"""
    def test_pi_default_working_days(self, minimal_config_dict: dict) -> None:
        """WHEN the code under test is exercised for: pi default working days"""
        cfg = load_config_from_dict(minimal_config_dict)

        """THEN the expected behaviour holds: pi default working days"""
        assert cfg.pi.working_days == [1, 2, 3, 4, 5]


# ---------------------------------------------------------------------------
# Dashboard config from dict
# ---------------------------------------------------------------------------


class TestDashboardConfigFromDict:
    """Tests for dashboard config from dict."""

    """GIVEN dashboard config from dict and the scenario: custom branding"""
    def test_custom_branding(self) -> None:
        """WHEN the code under test is exercised for: custom branding"""
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

        """THEN the expected behaviour holds: custom branding"""
        assert cfg.dashboard.branding.title == "My Board"
        assert cfg.dashboard.branding.subtitle == "Custom subtitle"
        assert cfg.dashboard.branding.primary_color == "#FF0000"

    """GIVEN dashboard config from dict and the scenario: custom tabs"""
    def test_custom_tabs(self) -> None:
        """WHEN the code under test is exercised for: custom tabs"""
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

        """THEN the expected behaviour holds: custom tabs"""
        assert cfg.dashboard.tabs.visible == ["overview", "workload"]
        assert cfg.dashboard.tabs.default_tab == "workload"

    """GIVEN dashboard config from dict and the scenario: charts partially disabled"""
    def test_charts_partially_disabled(self) -> None:
        """WHEN the code under test is exercised for: charts partially disabled"""
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

        """THEN the expected behaviour holds: charts partially disabled"""
        assert cfg.dashboard.charts.enabled is True
        assert cfg.dashboard.charts.risk_severity is False
        assert cfg.dashboard.charts.status_distribution is True  # default

    """GIVEN dashboard config from dict and the scenario: custom tables"""
    def test_custom_tables(self) -> None:
        """WHEN the code under test is exercised for: custom tables"""
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

        """THEN the expected behaviour holds: custom tables"""
        assert cfg.dashboard.tables.issues_columns == ["key", "summary", "status"]
        assert cfg.dashboard.tables.max_rows == 50
        assert cfg.dashboard.tables.sort_direction == "desc"


# ---------------------------------------------------------------------------
# PI config from dict
# ---------------------------------------------------------------------------


class TestPIConfigFromDict:
    """GIVEN p i config from dict and the scenario: enabled pi with start date"""
    def test_enabled_pi_with_start_date(self) -> None:
        """WHEN the code under test is exercised for: enabled pi with start date"""
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

        """THEN the expected behaviour holds: enabled pi with start date"""
        assert cfg.pi.enabled is True
        assert cfg.pi.name == "PI 2026.2"
        assert cfg.pi.start_date == "2026-06-01"
        assert cfg.pi.sprints_per_pi == 4
        assert cfg.pi.sprint_length_days == 8

    """GIVEN p i config from dict and the scenario: custom working days"""
    def test_custom_working_days(self) -> None:
        """WHEN the code under test is exercised for: custom working days"""
        raw = {
            "jira": {"base_url": "https://x.com"},
            "pi": {"working_days": [1, 2, 3, 4]},
        }
        cfg = load_config_from_dict(raw)

        """THEN the expected behaviour holds: custom working days"""
        assert cfg.pi.working_days == [1, 2, 3, 4]


# ---------------------------------------------------------------------------
# Round-trip: config_to_dict
# ---------------------------------------------------------------------------


class TestConfigRoundTrip:
    """Tests for config round trip."""

    """GIVEN config round trip and the scenario: round trip preserves structure"""
    def test_round_trip_preserves_structure(self, full_config_dict: dict) -> None:
        """WHEN the code under test is exercised for: round trip preserves structure"""
        cfg = load_config_from_dict(full_config_dict)
        exported = config_to_dict(cfg)

        """THEN the expected behaviour holds: round trip preserves structure"""
        assert isinstance(exported, dict)
        assert "jira" in exported
        assert "dashboard" in exported
        assert "pi" in exported

    """GIVEN config round trip and the scenario: round trip strips secrets"""
    def test_round_trip_strips_secrets(self, full_config_dict: dict) -> None:
        """WHEN the code under test is exercised for: round trip strips secrets"""
        cfg = load_config_from_dict(full_config_dict)
        exported = config_to_dict(cfg)
        jira = exported["jira"]

        """THEN the expected behaviour holds: round trip strips secrets"""
        assert "auth_token" not in jira
        assert "auth_email" not in jira

    """GIVEN config round trip and the scenario: round trip dashboard branding"""
    def test_round_trip_dashboard_branding(self) -> None:
        """WHEN the code under test is exercised for: round trip dashboard branding"""
        raw = {
            "jira": {"base_url": "https://x.com"},
            "dashboard": {"branding": {"title": "Round Trip Test"}},
        }
        cfg = load_config_from_dict(raw)
        exported = config_to_dict(cfg)

        """THEN the expected behaviour holds: round trip dashboard branding"""
        assert exported["dashboard"]["branding"]["title"] == "Round Trip Test"

    """GIVEN config round trip and the scenario: round trip pi"""
    def test_round_trip_pi(self) -> None:
        """WHEN the code under test is exercised for: round trip pi"""
        raw = {
            "jira": {"base_url": "https://x.com"},
            "pi": {"enabled": True, "name": "PI X", "start_date": "2026-01-05"},
        }
        cfg = load_config_from_dict(raw)
        exported = config_to_dict(cfg)

        """THEN the expected behaviour holds: round trip pi"""
        assert exported["pi"]["enabled"] is True
        assert exported["pi"]["name"] == "PI X"

    """GIVEN config round trip and the scenario: round trip is json serializable"""
    def test_round_trip_is_json_serializable(self, full_config_dict: dict) -> None:
        """WHEN the code under test is exercised for: round trip is json serializable"""
        cfg = load_config_from_dict(full_config_dict)
        exported = config_to_dict(cfg)
        # Should not raise
        serialized = json.dumps(exported)

        """THEN the expected behaviour holds: round trip is json serializable"""
        assert isinstance(serialized, str)

    """GIVEN config round trip and the scenario: reload from exported dict"""
    def test_reload_from_exported_dict(self, full_config_dict: dict) -> None:
        """WHEN the code under test is exercised for: reload from exported dict"""
        cfg = load_config_from_dict(full_config_dict)
        exported = config_to_dict(cfg)
        # Re-loading should produce a valid config
        # (need to add back secrets for jira since they are stripped)
        exported["jira"]["base_url"] = "https://test.atlassian.net"
        cfg2 = load_config_from_dict(exported)

        """THEN the expected behaviour holds: reload from exported dict"""
        assert cfg2.dashboard.branding.title == cfg.dashboard.branding.title


# ---------------------------------------------------------------------------
# Schema validation of dashboard/pi sections
# ---------------------------------------------------------------------------


class TestSchemaValidation:
    """Tests for schema validation."""

    """GIVEN schema validation and the scenario: valid dashboard config passes"""
    def test_valid_dashboard_config_passes(self) -> None:
        """WHEN the code under test is exercised for: valid dashboard config passes"""
        raw = {
            "jira": {"base_url": "https://x.com"},
            "dashboard": {
                "branding": {"title": "Test"},
                "layout": {"density": "compact"},
            },
        }
        # Should not raise
        cfg = load_config_from_dict(raw)

        """THEN the expected behaviour holds: valid dashboard config passes"""
        assert cfg.dashboard.layout.density == "compact"

    """GIVEN schema validation and the scenario: valid pi config passes"""
    def test_valid_pi_config_passes(self) -> None:
        """WHEN the code under test is exercised for: valid pi config passes"""
        raw = {
            "jira": {"base_url": "https://x.com"},
            "pi": {
                "enabled": True,
                "name": "PI Test",
                "start_date": "2026-03-02",
            },
        }
        cfg = load_config_from_dict(raw)

        """THEN the expected behaviour holds: valid pi config passes"""
        assert cfg.pi.enabled is True

    """GIVEN schema validation and the scenario: example config validates"""
    def test_example_config_validates(self) -> None:
        """WHEN the code under test is exercised for: example config validates"""
        example = Path(__file__).parent.parent / "examples" / "config.example.json"
        with example.open() as f:
            raw = json.load(f)
        cfg = load_config_from_dict(raw)

        """THEN the expected behaviour holds: example config validates"""
        assert cfg.pi.enabled is True
        assert cfg.dashboard.branding.title == "FlowBoard Dashboard"

    """GIVEN schema validation and the scenario: minimal example validates"""
    def test_minimal_example_validates(self) -> None:
        """WHEN the code under test is exercised for: minimal example validates"""
        minimal = Path(__file__).parent.parent / "examples" / "config.minimal.json"
        with minimal.open() as f:
            raw = json.load(f)
        cfg = load_config_from_dict(raw)

        """THEN the expected behaviour holds: minimal example validates"""
        assert cfg.pi.enabled is False  # default


# ---------------------------------------------------------------------------
# Section visibility
# ---------------------------------------------------------------------------


class TestSectionVisibility:
    """Tests for section visibility."""

    """GIVEN section visibility and the scenario: limited tabs"""
    def test_limited_tabs(self) -> None:
        """WHEN the code under test is exercised for: limited tabs"""
        raw = {
            "jira": {"base_url": "https://x.com"},
            "dashboard": {"tabs": {"visible": ["overview", "issues"]}},
        }
        cfg = load_config_from_dict(raw)

        """THEN the expected behaviour holds: limited tabs"""
        assert "workload" not in cfg.dashboard.tabs.visible
        assert "overview" in cfg.dashboard.tabs.visible

    """GIVEN section visibility and the scenario: empty summary cards"""
    def test_empty_summary_cards(self) -> None:
        """WHEN the code under test is exercised for: empty summary cards"""
        raw = {
            "jira": {"base_url": "https://x.com"},
            "dashboard": {"summary_cards": {"visible": []}},
        }
        cfg = load_config_from_dict(raw)

        """THEN the expected behaviour holds: empty summary cards"""
        assert cfg.dashboard.summary_cards.visible == []
