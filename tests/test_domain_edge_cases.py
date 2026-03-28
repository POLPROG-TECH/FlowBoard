"""Domain edge case tests — Jira JSON handling, sprint normalization, null fields, XSS safety, translator."""

from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import MagicMock, patch

import pytest
import requests

from flowboard.domain.models import (
    Issue,
    IssueLink,
    Person,
    Sprint,
    SprintHealth,
)
from flowboard.domain.scrum import (
    compute_blockers,
    compute_ceremonies,
)
from flowboard.i18n.translator import Translator
from flowboard.infrastructure.config.loader import (
    load_config_from_dict,
)
from flowboard.infrastructure.jira.normalizer import JiraNormalizer
from flowboard.presentation.html.charts import _json as chart_json
from flowboard.presentation.html.renderer import (
    _json_dumps,
    _safe_color,
    _safe_css_length,
)
from flowboard.shared.types import (
    IssueType,
    LinkType,
    Priority,
    SprintState,
    StatusCategory,
)

# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------


def _person(name: str = "Alice", team: str = "api") -> Person:
    return Person(account_id=name.lower(), display_name=name, email="", team=team)


def _sprint(sid: int = 1, name: str = "Sprint 1") -> Sprint:
    return Sprint(
        id=sid,
        name=name,
        board_id=1,
        state=SprintState.ACTIVE,
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 14),
    )


def _issue(
    key: str = "T-1",
    *,
    assignee: Person | None = None,
    sprint: Sprint | None = None,
    status_cat: StatusCategory = StatusCategory.IN_PROGRESS,
    issue_type: IssueType = IssueType.STORY,
    sp: float = 5.0,
    created: datetime | None = None,
    links: list[IssueLink] | None = None,
    priority: Priority = Priority.MEDIUM,
) -> Issue:
    return Issue(
        key=key,
        summary=f"Issue {key}",
        issue_type=issue_type,
        status_category=status_cat,
        assignee=assignee,
        story_points=sp,
        sprint=sprint,
        created=created or datetime(2026, 3, 1, tzinfo=UTC),
        priority=priority,
        links=links or [],
    )


def _sprint_health(sprint: Sprint) -> SprintHealth:
    return SprintHealth(
        sprint=sprint,
        total_issues=5,
        done_issues=2,
        in_progress_issues=2,
        todo_issues=1,
        blocked_issues=0,
        total_points=25.0,
        completed_points=10.0,
        aging_issues=0,
    )


def _minimal_config() -> dict:
    return {
        "jira": {"base_url": "https://test.atlassian.net"},
        "output": {"path": "output/test.html"},
    }


# =======================================================================
# JSON decode error handling in JiraClient._get_json
# =======================================================================


class TestJiraClientJsonDecodeHandling:
    """Covers: non-JSON Jira responses must raise JiraApiError, not crash."""

    def test_html_response_raises_jira_api_error(self):
        from flowboard.infrastructure.config.loader import JiraConfig
        from flowboard.infrastructure.jira.client import JiraApiError, JiraClient

        config = JiraConfig(base_url="https://test.atlassian.net")
        client = JiraClient(config)

        # Mock a response that returns HTML instead of JSON
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        mock_resp.text = "<html><body>Maintenance</body></html>"
        mock_resp.json.side_effect = requests.exceptions.JSONDecodeError("", "", 0)

        with (
            patch.object(client, "_request", return_value=mock_resp),
            pytest.raises(JiraApiError, match="non-JSON response"),
        ):
            client._get_json("https://test.atlassian.net/api")


# =======================================================================
# Sprint normalization — unguarded raw["id"]
# =======================================================================


class TestSprintNormalizationRobustness:
    """Covers: malformed sprint data must not crash normalization."""

    def test_sprint_missing_id_raises_value_error(self):
        config = load_config_from_dict(_minimal_config())
        normalizer = JiraNormalizer(config)
        with pytest.raises(ValueError, match="missing 'id'"):
            normalizer.normalize_sprint({"name": "No ID Sprint"})

    def test_normalize_sprints_skips_malformed(self):
        config = load_config_from_dict(_minimal_config())
        normalizer = JiraNormalizer(config)
        sprints = normalizer.normalize_sprints(
            [
                {"id": 1, "name": "Good Sprint"},
                {"name": "Bad Sprint"},  # missing id
                {"id": 3, "name": "Another Good"},
            ]
        )
        assert len(sprints) == 2
        assert sprints[0].name == "Good Sprint"
        assert sprints[1].name == "Another Good"


