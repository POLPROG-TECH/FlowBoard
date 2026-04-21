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
    """Tests for jira client json decode handling."""

    """GIVEN jira client json decode handling and the scenario: html response raises jira api error"""
    def test_html_response_raises_jira_api_error(self):
        """WHEN the code under test is exercised for: html response raises jira api error"""
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
    """Tests for sprint normalization robustness."""

    """GIVEN sprint normalization robustness and the scenario: sprint missing id raises value error"""
    def test_sprint_missing_id_raises_value_error(self):
        """WHEN the code under test is exercised for: sprint missing id raises value error"""
        config = load_config_from_dict(_minimal_config())
        normalizer = JiraNormalizer(config)
        with pytest.raises(ValueError, match="missing 'id'"):
            normalizer.normalize_sprint({"name": "No ID Sprint"})

    """GIVEN sprint normalization robustness and the scenario: normalize sprints skips malformed"""
    def test_normalize_sprints_skips_malformed(self):
        """WHEN the code under test is exercised for: normalize sprints skips malformed"""
        config = load_config_from_dict(_minimal_config())
        normalizer = JiraNormalizer(config)
        sprints = normalizer.normalize_sprints(
            [
                {"id": 1, "name": "Good Sprint"},
                {"name": "Bad Sprint"},  # missing id
                {"id": 3, "name": "Another Good"},
            ]
        )

        """THEN the expected behaviour holds: normalize sprints skips malformed"""
        assert len(sprints) == 2
        assert sprints[0].name == "Good Sprint"
        assert sprints[1].name == "Another Good"


# =======================================================================
# Null list fields in normalizer
# =======================================================================


class TestNormalizerNullListFields:
    """Tests for normalizer null list fields."""

    """GIVEN normalizer null list fields and the scenario: null issuelinks handled"""
    def test_null_issuelinks_handled(self):
        """WHEN the code under test is exercised for: null issuelinks handled"""
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

        """THEN the expected behaviour holds: null issuelinks handled"""
        assert issue.links == []
        assert issue.labels == []
        assert issue.components == []
        assert issue.fix_versions == []

    """GIVEN normalizer null list fields and the scenario: non dict component filtered"""
    def test_non_dict_component_filtered(self):
        """WHEN the code under test is exercised for: non dict component filtered"""
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

        """THEN the expected behaviour holds: non dict component filtered"""
        assert issue.components == ["UI", "API"]

    """GIVEN normalizer null list fields and the scenario: parent as string handled"""
    def test_parent_as_string_handled(self):
        """WHEN the code under test is exercised for: parent as string handled"""
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

        """THEN the expected behaviour holds: parent as string handled"""
        assert issue.parent_key == ""  # safely falls back


# =======================================================================
# Color default mismatch
# =======================================================================


class TestColorDefaultConsistency:
    """Tests for color default consistency."""

    """GIVEN color default consistency and the scenario: config without color uses fb6400"""
    def test_config_without_color_uses_fb6400(self):
        """WHEN the code under test is exercised for: config without color uses fb6400"""
        config = load_config_from_dict(_minimal_config())

        """THEN the expected behaviour holds: config without color uses fb6400"""
        assert config.output.primary_color == "#fb6400"
        assert config.dashboard.branding.primary_color == "#fb6400"


# =======================================================================
# StatusCategory crash on invalid mapping
# =======================================================================


class TestInvalidStatusMappingHandled:
    """Tests for invalid status mapping handled."""

    """GIVEN invalid status mapping handled and the scenario: invalid status mapping skipped gracefully"""
    def test_invalid_status_mapping_skipped_gracefully(self):
        """WHEN the code under test is exercised for: invalid status mapping skipped gracefully"""
        from flowboard.infrastructure.config.loader import _build_full_config

        # Bypass schema validation to test the normalizer's own defense
        raw = {**_minimal_config(), "status_mapping": {"Open": "To Do", "Invalid": "BadValue"}}
        config = _build_full_config(raw)
        normalizer = JiraNormalizer(config)
        # "Open" should be mapped correctly; "Invalid" should be skipped

        """THEN the expected behaviour holds: invalid status mapping skipped gracefully"""
        assert normalizer._status_map["Open"] == StatusCategory.TODO
        assert "Invalid" not in normalizer._status_map


