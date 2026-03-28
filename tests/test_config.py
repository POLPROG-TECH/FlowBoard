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
    """GIVEN a config dict, WHEN validated, THEN schema rules are enforced."""

    def test_minimal_valid_config(self, minimal_config_dict: dict) -> None:
        # GIVEN a config with only the required jira.base_url
        # WHEN loaded
        cfg = load_config_from_dict(minimal_config_dict)
        # THEN it succeeds with defaults applied
        assert cfg.jira.base_url == "https://test.atlassian.net"
        assert cfg.thresholds.overload_points == 20.0

    def test_full_config_loads_all_fields(self, full_config_dict: dict) -> None:
        cfg = load_config_from_dict(full_config_dict)
        assert cfg.jira.projects == ["PROJ"]
        assert cfg.jira.max_results == 50
        assert len(cfg.teams) == 2
        assert cfg.teams[0].key == "alpha"
        assert cfg.thresholds.overload_points == 15
        assert cfg.output.title == "Test Board"

    def test_missing_jira_section_raises(self) -> None:
        # GIVEN config without required 'jira' section
        # WHEN validated THEN it raises
        with pytest.raises(ConfigValidationError, match="jira"):
            load_config_from_dict({})

    def test_invalid_base_url_raises(self) -> None:
        with pytest.raises(ConfigValidationError):
            load_config_from_dict({"jira": {"base_url": "not-a-url"}})

    def test_extra_keys_rejected(self) -> None:
        with pytest.raises(ConfigValidationError):
            load_config_from_dict({
                "jira": {"base_url": "https://x.com"},
                "unknown_key": 123,
            })

    def test_env_override_token(self, minimal_config_dict: dict, monkeypatch: pytest.MonkeyPatch) -> None:
        # GIVEN env var FLOWBOARD_JIRA_TOKEN is set
        monkeypatch.setenv("FLOWBOARD_JIRA_TOKEN", "secret-tok")
        # WHEN loaded
        cfg = load_config_from_dict(minimal_config_dict)
        # THEN the token comes from env
        assert cfg.jira.auth_token == "secret-tok"

    def test_env_override_email(self, minimal_config_dict: dict, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FLOWBOARD_JIRA_EMAIL", "env@co.com")
        cfg = load_config_from_dict(minimal_config_dict)
        assert cfg.jira.auth_email == "env@co.com"


class TestConfigFromFile:
    """GIVEN a JSON config file on disk, WHEN loaded, THEN it parses correctly."""

    def test_load_example_config(self, tmp_path: Path) -> None:
        example = Path(__file__).parent.parent / "examples" / "config.example.json"
        cfg = load_config(example)
        assert cfg.jira.base_url == "https://yourcompany.atlassian.net"

    def test_file_not_found_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/config.json")