# =======================================================================
# Null list fields in normalizer
# =======================================================================


class TestNormalizerNullListFields:
    """Covers: Jira returning null for list fields must not crash."""

    def test_null_issuelinks_handled(self):
        config = load_config_from_dict(_minimal_config())
        normalizer = JiraNormalizer(config)
        raw = {
            "key": "T-1",
            "fields": {
                "summary": "Test",
                "issuetype": {"name": "Story"},
                "status": {"name": "To Do"},
                "issuelinks": None,
                "labels": None,
                "components": None,
                "fixVersions": None,
            },
        }
        issue = normalizer.normalize_issue(raw)
        assert issue.links == []
        assert issue.labels == []
        assert issue.components == []
        assert issue.fix_versions == []

    def test_non_dict_component_filtered(self):
        config = load_config_from_dict(_minimal_config())
        normalizer = JiraNormalizer(config)
        raw = {
            "key": "T-2",
            "fields": {
                "summary": "Test",
                "issuetype": {"name": "Task"},
                "status": {"name": "Open"},
                "components": [{"name": "UI"}, "not-a-dict", {"name": "API"}],
            },
        }
        issue = normalizer.normalize_issue(raw)
        assert issue.components == ["UI", "API"]

    def test_parent_as_string_handled(self):
        config = load_config_from_dict(_minimal_config())
        normalizer = JiraNormalizer(config)
        raw = {
            "key": "T-3",
            "fields": {
                "summary": "Test",
                "issuetype": {"name": "Sub-task"},
                "status": {"name": "Open"},
                "parent": "PROJ-123",  # string, not dict
            },
        }
        issue = normalizer.normalize_issue(raw)
        assert issue.parent_key == ""  # safely falls back


# =======================================================================
# Color default mismatch
# =======================================================================


class TestColorDefaultConsistency:
    """Covers: all code paths must produce the same primary_color default."""

    def test_config_without_color_uses_fb6400(self):
        config = load_config_from_dict(_minimal_config())
        assert config.output.primary_color == "#fb6400"
        assert config.dashboard.branding.primary_color == "#fb6400"


# =======================================================================
# StatusCategory crash on invalid mapping
# =======================================================================


class TestInvalidStatusMappingHandled:
    """Covers: invalid status_mapping values must warn, not crash."""

    def test_invalid_status_mapping_skipped_gracefully(self):
        from flowboard.infrastructure.config.loader import _build_full_config

        # Bypass schema validation to test the normalizer's own defense
        raw = {**_minimal_config(), "status_mapping": {"Open": "To Do", "Invalid": "BadValue"}}
        config = _build_full_config(raw)
        normalizer = JiraNormalizer(config)
        # "Open" should be mapped correctly; "Invalid" should be skipped
        assert normalizer._status_map["Open"] == StatusCategory.TODO
        assert "Invalid" not in normalizer._status_map


# =======================================================================
# Person cache keyed on empty string
# =======================================================================


class TestPersonCacheEmptyId:
    """Covers: empty account IDs must not corrupt the person cache."""

    def test_different_anonymous_users_are_distinct(self):
        config = load_config_from_dict(_minimal_config())
        normalizer = JiraNormalizer(config)
        p1 = normalizer.normalize_person({"displayName": "User A"})
        p2 = normalizer.normalize_person({"displayName": "User B"})
        assert p1.display_name == "User A"
        assert p2.display_name == "User B"
        assert p1 is not p2  # must be distinct objects


# =======================================================================
# XSS — Chart data </script> breakout
# =======================================================================


class TestChartJsonXssSafe:
    """Covers: chart JSON must escape HTML-significant characters."""

    def test_script_tag_escaped(self):
        malicious = {"label": "</script><script>alert(1)</script>"}
        result = chart_json(malicious)
        assert "</script>" not in result
        assert "\\u003c" in result
        assert "\\u003e" in result

    def test_ampersand_escaped(self):
        data = {"label": "A & B"}
        result = chart_json(data)
        assert "&" not in result.replace("\\u0026", "")


# =======================================================================
# XSS — Config JSON </script> breakout
# =======================================================================