# =======================================================================
# Person cache keyed on empty string
# =======================================================================


class TestPersonCacheEmptyId:
    """Tests for person cache empty id."""

    """GIVEN person cache empty id and the scenario: different anonymous users are distinct"""
    def test_different_anonymous_users_are_distinct(self):
        """WHEN the code under test is exercised for: different anonymous users are distinct"""
        config = load_config_from_dict(_minimal_config())
        normalizer = JiraNormalizer(config)
        p1 = normalizer.normalize_person({"displayName": "User A"})
        p2 = normalizer.normalize_person({"displayName": "User B"})

        """THEN the expected behaviour holds: different anonymous users are distinct"""
        assert p1.display_name == "User A"
        assert p2.display_name == "User B"
        assert p1 is not p2  # must be distinct objects


# =======================================================================
# XSS — Chart data </script> breakout
# =======================================================================


class TestChartJsonXssSafe:
    """Tests for chart json xss safe."""

    """GIVEN chart json xss safe and the scenario: script tag escaped"""
    def test_script_tag_escaped(self):
        """WHEN the code under test is exercised for: script tag escaped"""
        malicious = {"label": "</script><script>alert(1)</script>"}
        result = chart_json(malicious)

        """THEN the expected behaviour holds: script tag escaped"""
        assert "</script>" not in result
        assert "\\u003c" in result
        assert "\\u003e" in result

    """GIVEN chart json xss safe and the scenario: ampersand escaped"""
    def test_ampersand_escaped(self):
        """WHEN the code under test is exercised for: ampersand escaped"""
        data = {"label": "A & B"}
        result = chart_json(data)

        """THEN the expected behaviour holds: ampersand escaped"""
        assert "&" not in result.replace("\\u0026", "")


# =======================================================================
# XSS — Config JSON </script> breakout
# =======================================================================


class TestConfigJsonXssSafe:
    """Tests for config json xss safe."""

    """GIVEN config json xss safe and the scenario: script tag in jql escaped"""
    def test_script_tag_in_jql_escaped(self):
        """WHEN the code under test is exercised for: script tag in jql escaped"""
        data = {"jql_filter": "</script><img onerror=alert(1)>"}
        result = _json_dumps(data)

        """THEN the expected behaviour holds: script tag in jql escaped"""
        assert "</script>" not in result
        assert "\\u003c" in result


# =======================================================================
# Ceremony IndexError + unescaped metric values
# =======================================================================


class TestCeremonyHeadlineRobustness:
    """Tests for ceremony headline robustness."""

    """GIVEN ceremony headline robustness and the scenario: short daily headline no crash"""
    def test_short_daily_headline_no_crash(self):
        """WHEN the code under test is exercised for: short daily headline no crash"""
        from flowboard.presentation.html.components import _format_ceremony_headline

        t = Translator("en")
        # Only 2 parts instead of expected 3
        result = _format_ceremony_headline("daily:5", t)

        """THEN the expected behaviour holds: short daily headline no crash"""
        assert result == "daily:5"  # falls through safely

    """GIVEN ceremony headline robustness and the scenario: valid headline translated"""
    def test_valid_headline_translated(self):
        """WHEN the code under test is exercised for: valid headline translated"""
        from flowboard.presentation.html.components import _format_ceremony_headline

        t = Translator("en")
        result = _format_ceremony_headline("daily:3:5", t)

        """THEN the expected behaviour holds: valid headline translated"""
        assert result != "daily:3:5"  # should be translated


# =======================================================================
# CSS injection via config variables
# =======================================================================


