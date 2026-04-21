"""Tests for configuration loading, validation, and schema enforcement."""

from __future__ import annotations

from pathlib import Path

import pytest

from flowboard.infrastructure.config.loader import (
    load_config,
    load_config_from_dict,
)
from flowboard.infrastructure.config.validator import ConfigValidationError


class TestConfigValidation:
    """Tests for config validation."""

    """GIVEN config validation and the scenario: minimal valid config"""
    def test_minimal_valid_config(self, minimal_config_dict: dict) -> None:
        """WHEN the code under test is exercised for: minimal valid config"""
        cfg = load_config_from_dict(minimal_config_dict)

        """THEN the expected behaviour holds: minimal valid config"""
        assert cfg.jira.base_url == "https://test.atlassian.net"
        assert cfg.thresholds.overload_points == 20.0

    """GIVEN config validation and the scenario: full config loads all fields"""
    def test_full_config_loads_all_fields(self, full_config_dict: dict) -> None:
        """WHEN the code under test is exercised for: full config loads all fields"""
        cfg = load_config_from_dict(full_config_dict)

        """THEN the expected behaviour holds: full config loads all fields"""
        assert cfg.jira.projects == ["PROJ"]
        assert cfg.jira.max_results == 50
        assert len(cfg.teams) == 2
        assert cfg.teams[0].key == "alpha"
        assert cfg.thresholds.overload_points == 15
        assert cfg.output.title == "Test Board"

    """GIVEN config validation and the scenario: missing jira section raises"""
    def test_missing_jira_section_raises(self) -> None:
        """WHEN the code under test is exercised for: missing jira section raises"""
        with pytest.raises(ConfigValidationError, match="jira"):
            load_config_from_dict({})

    """GIVEN config validation and the scenario: invalid base url raises"""
    def test_invalid_base_url_raises(self) -> None:
        """WHEN the code under test is exercised for: invalid base url raises"""
        with pytest.raises(ConfigValidationError):
            load_config_from_dict({"jira": {"base_url": "not-a-url"}})

    """GIVEN config validation and the scenario: extra keys rejected"""
    def test_extra_keys_rejected(self) -> None:
        """WHEN the code under test is exercised for: extra keys rejected"""
        with pytest.raises(ConfigValidationError):
            load_config_from_dict(
                {
                    "jira": {"base_url": "https://x.com"},
                    "unknown_key": 123,
                }
            )

    """GIVEN config validation and the scenario: env override token"""
    def test_env_override_token(
        self, minimal_config_dict: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """WHEN the code under test is exercised for: env override token"""
        monkeypatch.setenv("FLOWBOARD_JIRA_TOKEN", "secret-tok")
        cfg = load_config_from_dict(minimal_config_dict)

        """THEN the expected behaviour holds: env override token"""
        assert cfg.jira.auth_token == "secret-tok"

    """GIVEN config validation and the scenario: env override email"""
    def test_env_override_email(
        self, minimal_config_dict: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """WHEN the code under test is exercised for: env override email"""
        monkeypatch.setenv("FLOWBOARD_JIRA_EMAIL", "env@co.com")
        cfg = load_config_from_dict(minimal_config_dict)

        """THEN the expected behaviour holds: env override email"""
        assert cfg.jira.auth_email == "env@co.com"


class TestConfigFromFile:
    """Tests for config from file."""

    """GIVEN config from file and the scenario: load example config"""
    def test_load_example_config(self, tmp_path: Path) -> None:
        """WHEN the code under test is exercised for: load example config"""
        example = Path(__file__).parent.parent / "examples" / "config.example.json"
        cfg = load_config(example)

        """THEN the expected behaviour holds: load example config"""
        assert cfg.jira.base_url == "https://yourcompany.atlassian.net"

    """GIVEN config from file and the scenario: file not found raises"""
    def test_file_not_found_raises(self) -> None:
        """WHEN the code under test is exercised for: file not found raises"""
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/config.json")