class TestConfigJsonXssSafe:
    """Covers: config JSON must escape HTML-significant characters."""

    def test_script_tag_in_jql_escaped(self):
        data = {"jql_filter": "</script><img onerror=alert(1)>"}
        result = _json_dumps(data)
        assert "</script>" not in result
        assert "\\u003c" in result


# =======================================================================
# Ceremony IndexError + unescaped metric values
# =======================================================================


class TestCeremonyHeadlineRobustness:
    """Covers: malformed ceremony headlines must not IndexError."""

    def test_short_daily_headline_no_crash(self):
        from flowboard.presentation.html.components import _format_ceremony_headline

        t = Translator("en")
        # Only 2 parts instead of expected 3
        result = _format_ceremony_headline("daily:5", t)
        assert result == "daily:5"  # falls through safely

    def test_valid_headline_translated(self):
        from flowboard.presentation.html.components import _format_ceremony_headline

        t = Translator("en")
        result = _format_ceremony_headline("daily:3:5", t)
        assert result != "daily:3:5"  # should be translated


# =======================================================================
# CSS injection via config variables
# =======================================================================


class TestCssInjectionPrevention:
    """Covers: CSS variables must be sanitized to safe patterns."""

    def test_valid_color_passes(self):
        assert _safe_color("#fb6400") == "#fb6400"
        assert _safe_color("#fff") == "#fff"
        assert _safe_color("#002754e6") == "#002754e6"

    def test_injected_color_blocked(self):
        malicious = "red;} body{display:none} :root{--primary:red"
        assert _safe_color(malicious) == "#fb6400"

    def test_valid_length_passes(self):
        assert _safe_css_length("1440px") == "1440px"
        assert _safe_css_length("100%") == "100%"
        assert _safe_css_length("90rem") == "90rem"

    def test_injected_length_blocked(self):
        malicious = "1440px;} body{display:none"
        assert _safe_css_length(malicious) == "1440px"


# =======================================================================
# Translator format_number NaN/Inf + ValueError
# =======================================================================


class TestTranslatorEdgeCases:
    """Covers: format_number on NaN/Inf and format string ValueError."""

    def test_format_number_nan_returns_dash(self):
        t = Translator("en")
        assert t.format_number(float("nan")) == "—"

    def test_format_number_inf_returns_dash(self):
        t = Translator("en")
        assert t.format_number(float("inf")) == "—"

    def test_format_number_negative_inf_returns_dash(self):
        t = Translator("en")
        assert t.format_number(float("-inf")) == "—"

    def test_format_string_valueerror_handled(self):
        t = Translator("en")
        # Patch translations to contain a malformed format spec
        t._messages["test.bad_format"] = "{0!z}"
        result = t("test.bad_format", some_var="x")
        assert result == "[?]"  # malformed placeholder replaced with safe marker, no crash


# =======================================================================
# scrum age_days None comparisons (CRITICAL)
# =======================================================================


class TestScrumNoneAgeDays:
    """Covers: Issues with created=None must not crash scrum analytics."""

    def test_compute_blockers_with_none_created(self):
        alice = _person("Alice")
        sp = _sprint()
        blocked_link = IssueLink(
            target_key="T-2",
            link_type=LinkType.IS_BLOCKED_BY,
            is_resolved=False,
            target_summary="Blocker",
        )
        issue = Issue(
            key="T-1",
            summary="No created",
            issue_type=IssueType.STORY,
            status_category=StatusCategory.IN_PROGRESS,
            assignee=alice,
            story_points=5,
            sprint=sp,
            created=None,
            links=[blocked_link],
        )
        result = compute_blockers([issue], date(2026, 3, 10))
        assert len(result) == 1
        assert result[0].key == "T-1"

    def test_compute_ceremonies_with_none_created(self):
        alice = _person("Alice")
        sp = _sprint()
        issue = Issue(
            key="T-1",
            summary="No created",
            issue_type=IssueType.STORY,
            status_category=StatusCategory.IN_PROGRESS,
            assignee=alice,
            story_points=5,
            sprint=sp,
            created=None,
        )
        # Must not raise TypeError
        from flowboard.domain.scrum import ReadinessReport

        result = compute_ceremonies(
            [issue],
            [],
            [],
            [],
            ReadinessReport(items=[], avg_readiness=0.0),
            [],
            today=date(2026, 3, 10),
        )
        assert result is not None


# =======================================================================
# PI infinite loop with empty working_days
# =======================================================================