class TestCssInjectionPrevention:
    """Tests for css injection prevention."""

    """GIVEN css injection prevention and the scenario: valid color passes"""
    def test_valid_color_passes(self):
        """THEN the expected behaviour holds: valid color passes"""
        assert _safe_color("#fb6400") == "#fb6400"
        assert _safe_color("#fff") == "#fff"
        assert _safe_color("#002754e6") == "#002754e6"

    """GIVEN css injection prevention and the scenario: injected color blocked"""
    def test_injected_color_blocked(self):
        """WHEN the code under test is exercised for: injected color blocked"""
        malicious = "red;} body{display:none} :root{--primary:red"

        """THEN the expected behaviour holds: injected color blocked"""
        assert _safe_color(malicious) == "#fb6400"

    """GIVEN css injection prevention and the scenario: valid length passes"""
    def test_valid_length_passes(self):
        """THEN the expected behaviour holds: valid length passes"""
        assert _safe_css_length("1440px") == "1440px"
        assert _safe_css_length("100%") == "100%"
        assert _safe_css_length("90rem") == "90rem"

    """GIVEN css injection prevention and the scenario: injected length blocked"""
    def test_injected_length_blocked(self):
        """WHEN the code under test is exercised for: injected length blocked"""
        malicious = "1440px;} body{display:none"

        """THEN the expected behaviour holds: injected length blocked"""
        assert _safe_css_length(malicious) == "1440px"


# =======================================================================
# Translator format_number NaN/Inf + ValueError
# =======================================================================


class TestTranslatorEdgeCases:
    """Tests for translator edge cases."""

    """GIVEN translator edge cases and the scenario: format number nan returns dash"""
    def test_format_number_nan_returns_dash(self):
        """WHEN the code under test is exercised for: format number nan returns dash"""
        t = Translator("en")

        """THEN the expected behaviour holds: format number nan returns dash"""
        assert t.format_number(float("nan")) == "—"

    """GIVEN translator edge cases and the scenario: format number inf returns dash"""
    def test_format_number_inf_returns_dash(self):
        """WHEN the code under test is exercised for: format number inf returns dash"""
        t = Translator("en")

        """THEN the expected behaviour holds: format number inf returns dash"""
        assert t.format_number(float("inf")) == "—"

    """GIVEN translator edge cases and the scenario: format number negative inf returns dash"""
    def test_format_number_negative_inf_returns_dash(self):
        """WHEN the code under test is exercised for: format number negative inf returns dash"""
        t = Translator("en")

        """THEN the expected behaviour holds: format number negative inf returns dash"""
        assert t.format_number(float("-inf")) == "—"

    """GIVEN translator edge cases and the scenario: format string valueerror handled"""
    def test_format_string_valueerror_handled(self):
        """WHEN the code under test is exercised for: format string valueerror handled"""
        t = Translator("en")
        # Patch translations to contain a malformed format spec
        t._messages["test.bad_format"] = "{0!z}"
        result = t("test.bad_format", some_var="x")

        """THEN the expected behaviour holds: format string valueerror handled"""
        assert result == "[?]"  # malformed placeholder replaced with safe marker, no crash


# =======================================================================
# scrum age_days None comparisons (CRITICAL)
# =======================================================================


class TestScrumNoneAgeDays:
    """Tests for scrum none age days."""

    """GIVEN scrum none age days and the scenario: compute blockers with none created"""
    def test_compute_blockers_with_none_created(self):
        """WHEN the code under test is exercised for: compute blockers with none created"""
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

        """THEN the expected behaviour holds: compute blockers with none created"""
        assert len(result) == 1
        assert result[0].key == "T-1"

    """GIVEN scrum none age days and the scenario: compute ceremonies with none created"""
    def test_compute_ceremonies_with_none_created(self):
        """WHEN the code under test is exercised for: compute ceremonies with none created"""
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

        """THEN the expected behaviour holds: compute ceremonies with none created"""
        assert result is not None


# =======================================================================
# PI infinite loop with empty working_days
# =======================================================================
