"""Tests for infrastructure resilience — environment variable validation, retry
logic, authentication errors, secrets masking, date parsing, JSON serialization,
sprint deduplication, PI date normalization, request timeouts, and more.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from flowboard.domain.models import (
    BoardSnapshot,
    Issue,
    OverlapConflict,
    Person,
)
from flowboard.domain.pi import compute_pi_snapshot
from flowboard.i18n.translator import (
    get_locale,
    get_translator,
    reset_locale,
    set_locale,
)
from flowboard.infrastructure.config.loader import (
    _apply_env_overrides,
    load_config_from_dict,
)
from flowboard.presentation.html.components import conflict_list
from flowboard.shared.types import (
    RiskSeverity,
    StatusCategory,
)
from flowboard.shared.utils import parse_date, parse_datetime


def _person(aid: str = "u1", name: str = "Alice", team: str = "alpha") -> Person:
    return Person(account_id=aid, display_name=name, team=team)


def _issue(
    key: str = "T-1",
    sp: float = 5.0,
    status_cat: StatusCategory = StatusCategory.TODO,
    assignee: Person | None = None,
    created: datetime | None = None,
) -> Issue:
    return Issue(
        key=key,
        summary=f"Issue {key}",
        status_category=status_cat,
        assignee=assignee,
        story_points=sp,
        created=created or datetime(2026, 3, 1, tzinfo=UTC),
    )


# ====================================================================
# Env var overrides validated (empty/whitespace rejected)
# ====================================================================


class TestEnvVarOverridesValidated:
    def test_empty_string_env_var_not_applied(self):
        with patch.dict(os.environ, {"FLOWBOARD_JIRA_URL": ""}):
            raw = {"jira": {"base_url": "https://valid.example.com"}}
            result = _apply_env_overrides(raw)
            assert result["jira"]["base_url"] == "https://valid.example.com"

    def test_whitespace_only_env_var_not_applied(self):
        with patch.dict(os.environ, {"FLOWBOARD_JIRA_URL": "   "}):
            raw = {"jira": {"base_url": "https://valid.example.com"}}
            result = _apply_env_overrides(raw)
            assert result["jira"]["base_url"] == "https://valid.example.com"

    def test_valid_env_var_is_applied(self):
        with patch.dict(os.environ, {"FLOWBOARD_JIRA_URL": "https://new.example.com"}):
            raw = {"jira": {"base_url": "https://old.example.com"}}
            result = _apply_env_overrides(raw)
            assert result["jira"]["base_url"] == "https://new.example.com"

    def test_url_trailing_slash_stripped(self):
        with patch.dict(os.environ, {"FLOWBOARD_JIRA_URL": "https://new.example.com/"}):
            raw = {"jira": {}}
            result = _apply_env_overrides(raw)
            assert result["jira"]["base_url"] == "https://new.example.com"


# ====================================================================
# Retry transient network errors
# ====================================================================


class TestRetryTransientErrors:
    def test_backoff_codes_include_502_504(self):
        from flowboard.infrastructure.jira.client import _BACKOFF_CODES

        assert 502 in _BACKOFF_CODES
        assert 504 in _BACKOFF_CODES
        assert 429 in _BACKOFF_CODES
        assert 503 in _BACKOFF_CODES

    def test_request_timeout_is_set(self):
        from flowboard.infrastructure.jira.client import _REQUEST_TIMEOUT

        assert _REQUEST_TIMEOUT == (10, 60)

    def test_max_backoff_ceiling_exists(self):
        from flowboard.infrastructure.jira.client import _MAX_BACKOFF_SECONDS

        assert _MAX_BACKOFF_SECONDS == 30


# ====================================================================
# Auth error distinguished in CLI generate command
# ====================================================================


class TestAuthErrorDistinguished:
    def test_generate_catches_auth_error(self):
        """The generate command must import JiraAuthError for specific handling."""
        import inspect

        from flowboard.cli.main import generate

        src = inspect.getsource(generate)
        assert "JiraAuthError" in src

    def test_auth_error_message_is_actionable(self):
        import inspect

        from flowboard.cli.main import generate

        src = inspect.getsource(generate)
        assert "Authentication failed" in src or "auth" in src.lower()


# ====================================================================
# Epic key extraction handles dict, list, None
# ====================================================================


class TestEpicKeyExtraction:
    def _build_normalizer(self):
        from flowboard.infrastructure.jira.normalizer import JiraNormalizer

        cfg = load_config_from_dict(
            {
                "jira": {"base_url": "https://test.atlassian.net"},
            }
        )
        return JiraNormalizer(cfg)

    def test_string_epic_key(self):
        normalizer = self._build_normalizer()
        raw = {
            "key": "T-1",
            "fields": {
                "issuetype": {"name": "Story"},
                "status": {"name": "To Do"},
                "customfield_10014": "EPIC-1",
            },
        }
        issue = normalizer.normalize_issue(raw)
        assert issue.epic_key == "EPIC-1"

    def test_dict_epic_key(self):
        normalizer = self._build_normalizer()
        raw = {
            "key": "T-2",
            "fields": {
                "issuetype": {"name": "Story"},
                "status": {"name": "To Do"},
                "customfield_10014": {"key": "EPIC-2", "name": "My Epic"},
            },
        }
        issue = normalizer.normalize_issue(raw)
        assert issue.epic_key == "EPIC-2"

    def test_list_epic_key(self):
        normalizer = self._build_normalizer()
        raw = {
            "key": "T-3",
            "fields": {
                "issuetype": {"name": "Story"},
                "status": {"name": "To Do"},
                "customfield_10014": [{"key": "EPIC-3"}],
            },
        }
        issue = normalizer.normalize_issue(raw)
        assert issue.epic_key == "EPIC-3"

    def test_none_epic_key(self):
        normalizer = self._build_normalizer()
        raw = {
            "key": "T-4",
            "fields": {
                "issuetype": {"name": "Story"},
                "status": {"name": "To Do"},
                "customfield_10014": None,
            },
        }
        issue = normalizer.normalize_issue(raw)
        assert issue.epic_key == ""

    def test_empty_list_epic_key(self):
        normalizer = self._build_normalizer()
        raw = {
            "key": "T-5",
            "fields": {
                "issuetype": {"name": "Story"},
                "status": {"name": "To Do"},
                "customfield_10014": [],
            },
        }
        issue = normalizer.normalize_issue(raw)
        assert issue.epic_key == ""


# ====================================================================
# Template pre-flight check
# ====================================================================


class TestTemplatePreFlightCheck:
    def test_build_env_raises_if_dir_missing(self, tmp_path):
        from flowboard.presentation.html import renderer

        original = renderer._TEMPLATE_DIR
        renderer._TEMPLATE_DIR = tmp_path / "nonexistent"
        try:
            with pytest.raises(FileNotFoundError, match="Template directory not found"):
                renderer._build_env()
        finally:
            renderer._TEMPLATE_DIR = original

    def test_build_env_succeeds_with_valid_dir(self):
        from flowboard.presentation.html.renderer import _build_env

        env = _build_env()
        assert env is not None


# ====================================================================
# Secrets masked in validate-config output
# ====================================================================


class TestSecretsMasked:
    def test_describe_config_masks_token(self):
        from flowboard.application.services import describe_config

        cfg = load_config_from_dict(
            {
                "jira": {
                    "base_url": "https://test.atlassian.net",
                    "auth_token": "super-secret-token-12345",
                    "auth_email": "user@example.com",
                },
            }
        )
        info = describe_config(cfg)
        assert "super-secret-token-12345" not in info["auth_token"]
        assert "****" in info["auth_token"] or info["auth_token"].startswith("*")


# ====================================================================
# Empty Jira response logs warning
# ====================================================================


class TestEmptyJiraResponseWarning:
    def test_empty_issues_logs_warning(self, caplog):
        from flowboard.application.orchestrator import analyse_raw_payload

        cfg = load_config_from_dict(
            {
                "jira": {"base_url": "https://test.atlassian.net"},
            }
        )
        with caplog.at_level(logging.WARNING, logger="flowboard.application.orchestrator"):
            analyse_raw_payload({"issues": [], "sprints": []}, cfg)
        assert any("No issues returned" in msg for msg in caplog.messages)


# ====================================================================
# Date parsing logs warning on failure
# ====================================================================


class TestDateParsingWarning:
    def test_invalid_date_logs_warning(self, caplog):
        with caplog.at_level(logging.WARNING, logger="flowboard.shared.utils"):
            result = parse_date("2026-13-45")
        assert result is None
        assert any("Failed to parse date" in msg for msg in caplog.messages)

    def test_invalid_datetime_logs_warning(self, caplog):
        with caplog.at_level(logging.WARNING, logger="flowboard.shared.utils"):
            result = parse_datetime("not-a-date")
        assert result is None
        assert any("Failed to parse datetime" in msg for msg in caplog.messages)

    def test_empty_string_no_warning(self, caplog):
        with caplog.at_level(logging.WARNING, logger="flowboard.shared.utils"):
            assert parse_date("") is None
            assert parse_date(None) is None
        assert not any("Failed to parse" in msg for msg in caplog.messages)


# ====================================================================
# Strict JSON serializer
# ====================================================================


class TestStrictJsonSerializer:
    def test_datetime_serialized_as_iso(self):
        from flowboard.presentation.html.renderer import _json_dumps

        data = {"ts": datetime(2026, 3, 18, 12, 0)}
        result = _json_dumps(data)
        assert "2026-03-18T12:00:00" in result

    def test_date_serialized_as_iso(self):
        from flowboard.presentation.html.renderer import _json_dumps

        data = {"d": date(2026, 3, 18)}
        result = _json_dumps(data)
        assert "2026-03-18" in result

    def test_domain_object_serializes_as_dict(self):
        from flowboard.presentation.html.renderer import _json_dumps

        data = {"person": _person()}
        result = _json_dumps(data)
        assert isinstance(result, str)
        assert "person" in result


# ====================================================================
# Sprint dedup doesn't drop id=0
# ====================================================================


class TestSprintDedupIdZero:
    def test_sprint_id_zero_not_dropped(self):
        from flowboard.infrastructure.jira.client import JiraClient
        from flowboard.infrastructure.jira.connector import JiraConnector

        client = MagicMock(spec=JiraClient)
        client.get_sprints.return_value = [
            {"id": 0, "name": "Sprint Zero", "state": "active"},
            {"id": 1, "name": "Sprint One", "state": "active"},
        ]
        cfg = load_config_from_dict(
            {
                "jira": {"base_url": "https://test.atlassian.net", "boards": [1]},
            }
        )
        connector = JiraConnector(client, cfg)
        sprints = connector._fetch_sprints()
        ids = [s.get("id") for s in sprints]
        assert 0 in ids
        assert 1 in ids


# ====================================================================
# PI date format normalization
# ====================================================================


class TestPIDateNormalization:
    def test_single_digit_month_accepted(self):
        snap = compute_pi_snapshot("PI 1", "2026-3-2", today=date(2026, 3, 18))
        assert snap.start_date == date(2026, 3, 2)

    def test_single_digit_day_accepted(self):
        snap = compute_pi_snapshot("PI 1", "2026-03-2", today=date(2026, 3, 18))
        assert snap.start_date == date(2026, 3, 2)

    def test_standard_format_still_works(self):
        snap = compute_pi_snapshot("PI 1", "2026-03-02", today=date(2026, 3, 18))
        assert snap.start_date == date(2026, 3, 2)

    def test_invalid_date_raises(self):
        with pytest.raises(ValueError, match="Invalid PI start date"):
            compute_pi_snapshot("PI 1", "not-a-date", today=date(2026, 3, 18))


# ====================================================================
# Working day validation
# ====================================================================


class TestWorkingDayValidation:
    def test_invalid_weekday_zero_raises(self):
        with pytest.raises(ValueError, match="Invalid working day"):
            compute_pi_snapshot(
                "PI 1", "2026-03-02", working_days=[0, 1, 2], today=date(2026, 3, 18)
            )

    def test_invalid_weekday_eight_raises(self):
        with pytest.raises(ValueError, match="Invalid working day"):
            compute_pi_snapshot(
                "PI 1", "2026-03-02", working_days=[1, 2, 8], today=date(2026, 3, 18)
            )

    def test_valid_weekdays_accepted(self):
        snap = compute_pi_snapshot(
            "PI 1", "2026-03-02", working_days=[1, 2, 3, 4, 5], today=date(2026, 3, 18)
        )
        assert snap.name == "PI 1"


# ====================================================================
# conflict_list uses severity directly
# ====================================================================


class TestConflictSeverityDirect:
    def test_conflict_list_no_redundant_wrapping(self):
        import inspect

        src = inspect.getsource(conflict_list)
        assert "RiskSeverity(c.severity)" not in src

    def test_conflict_list_renders(self):
        t = get_translator("en")
        conflict = OverlapConflict(
            category="resource_contention",
            severity=RiskSeverity.HIGH,
            description="Test conflict",
            recommendation="Fix it",
        )
        html = conflict_list([conflict], t=t)
        assert "Test conflict" in html
        assert "conflict-item" in html


# ====================================================================
# Demo fixture path is robust
# ====================================================================


class TestDemoFixturePath:
    def test_locate_demo_fixture_finds_file(self):
        from flowboard.cli.main import _locate_demo_fixture

        path = _locate_demo_fixture()
        assert path.exists()
        assert path.name == "mock_jira_data.json"


# ====================================================================
# Schema path resolution is robust
# ====================================================================


class TestSchemaPathResolution:
    def test_schema_loads_successfully(self):
        from flowboard.infrastructure.config.validator import _load_schema

        schema = _load_schema()
        assert "properties" in schema or "$schema" in schema or "type" in schema

    def test_find_schema_path_finds_file(self):
        from flowboard.infrastructure.config.validator import _find_schema_path

        path = _find_schema_path()
        assert path.exists()


# ====================================================================
# pi_snapshot typed correctly (not object)
# ====================================================================


class TestPISnapshotTyping:
    def test_pi_snapshot_annotation_is_not_object(self):
        import inspect

        src = inspect.getsource(BoardSnapshot)
        assert "object | None" not in src
        assert "pi_snapshot" in src


# ====================================================================
# Request timeout configured
# ====================================================================


class TestRequestTimeout:
    def test_request_uses_timeout(self):
        import inspect

        from flowboard.infrastructure.jira.client import JiraClient

        src = inspect.getsource(JiraClient._request)
        assert "timeout" in src


# ====================================================================
# Package data includes explicit template patterns
# ====================================================================


class TestPackageData:
    def test_pyproject_includes_templates(self):
        pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
        content = pyproject_path.read_text()
        assert "presentation/html/templates/*.html" in content
        assert "presentation/html/templates/**/*.html" in content


# ====================================================================
# verify_jira_connection uses context manager
# ====================================================================


class TestVerifyUsesContextManager:
    def test_verify_function_uses_with_statement(self):
        import inspect

        from flowboard.application.services import verify_jira_connection

        src = inspect.getsource(verify_jira_connection)
        assert "with JiraClient" in src


# ====================================================================
# Thread-local locale cleanup
# ====================================================================


class TestLocaleCleanup:
    def test_reset_locale_resets_to_default(self):
        set_locale("pl")
        assert get_locale() == "pl"
        reset_locale()
        assert get_locale() == "en"

    def test_reset_locale_works_across_calls(self):
        set_locale("pl")
        reset_locale()
        set_locale("pl")
        reset_locale()
        assert get_locale() == "en"


# ====================================================================
# __all__ exports defined
# ====================================================================


class TestAllExports:
    def test_flowboard_init_has_all(self):
        import flowboard

        assert hasattr(flowboard, "__all__")

    def test_i18n_init_has_all(self):
        import flowboard.i18n

        assert hasattr(flowboard.i18n, "__all__")
        assert "reset_locale" in flowboard.i18n.__all__


# ====================================================================
# Structured logging
# ====================================================================


class TestStructuredLogging:
    def test_setup_logging_produces_json_format(self):
        import inspect

        from flowboard.cli.main import _JsonFormatter

        src = inspect.getsource(_JsonFormatter)
        assert '"time"' in src or "time" in src
        assert '"message"' in src or "message" in src


# ====================================================================
# Output directory creation
# ====================================================================


class TestOutputDirectoryCreation:
    def test_render_creates_output_dir(self):
        """Orchestrator._render must create parent directories."""
        import inspect

        from flowboard.application.orchestrator import Orchestrator

        src = inspect.getsource(Orchestrator._render)
        assert "mkdir" in src
        assert "parents=True" in src
        assert "exist_ok=True" in src


# ====================================================================
# Backoff ceiling and jitter
# ====================================================================


class TestBackoffCeilingJitter:
    def test_backoff_ceiling_constant(self):
        from flowboard.infrastructure.jira.client import _MAX_BACKOFF_SECONDS

        assert _MAX_BACKOFF_SECONDS <= 60  # reasonable upper bound

    def test_random_import_for_jitter(self):
        import inspect

        from flowboard.infrastructure.jira import client

        src = inspect.getsource(client)
        assert "random" in src


# ====================================================================
# age_days timezone-safe
# ====================================================================


class TestAgeDaysTimezoneSafe:
    def test_age_days_utc_aware(self):
        issue = _issue(created=datetime(2026, 3, 1, tzinfo=UTC))
        age = issue.age_days
        assert age is not None
        assert age >= 0

    def test_age_days_naive_datetime(self):
        issue = _issue(created=datetime(2026, 3, 1))
        age = issue.age_days
        assert age is not None
        assert age >= 0

    def test_age_days_none_created(self):
        issue = _issue()
        issue.created = None
        assert issue.age_days is None

    def test_age_days_resolved(self):
        issue = _issue(created=datetime(2026, 3, 1, tzinfo=UTC))
        issue.resolved = datetime(2026, 3, 5, tzinfo=UTC)
        assert issue.age_days == 4

    def test_age_days_never_negative(self):
        """Even if created is in the future, age_days should be 0, not negative."""
        issue = _issue(created=datetime(2099, 1, 1, tzinfo=UTC))
        assert issue.age_days == 0
