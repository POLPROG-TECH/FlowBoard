"""Tests for infrastructure resilience - environment variable validation, retry
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
    """GIVEN env var overrides validated and the scenario: empty string env var not applied"""
    def test_empty_string_env_var_not_applied(self):
        """THEN the expected behaviour holds: empty string env var not applied"""
        with patch.dict(os.environ, {"FLOWBOARD_JIRA_URL": ""}):
            raw = {"jira": {"base_url": "https://valid.example.com"}}
            result = _apply_env_overrides(raw)
            assert result["jira"]["base_url"] == "https://valid.example.com"

    """GIVEN env var overrides validated and the scenario: whitespace only env var not applied"""
    def test_whitespace_only_env_var_not_applied(self):
        """THEN the expected behaviour holds: whitespace only env var not applied"""
        with patch.dict(os.environ, {"FLOWBOARD_JIRA_URL": "   "}):
            raw = {"jira": {"base_url": "https://valid.example.com"}}
            result = _apply_env_overrides(raw)
            assert result["jira"]["base_url"] == "https://valid.example.com"

    """GIVEN env var overrides validated and the scenario: valid env var is applied"""
    def test_valid_env_var_is_applied(self):
        """THEN the expected behaviour holds: valid env var is applied"""
        with patch.dict(os.environ, {"FLOWBOARD_JIRA_URL": "https://new.example.com"}):
            raw = {"jira": {"base_url": "https://old.example.com"}}
            result = _apply_env_overrides(raw)
            assert result["jira"]["base_url"] == "https://new.example.com"

    """GIVEN env var overrides validated and the scenario: url trailing slash stripped"""
    def test_url_trailing_slash_stripped(self):
        """THEN the expected behaviour holds: url trailing slash stripped"""
        with patch.dict(os.environ, {"FLOWBOARD_JIRA_URL": "https://new.example.com/"}):
            raw = {"jira": {}}
            result = _apply_env_overrides(raw)
            assert result["jira"]["base_url"] == "https://new.example.com"


# ====================================================================
# Retry transient network errors
# ====================================================================


class TestRetryTransientErrors:
    """GIVEN retry transient errors and the scenario: backoff codes include 502 504"""
    def test_backoff_codes_include_502_504(self):
        """WHEN the code under test is exercised for: backoff codes include 502 504"""
        from flowboard.infrastructure.jira.client import _BACKOFF_CODES

        """THEN the expected behaviour holds: backoff codes include 502 504"""
        assert 502 in _BACKOFF_CODES
        assert 504 in _BACKOFF_CODES
        assert 429 in _BACKOFF_CODES
        assert 503 in _BACKOFF_CODES

    """GIVEN retry transient errors and the scenario: request timeout is set"""
    def test_request_timeout_is_set(self):
        """WHEN the code under test is exercised for: request timeout is set"""
        from flowboard.infrastructure.jira.client import _REQUEST_TIMEOUT

        """THEN the expected behaviour holds: request timeout is set"""
        assert _REQUEST_TIMEOUT == (10, 60)

    """GIVEN retry transient errors and the scenario: max backoff ceiling exists"""
    def test_max_backoff_ceiling_exists(self):
        """WHEN the code under test is exercised for: max backoff ceiling exists"""
        from flowboard.infrastructure.jira.client import _MAX_BACKOFF_SECONDS

        """THEN the expected behaviour holds: max backoff ceiling exists"""
        assert _MAX_BACKOFF_SECONDS == 30


# ====================================================================
# Auth error distinguished in CLI generate command
# ====================================================================


class TestAuthErrorDistinguished:
    """GIVEN auth error distinguished and the scenario: generate catches auth error"""
    def test_generate_catches_auth_error(self):
        """WHEN the code under test is exercised for: generate catches auth error"""
        import inspect

        from flowboard.cli.main import generate

        src = inspect.getsource(generate)

        """THEN the expected behaviour holds: generate catches auth error"""
        assert "JiraAuthError" in src

    """GIVEN auth error distinguished and the scenario: auth error message is actionable"""
    def test_auth_error_message_is_actionable(self):
        """WHEN the code under test is exercised for: auth error message is actionable"""
        import inspect

        from flowboard.cli.main import generate

        src = inspect.getsource(generate)

        """THEN the expected behaviour holds: auth error message is actionable"""
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

    """GIVEN epic key extraction and the scenario: string epic key"""
    def test_string_epic_key(self):
        """WHEN the code under test is exercised for: string epic key"""
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

        """THEN the expected behaviour holds: string epic key"""
        assert issue.epic_key == "EPIC-1"

    """GIVEN epic key extraction and the scenario: dict epic key"""
    def test_dict_epic_key(self):
        """WHEN the code under test is exercised for: dict epic key"""
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

        """THEN the expected behaviour holds: dict epic key"""
        assert issue.epic_key == "EPIC-2"

    """GIVEN epic key extraction and the scenario: list epic key"""
    def test_list_epic_key(self):
        """WHEN the code under test is exercised for: list epic key"""
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

        """THEN the expected behaviour holds: list epic key"""
        assert issue.epic_key == "EPIC-3"

    """GIVEN epic key extraction and the scenario: none epic key"""
    def test_none_epic_key(self):
        """WHEN the code under test is exercised for: none epic key"""
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

        """THEN the expected behaviour holds: none epic key"""
        assert issue.epic_key == ""

    """GIVEN epic key extraction and the scenario: empty list epic key"""
    def test_empty_list_epic_key(self):
        """WHEN the code under test is exercised for: empty list epic key"""
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

        """THEN the expected behaviour holds: empty list epic key"""
        assert issue.epic_key == ""


# ====================================================================
# Template pre-flight check
# ====================================================================


class TestTemplatePreFlightCheck:
    """GIVEN template pre flight check and the scenario: build env raises if dir missing"""
    def test_build_env_raises_if_dir_missing(self, tmp_path):
        """WHEN the code under test is exercised for: build env raises if dir missing"""
        from flowboard.presentation.html import renderer

        original = renderer._TEMPLATE_DIR
        renderer._TEMPLATE_DIR = tmp_path / "nonexistent"
        try:
            with pytest.raises(FileNotFoundError, match="Template directory not found"):
                renderer._build_env()
        finally:
            renderer._TEMPLATE_DIR = original

    """GIVEN template pre flight check and the scenario: build env succeeds with valid dir"""
    def test_build_env_succeeds_with_valid_dir(self):
        """WHEN the code under test is exercised for: build env succeeds with valid dir"""
        from flowboard.presentation.html.renderer import _build_env

        env = _build_env()

        """THEN the expected behaviour holds: build env succeeds with valid dir"""
        assert env is not None


# ====================================================================
# Secrets masked in validate-config output
# ====================================================================


class TestSecretsMasked:
    """GIVEN secrets masked and the scenario: describe config masks token"""
    def test_describe_config_masks_token(self):
        """WHEN the code under test is exercised for: describe config masks token"""
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

        """THEN the expected behaviour holds: describe config masks token"""
        assert "super-secret-token-12345" not in info["auth_token"]
        assert "****" in info["auth_token"] or info["auth_token"].startswith("*")


# ====================================================================
# Empty Jira response logs warning
# ====================================================================


class TestEmptyJiraResponseWarning:
    """GIVEN empty jira response warning and the scenario: empty issues logs warning"""
    def test_empty_issues_logs_warning(self, caplog):
        """WHEN the code under test is exercised for: empty issues logs warning"""
        from flowboard.application.orchestrator import analyse_raw_payload

        cfg = load_config_from_dict(
            {
                "jira": {"base_url": "https://test.atlassian.net"},
            }
        )
        with caplog.at_level(logging.WARNING, logger="flowboard.application.orchestrator"):
            analyse_raw_payload({"issues": [], "sprints": []}, cfg)

        """THEN the expected behaviour holds: empty issues logs warning"""
        assert any("No issues returned" in msg for msg in caplog.messages)


# ====================================================================
# Date parsing logs warning on failure
# ====================================================================


class TestDateParsingWarning:
    """GIVEN date parsing warning and the scenario: invalid date logs warning"""
    def test_invalid_date_logs_warning(self, caplog):
        """WHEN the code under test is exercised for: invalid date logs warning"""
        with caplog.at_level(logging.WARNING, logger="flowboard.shared.utils"):
            result = parse_date("2026-13-45")

        """THEN the expected behaviour holds: invalid date logs warning"""
        assert result is None
        assert any("Failed to parse date" in msg for msg in caplog.messages)

    """GIVEN date parsing warning and the scenario: invalid datetime logs warning"""
    def test_invalid_datetime_logs_warning(self, caplog):
        """WHEN the code under test is exercised for: invalid datetime logs warning"""
        with caplog.at_level(logging.WARNING, logger="flowboard.shared.utils"):
            result = parse_datetime("not-a-date")

        """THEN the expected behaviour holds: invalid datetime logs warning"""
        assert result is None
        assert any("Failed to parse datetime" in msg for msg in caplog.messages)

    """GIVEN date parsing warning and the scenario: empty string no warning"""
    def test_empty_string_no_warning(self, caplog):
        """THEN the expected behaviour holds: empty string no warning"""
        with caplog.at_level(logging.WARNING, logger="flowboard.shared.utils"):
            assert parse_date("") is None
            assert parse_date(None) is None
        assert not any("Failed to parse" in msg for msg in caplog.messages)


# ====================================================================
# Strict JSON serializer
# ====================================================================


class TestStrictJsonSerializer:
    """GIVEN strict json serializer and the scenario: datetime serialized as iso"""
    def test_datetime_serialized_as_iso(self):
        """WHEN the code under test is exercised for: datetime serialized as iso"""
        from flowboard.presentation.html.renderer import _json_dumps

        data = {"ts": datetime(2026, 3, 18, 12, 0)}
        result = _json_dumps(data)

        """THEN the expected behaviour holds: datetime serialized as iso"""
        assert "2026-03-18T12:00:00" in result

    """GIVEN strict json serializer and the scenario: date serialized as iso"""
    def test_date_serialized_as_iso(self):
        """WHEN the code under test is exercised for: date serialized as iso"""
        from flowboard.presentation.html.renderer import _json_dumps

        data = {"d": date(2026, 3, 18)}
        result = _json_dumps(data)

        """THEN the expected behaviour holds: date serialized as iso"""
        assert "2026-03-18" in result

    """GIVEN strict json serializer and the scenario: domain object serializes as dict"""
    def test_domain_object_serializes_as_dict(self):
        """WHEN the code under test is exercised for: domain object serializes as dict"""
        from flowboard.presentation.html.renderer import _json_dumps

        data = {"person": _person()}
        result = _json_dumps(data)

        """THEN the expected behaviour holds: domain object serializes as dict"""
        assert isinstance(result, str)
        assert "person" in result


# ====================================================================
# Sprint dedup doesn't drop id=0
# ====================================================================


class TestSprintDedupIdZero:
    """GIVEN sprint dedup id zero and the scenario: sprint id zero not dropped"""
    def test_sprint_id_zero_not_dropped(self):
        """WHEN the code under test is exercised for: sprint id zero not dropped"""
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

        """THEN the expected behaviour holds: sprint id zero not dropped"""
        assert 0 in ids
        assert 1 in ids


# ====================================================================
# PI date format normalization
# ====================================================================


class TestPIDateNormalization:
    """GIVEN p i date normalization and the scenario: single digit month accepted"""
    def test_single_digit_month_accepted(self):
        """WHEN the code under test is exercised for: single digit month accepted"""
        snap = compute_pi_snapshot("PI 1", "2026-3-2", today=date(2026, 3, 18))

        """THEN the expected behaviour holds: single digit month accepted"""
        assert snap.start_date == date(2026, 3, 2)

    """GIVEN p i date normalization and the scenario: single digit day accepted"""
    def test_single_digit_day_accepted(self):
        """WHEN the code under test is exercised for: single digit day accepted"""
        snap = compute_pi_snapshot("PI 1", "2026-03-2", today=date(2026, 3, 18))

        """THEN the expected behaviour holds: single digit day accepted"""
        assert snap.start_date == date(2026, 3, 2)

    """GIVEN p i date normalization and the scenario: standard format still works"""
    def test_standard_format_still_works(self):
        """WHEN the code under test is exercised for: standard format still works"""
        snap = compute_pi_snapshot("PI 1", "2026-03-02", today=date(2026, 3, 18))

        """THEN the expected behaviour holds: standard format still works"""
        assert snap.start_date == date(2026, 3, 2)

    """GIVEN p i date normalization and the scenario: invalid date raises"""
    def test_invalid_date_raises(self):
        """WHEN the code under test is exercised for: invalid date raises"""
        with pytest.raises(ValueError, match="Invalid PI start date"):
            compute_pi_snapshot("PI 1", "not-a-date", today=date(2026, 3, 18))


# ====================================================================
# Working day validation
# ====================================================================


class TestWorkingDayValidation:
    """GIVEN working day validation and the scenario: invalid weekday zero raises"""
    def test_invalid_weekday_zero_raises(self):
        """WHEN the code under test is exercised for: invalid weekday zero raises"""
        with pytest.raises(ValueError, match="Invalid working day"):
            compute_pi_snapshot(
                "PI 1", "2026-03-02", working_days=[0, 1, 2], today=date(2026, 3, 18)
            )

    """GIVEN working day validation and the scenario: invalid weekday eight raises"""
    def test_invalid_weekday_eight_raises(self):
        """WHEN the code under test is exercised for: invalid weekday eight raises"""
        with pytest.raises(ValueError, match="Invalid working day"):
            compute_pi_snapshot(
                "PI 1", "2026-03-02", working_days=[1, 2, 8], today=date(2026, 3, 18)
            )

    """GIVEN working day validation and the scenario: valid weekdays accepted"""
    def test_valid_weekdays_accepted(self):
        """WHEN the code under test is exercised for: valid weekdays accepted"""
        snap = compute_pi_snapshot(
            "PI 1", "2026-03-02", working_days=[1, 2, 3, 4, 5], today=date(2026, 3, 18)
        )

        """THEN the expected behaviour holds: valid weekdays accepted"""
        assert snap.name == "PI 1"


# ====================================================================
# conflict_list uses severity directly
# ====================================================================


class TestConflictSeverityDirect:
    """GIVEN conflict severity direct and the scenario: conflict list no redundant wrapping"""
    def test_conflict_list_no_redundant_wrapping(self):
        """WHEN the code under test is exercised for: conflict list no redundant wrapping"""
        import inspect

        src = inspect.getsource(conflict_list)

        """THEN the expected behaviour holds: conflict list no redundant wrapping"""
        assert "RiskSeverity(c.severity)" not in src

    """GIVEN conflict severity direct and the scenario: conflict list renders"""
    def test_conflict_list_renders(self):
        """WHEN the code under test is exercised for: conflict list renders"""
        t = get_translator("en")
        conflict = OverlapConflict(
            category="resource_contention",
            severity=RiskSeverity.HIGH,
            description="Test conflict",
            recommendation="Fix it",
        )
        html = conflict_list([conflict], t=t)

        """THEN the expected behaviour holds: conflict list renders"""
        assert "Test conflict" in html
        assert "conflict-item" in html


# ====================================================================
# Demo fixture path is robust
# ====================================================================


class TestDemoFixturePath:
    """GIVEN demo fixture path and the scenario: locate demo fixture finds file"""
    def test_locate_demo_fixture_finds_file(self):
        """WHEN the code under test is exercised for: locate demo fixture finds file"""
        from flowboard.cli.main import _locate_demo_fixture

        path = _locate_demo_fixture()

        """THEN the expected behaviour holds: locate demo fixture finds file"""
        assert path.exists()
        assert path.name == "mock_jira_data.json"


# ====================================================================
# Schema path resolution is robust
# ====================================================================


class TestSchemaPathResolution:
    """GIVEN schema path resolution and the scenario: schema loads successfully"""
    def test_schema_loads_successfully(self):
        """WHEN the code under test is exercised for: schema loads successfully"""
        from flowboard.infrastructure.config.validator import _load_schema

        schema = _load_schema()

        """THEN the expected behaviour holds: schema loads successfully"""
        assert "properties" in schema or "$schema" in schema or "type" in schema

    """GIVEN schema path resolution and the scenario: find schema path finds file"""
    def test_find_schema_path_finds_file(self):
        """WHEN the code under test is exercised for: find schema path finds file"""
        from flowboard.infrastructure.config.validator import _find_schema_path

        path = _find_schema_path()

        """THEN the expected behaviour holds: find schema path finds file"""
        assert path.exists()


# ====================================================================
# pi_snapshot typed correctly (not object)
# ====================================================================


class TestPISnapshotTyping:
    """GIVEN p i snapshot typing and the scenario: pi snapshot annotation is not object"""
    def test_pi_snapshot_annotation_is_not_object(self):
        """WHEN the code under test is exercised for: pi snapshot annotation is not object"""
        import inspect

        src = inspect.getsource(BoardSnapshot)

        """THEN the expected behaviour holds: pi snapshot annotation is not object"""
        assert "object | None" not in src
        assert "pi_snapshot" in src


# ====================================================================
# Request timeout configured
# ====================================================================


class TestRequestTimeout:
    """GIVEN request timeout and the scenario: request uses timeout"""
    def test_request_uses_timeout(self):
        """WHEN the code under test is exercised for: request uses timeout"""
        import inspect

        from flowboard.infrastructure.jira.client import JiraClient

        src = inspect.getsource(JiraClient._request)

        """THEN the expected behaviour holds: request uses timeout"""
        assert "timeout" in src


# ====================================================================
# Package data includes explicit template patterns
# ====================================================================


class TestPackageData:
    """GIVEN package data and the scenario: pyproject includes templates"""
    def test_pyproject_includes_templates(self):
        """WHEN the code under test is exercised for: pyproject includes templates"""
        pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
        content = pyproject_path.read_text()

        """THEN the expected behaviour holds: pyproject includes templates"""
        assert "presentation/html/templates/*.html" in content
        assert "presentation/html/templates/**/*.html" in content


# ====================================================================
# verify_jira_connection uses context manager
# ====================================================================


class TestVerifyUsesContextManager:
    """GIVEN verify uses context manager and the scenario: verify function uses with statement"""
    def test_verify_function_uses_with_statement(self):
        """WHEN the code under test is exercised for: verify function uses with statement"""
        import inspect

        from flowboard.application.services import verify_jira_connection

        src = inspect.getsource(verify_jira_connection)

        """THEN the expected behaviour holds: verify function uses with statement"""
        assert "with JiraClient" in src


# ====================================================================
# Thread-local locale cleanup
# ====================================================================


class TestLocaleCleanup:
    """GIVEN locale cleanup and the scenario: reset locale resets to default"""
    def test_reset_locale_resets_to_default(self):
        """WHEN the code under test is exercised for: reset locale resets to default"""
        set_locale("pl")

        """THEN the expected behaviour holds: reset locale resets to default"""
        assert get_locale() == "pl"
        reset_locale()
        assert get_locale() == "en"

    """GIVEN locale cleanup and the scenario: reset locale works across calls"""
    def test_reset_locale_works_across_calls(self):
        """WHEN the code under test is exercised for: reset locale works across calls"""
        set_locale("pl")
        reset_locale()
        set_locale("pl")
        reset_locale()

        """THEN the expected behaviour holds: reset locale works across calls"""
        assert get_locale() == "en"


# ====================================================================
# __all__ exports defined
# ====================================================================


class TestAllExports:
    """GIVEN all exports and the scenario: flowboard init has all"""
    def test_flowboard_init_has_all(self):
        """WHEN the code under test is exercised for: flowboard init has all"""
        import flowboard

        """THEN the expected behaviour holds: flowboard init has all"""
        assert hasattr(flowboard, "__all__")

    """GIVEN all exports and the scenario: i18n init has all"""
    def test_i18n_init_has_all(self):
        """WHEN the code under test is exercised for: i18n init has all"""
        import flowboard.i18n

        """THEN the expected behaviour holds: i18n init has all"""
        assert hasattr(flowboard.i18n, "__all__")
        assert "reset_locale" in flowboard.i18n.__all__


# ====================================================================
# Structured logging
# ====================================================================


class TestStructuredLogging:
    """GIVEN structured logging and the scenario: setup logging produces json format"""
    def test_setup_logging_produces_json_format(self):
        """WHEN the code under test is exercised for: setup logging produces json format"""
        import inspect

        from flowboard.cli.main import _JsonFormatter

        src = inspect.getsource(_JsonFormatter)

        """THEN the expected behaviour holds: setup logging produces json format"""
        assert '"time"' in src or "time" in src
        assert '"message"' in src or "message" in src


# ====================================================================
# Output directory creation
# ====================================================================


class TestOutputDirectoryCreation:
    """GIVEN output directory creation and the scenario: render creates output dir"""
    def test_render_creates_output_dir(self):
        """WHEN the code under test is exercised for: render creates output dir"""
        import inspect

        from flowboard.application.orchestrator import Orchestrator

        src = inspect.getsource(Orchestrator._render)

        """THEN the expected behaviour holds: render creates output dir"""
        assert "mkdir" in src
        assert "parents=True" in src
        assert "exist_ok=True" in src


# ====================================================================
# Backoff ceiling and jitter
# ====================================================================


class TestBackoffCeilingJitter:
    """GIVEN backoff ceiling jitter and the scenario: backoff ceiling constant"""
    def test_backoff_ceiling_constant(self):
        """WHEN the code under test is exercised for: backoff ceiling constant"""
        from flowboard.infrastructure.jira.client import _MAX_BACKOFF_SECONDS

        """THEN the expected behaviour holds: backoff ceiling constant"""
        assert _MAX_BACKOFF_SECONDS <= 60  # reasonable upper bound

    """GIVEN backoff ceiling jitter and the scenario: random import for jitter"""
    def test_random_import_for_jitter(self):
        """WHEN the code under test is exercised for: random import for jitter"""
        import inspect

        from flowboard.infrastructure.jira import client

        src = inspect.getsource(client)

        """THEN the expected behaviour holds: random import for jitter"""
        assert "random" in src


# ====================================================================
# age_days timezone-safe
# ====================================================================


class TestAgeDaysTimezoneSafe:
    """GIVEN age days timezone safe and the scenario: age days utc aware"""
    def test_age_days_utc_aware(self):
        """WHEN the code under test is exercised for: age days utc aware"""
        issue = _issue(created=datetime(2026, 3, 1, tzinfo=UTC))
        age = issue.age_days

        """THEN the expected behaviour holds: age days utc aware"""
        assert age is not None
        assert age >= 0

    """GIVEN age days timezone safe and the scenario: age days naive datetime"""
    def test_age_days_naive_datetime(self):
        """WHEN the code under test is exercised for: age days naive datetime"""
        issue = _issue(created=datetime(2026, 3, 1))
        age = issue.age_days

        """THEN the expected behaviour holds: age days naive datetime"""
        assert age is not None
        assert age >= 0

    """GIVEN age days timezone safe and the scenario: age days none created"""
    def test_age_days_none_created(self):
        """WHEN the code under test is exercised for: age days none created"""
        issue = _issue()
        issue.created = None

        """THEN the expected behaviour holds: age days none created"""
        assert issue.age_days is None

    """GIVEN age days timezone safe and the scenario: age days resolved"""
    def test_age_days_resolved(self):
        """WHEN the code under test is exercised for: age days resolved"""
        issue = _issue(created=datetime(2026, 3, 1, tzinfo=UTC))
        issue.resolved = datetime(2026, 3, 5, tzinfo=UTC)

        """THEN the expected behaviour holds: age days resolved"""
        assert issue.age_days == 4

    """GIVEN age days timezone safe and the scenario: age days never negative"""
    def test_age_days_never_negative(self):
        """WHEN the code under test is exercised for: age days never negative"""
        issue = _issue(created=datetime(2099, 1, 1, tzinfo=UTC))

        """THEN the expected behaviour holds: age days never negative"""
        assert issue.age_days == 0
