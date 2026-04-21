"""Tests for security and sanitization - XSS prevention across all components,
authentication error propagation, CSV None handling, JQL injection prevention,
retry-after header parsing, error response sanitization, narrowed exception
types, config encoding, and CSV formula injection guards.
"""

from __future__ import annotations

import csv
import io
from datetime import UTC, date, datetime
from unittest.mock import MagicMock

import pytest

from flowboard.domain.models import (
    BoardSnapshot,
    Dependency,
    Issue,
    OverlapConflict,
    Person,
    RiskSignal,
    RoadmapItem,
    Sprint,
    SprintHealth,
    WorkloadRecord,
)
from flowboard.infrastructure.config.loader import load_config_from_dict
from flowboard.presentation.export.csv_export import (
    export_issues_csv,
    export_risks_csv,
    export_workload_csv,
)
from flowboard.presentation.html.components import (
    conflict_list,
    dependency_table,
    issues_table,
    pi_timeline_view,
    risk_table,
    roadmap_timeline,
    sprint_health_cards,
    workload_table,
)
from flowboard.shared.types import (
    IssueStatus,
    IssueType,
    LinkType,
    RiskCategory,
    RiskSeverity,
    SprintState,
    StatusCategory,
)

# ======================================================================
# XSS prevention in all HTML component builders
# ======================================================================


class TestXSSPrevention:
    """Tests for x s s prevention."""

    XSS_SCRIPT = '<script>alert("xss")</script>'
    XSS_IMG = "<img src=x onerror=alert(1)>"
    XSS_ENCODED_SCRIPT = "&lt;script&gt;"  # what escaped version should contain

    def _make_person(self, name: str = "Alice") -> Person:
        return Person(account_id="u1", display_name=name, team="alpha")

    def _make_issue(
        self, key: str = "T-1", summary: str = "Test", assignee: Person | None = None
    ) -> Issue:
        return Issue(
            key=key,
            summary=summary,
            issue_type=IssueType.STORY,
            status=IssueStatus.OTHER,
            status_category=StatusCategory.TODO,
            assignee=assignee or self._make_person(),
            created=datetime(2026, 3, 1, tzinfo=UTC),
        )

    """GIVEN x s s prevention and the scenario: workload table escapes person name"""
    def test_workload_table_escapes_person_name(self) -> None:
        """WHEN the code under test is exercised for: workload table escapes person name"""
        p = self._make_person(self.XSS_SCRIPT)
        wr = WorkloadRecord(person=p, team="alpha", issue_count=1, story_points=5)
        html = workload_table([wr])

        """THEN the expected behaviour holds: workload table escapes person name"""
        assert "<script>" not in html
        assert self.XSS_ENCODED_SCRIPT in html

    """GIVEN x s s prevention and the scenario: workload table escapes team name"""
    def test_workload_table_escapes_team_name(self) -> None:
        """WHEN the code under test is exercised for: workload table escapes team name"""
        p = self._make_person()
        wr = WorkloadRecord(person=p, team=self.XSS_SCRIPT, issue_count=1, story_points=5)
        html = workload_table([wr])

        """THEN the expected behaviour holds: workload table escapes team name"""
        assert "<script>" not in html

    """GIVEN x s s prevention and the scenario: risk table escapes title"""
    def test_risk_table_escapes_title(self) -> None:
        """WHEN the code under test is exercised for: risk table escapes title"""
        signal = RiskSignal(
            severity=RiskSeverity.HIGH,
            category=RiskCategory.OVERLOAD,
            title=self.XSS_SCRIPT,
            description="Normal",
            recommendation="Normal",
        )
        html = risk_table([signal])

        """THEN the expected behaviour holds: risk table escapes title"""
        assert "<script>" not in html
        assert self.XSS_ENCODED_SCRIPT in html

    """GIVEN x s s prevention and the scenario: risk table escapes recommendation"""
    def test_risk_table_escapes_recommendation(self) -> None:
        """WHEN the code under test is exercised for: risk table escapes recommendation"""
        signal = RiskSignal(
            severity=RiskSeverity.HIGH,
            category=RiskCategory.OVERLOAD,
            title="Normal",
            description="Normal",
            recommendation=self.XSS_IMG,
        )
        html = risk_table([signal])
        # Ensure the raw <img tag is not present - only the escaped form

        """THEN the expected behaviour holds: risk table escapes recommendation"""
        assert "<img src=" not in html
        assert "&lt;img" in html

    """GIVEN x s s prevention and the scenario: sprint health escapes sprint name"""
    def test_sprint_health_escapes_sprint_name(self) -> None:
        """WHEN the code under test is exercised for: sprint health escapes sprint name"""
        sp = Sprint(
            id=1,
            name=self.XSS_SCRIPT,
            state=SprintState.ACTIVE,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 14),
        )
        sh = SprintHealth(sprint=sp, total_issues=10, done_issues=5)
        html = sprint_health_cards([sh])

        """THEN the expected behaviour holds: sprint health escapes sprint name"""
        assert "<script>" not in html
        assert self.XSS_ENCODED_SCRIPT in html

    """GIVEN x s s prevention and the scenario: roadmap escapes key"""
    def test_roadmap_escapes_key(self) -> None:
        """WHEN the code under test is exercised for: roadmap escapes key"""
        ri = RoadmapItem(key=self.XSS_SCRIPT, title="Normal", status=StatusCategory.TODO)
        html = roadmap_timeline([ri])

        """THEN the expected behaviour holds: roadmap escapes key"""
        assert "<script>" not in html

    """GIVEN x s s prevention and the scenario: roadmap escapes owner name"""
    def test_roadmap_escapes_owner_name(self) -> None:
        """WHEN the code under test is exercised for: roadmap escapes owner name"""
        p = self._make_person(self.XSS_IMG)
        ri = RoadmapItem(key="E-1", title="Normal", owner=p, status=StatusCategory.TODO)
        html = roadmap_timeline([ri])
        # Raw <img tag must not appear - only escaped version

        """THEN the expected behaviour holds: roadmap escapes owner name"""
        assert "<img src=" not in html
        assert "&lt;img" in html

    """GIVEN x s s prevention and the scenario: issues table escapes key"""
    def test_issues_table_escapes_key(self) -> None:
        """WHEN the code under test is exercised for: issues table escapes key"""
        issue = self._make_issue(key=self.XSS_SCRIPT)
        html = issues_table([issue])

        """THEN the expected behaviour holds: issues table escapes key"""
        assert "<script>" not in html

    """GIVEN x s s prevention and the scenario: issues table escapes assignee name"""
    def test_issues_table_escapes_assignee_name(self) -> None:
        """WHEN the code under test is exercised for: issues table escapes assignee name"""
        p = self._make_person(self.XSS_IMG)
        issue = self._make_issue(assignee=p)
        html = issues_table([issue])
        # Raw <img tag must not appear

        """THEN the expected behaviour holds: issues table escapes assignee name"""
        assert "<img src=" not in html
        assert "&lt;img" in html

    """GIVEN x s s prevention and the scenario: issues table escapes sprint name"""
    def test_issues_table_escapes_sprint_name(self) -> None:
        """WHEN the code under test is exercised for: issues table escapes sprint name"""
        sp = Sprint(id=1, name=self.XSS_SCRIPT, state=SprintState.ACTIVE)
        issue = self._make_issue()
        issue.sprint = sp
        html = issues_table([issue])

        """THEN the expected behaviour holds: issues table escapes sprint name"""
        assert "<script>" not in html

    """GIVEN x s s prevention and the scenario: conflict list escapes description"""
    def test_conflict_list_escapes_description(self) -> None:
        """WHEN the code under test is exercised for: conflict list escapes description"""
        c = OverlapConflict(
            category="resource_contention",
            severity=RiskSeverity.HIGH,
            description=self.XSS_SCRIPT,
            recommendation=self.XSS_IMG,
        )
        html = conflict_list([c])

        """THEN the expected behaviour holds: conflict list escapes description"""
        assert "<script>" not in html
        # Raw <img tag must not appear
        assert "<img src=" not in html

    """GIVEN x s s prevention and the scenario: dependency table escapes keys"""
    def test_dependency_table_escapes_keys(self) -> None:
        """WHEN the code under test is exercised for: dependency table escapes keys"""
        dep = Dependency(
            source_key=self.XSS_SCRIPT,
            target_key=self.XSS_IMG,
            link_type=LinkType.BLOCKS,
            source_status=StatusCategory.TODO,
            target_status=StatusCategory.TODO,
        )
        snap = BoardSnapshot(dependencies=[dep])
        html = dependency_table(snap)

        """THEN the expected behaviour holds: dependency table escapes keys"""
        assert "<script>" not in html
        # Raw <img tag must not appear
        assert "<img src=" not in html


# ======================================================================
# Connector re-raises JiraAuthError instead of swallowing it
# ======================================================================


class TestConnectorAuthErrorPropagation:
    """Tests for connector auth error propagation."""

    """GIVEN connector auth error propagation and the scenario: auth error propagates from sprint fetch"""
    def test_auth_error_propagates_from_sprint_fetch(self) -> None:
        """WHEN the code under test is exercised for: auth error propagates from sprint fetch"""
        from flowboard.infrastructure.jira.client import JiraAuthError
        from flowboard.infrastructure.jira.connector import JiraConnector

        config = load_config_from_dict(
            {"jira": {"base_url": "https://test.atlassian.net", "boards": [1]}}
        )
        mock_client = MagicMock()
        mock_client.get_sprints.side_effect = JiraAuthError(401, "Unauthorized")

        connector = JiraConnector(mock_client, config)

        with pytest.raises(JiraAuthError):
            connector._fetch_sprints()

    """GIVEN connector auth error propagation and the scenario: non auth errors are still swallowed"""
    def test_non_auth_errors_are_still_swallowed(self) -> None:
        """WHEN the code under test is exercised for: non auth errors are still swallowed"""
        from flowboard.infrastructure.jira.client import JiraApiError
        from flowboard.infrastructure.jira.connector import JiraConnector

        config = load_config_from_dict(
            {"jira": {"base_url": "https://test.atlassian.net", "boards": [1]}}
        )
        mock_client = MagicMock()
        mock_client.get_sprints.side_effect = JiraApiError(500, "Internal error")

        connector = JiraConnector(mock_client, config)
        # Should NOT raise - Jira API errors for individual boards are caught
        result = connector._fetch_sprints()

        """THEN the expected behaviour holds: non auth errors are still swallowed"""
        assert result == []

    """GIVEN connector auth error propagation and the scenario: unexpected errors propagate"""
    def test_unexpected_errors_propagate(self) -> None:
        """WHEN the code under test is exercised for: unexpected errors propagate"""
        from flowboard.infrastructure.jira.connector import JiraConnector

        config = load_config_from_dict(
            {"jira": {"base_url": "https://test.atlassian.net", "boards": [1]}}
        )
        mock_client = MagicMock()
        mock_client.get_sprints.side_effect = RuntimeError("Bug in code")

        connector = JiraConnector(mock_client, config)
        with pytest.raises(RuntimeError, match="Bug in code"):
            connector._fetch_sprints()


# ======================================================================
# locale.getdefaultlocale() replaced with locale.getlocale()
# ======================================================================


class TestLocaleDetectionDeprecation:
    """Tests for locale detection deprecation."""

    """GIVEN locale detection deprecation and the scenario: detect locale does not use deprecated api"""
    def test_detect_locale_does_not_use_deprecated_api(self) -> None:
        """WHEN the code under test is exercised for: detect locale does not use deprecated api"""
        import inspect

        from flowboard.i18n.translator import detect_locale

        source = inspect.getsource(detect_locale)

        """THEN the expected behaviour holds: detect locale does not use deprecated api"""
        assert "getdefaultlocale" not in source, (
            "detect_locale still uses deprecated locale.getdefaultlocale()"
        )

    """GIVEN locale detection deprecation and the scenario: detect locale returns valid locale"""
    def test_detect_locale_returns_valid_locale(self) -> None:
        """WHEN the code under test is exercised for: detect locale returns valid locale"""
        from flowboard.i18n.translator import detect_locale

        result = detect_locale()

        """THEN the expected behaviour holds: detect locale returns valid locale"""
        assert result in ("en", "pl")

    """GIVEN locale detection deprecation and the scenario: detect locale no deprecation warnings"""
    def test_detect_locale_no_deprecation_warnings(self) -> None:
        """WHEN the code under test is exercised for: detect locale no deprecation warnings"""
        import warnings

        from flowboard.i18n.translator import detect_locale

        """THEN the expected behaviour holds: detect locale no deprecation warnings"""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            detect_locale()
            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) == 0, (
                f"detect_locale raised DeprecationWarning: {deprecation_warnings}"
            )


# ======================================================================
# CSV export writes empty string instead of "None" for missing team
# ======================================================================


class TestCSVExportNoneHandling:
    """Tests for c s v export none handling."""

    """GIVEN c s v export none handling and the scenario: none team in workload csv"""
    def test_none_team_in_workload_csv(self) -> None:
        """WHEN the code under test is exercised for: none team in workload csv"""
        p = Person(account_id="u1", display_name="Alice")
        wr = WorkloadRecord(person=p, issue_count=5, story_points=10)
        # Force team to None to simulate edge case
        wr.team = None  # type: ignore[assignment]
        snap = BoardSnapshot(workload_records=[wr])
        csv_str = export_workload_csv(snap)

        """THEN the expected behaviour holds: none team in workload csv"""
        assert "None" not in csv_str, "CSV should not contain 'None' string"

    """GIVEN c s v export none handling and the scenario: empty team in workload csv"""
    def test_empty_team_in_workload_csv(self) -> None:
        """WHEN the code under test is exercised for: empty team in workload csv"""
        p = Person(account_id="u1", display_name="Alice")
        wr = WorkloadRecord(person=p, team="", issue_count=5, story_points=10)
        snap = BoardSnapshot(workload_records=[wr])
        csv_str = export_workload_csv(snap)
        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)

        """THEN the expected behaviour holds: empty team in workload csv"""
        assert rows[1][1] == "", "Empty team should be empty string in CSV"

    """GIVEN c s v export none handling and the scenario: valid team in workload csv"""
    def test_valid_team_in_workload_csv(self) -> None:
        """WHEN the code under test is exercised for: valid team in workload csv"""
        p = Person(account_id="u1", display_name="Alice")
        wr = WorkloadRecord(person=p, team="alpha", issue_count=5, story_points=10)
        snap = BoardSnapshot(workload_records=[wr])
        csv_str = export_workload_csv(snap)
        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)

        """THEN the expected behaviour holds: valid team in workload csv"""
        assert rows[1][1] == "alpha"


# ======================================================================
# timedelta import moved to module level in utils.py
# ======================================================================


class TestUtilsImportFix:
    """Tests for utils import fix."""

    """GIVEN utils import fix and the scenario: timedelta at module level"""
    def test_timedelta_at_module_level(self) -> None:
        """WHEN the code under test is exercised for: timedelta at module level"""
        import inspect

        from flowboard.shared import utils

        source = inspect.getsource(utils.business_days_between)
        # The function body should NOT contain 'from datetime import timedelta'

        """THEN the expected behaviour holds: timedelta at module level"""
        assert "from datetime import timedelta" not in source, (
            "timedelta should be imported at module level, not inside function"
        )

    """GIVEN utils import fix and the scenario: business days between still works"""
    def test_business_days_between_still_works(self) -> None:
        """WHEN the code under test is exercised for: business days between still works"""
        from flowboard.shared.utils import business_days_between

        # Mon-Fri: 5 business days

        """THEN the expected behaviour holds: business days between still works"""
        assert business_days_between(date(2026, 3, 16), date(2026, 3, 20)) == 5
        # Span including weekend
        assert business_days_between(date(2026, 3, 16), date(2026, 3, 22)) == 5
        # Same day (Monday)
        assert business_days_between(date(2026, 3, 16), date(2026, 3, 16)) == 1
        # End before start
        assert business_days_between(date(2026, 3, 20), date(2026, 3, 16)) == 0


# ======================================================================
# PI timeline escapes dynamic content
# ======================================================================


class TestPITimelineXSS:
    """Tests for p i timeline x s s."""

    """GIVEN p i timeline x s s and the scenario: pi name escaped"""
    def test_pi_name_escaped(self) -> None:
        """WHEN the code under test is exercised for: pi name escaped"""
        from flowboard.domain.pi import PISnapshot, PISprintSlot

        slot = PISprintSlot(
            index=1,
            name="Sprint 1",
            start_date=date(2026, 3, 2),
            end_date=date(2026, 3, 13),
            is_current=True,
            working_days_total=10,
            working_days_elapsed=5,
            working_days_remaining=5,
        )
        pi = PISnapshot(
            name="<script>alert(1)</script>",
            start_date=date(2026, 3, 2),
            end_date=date(2026, 4, 24),
            sprints=[slot],
            current_sprint_index=1,
            total_working_days=50,
            elapsed_working_days=5,
            remaining_working_days=45,
            progress_pct=10.0,
            today=date(2026, 3, 9),
        )
        html = pi_timeline_view(pi, [])

        """THEN the expected behaviour holds: pi name escaped"""
        assert "<script>" not in html, "PI name should be HTML-escaped"
        assert "&lt;script&gt;" in html

    """GIVEN p i timeline x s s and the scenario: sprint name escaped in pi view"""
    def test_sprint_name_escaped_in_pi_view(self) -> None:
        """WHEN the code under test is exercised for: sprint name escaped in pi view"""
        from flowboard.domain.pi import PISnapshot, PISprintSlot

        slot = PISprintSlot(
            index=1,
            name="<img src=x onerror=alert(1)>",
            start_date=date(2026, 3, 2),
            end_date=date(2026, 3, 13),
            is_current=False,
            working_days_total=10,
            working_days_elapsed=10,
            working_days_remaining=0,
        )
        pi = PISnapshot(
            name="PI 1",
            start_date=date(2026, 3, 2),
            end_date=date(2026, 3, 13),
            sprints=[slot],
            total_working_days=10,
            elapsed_working_days=10,
            remaining_working_days=0,
            progress_pct=100.0,
            today=date(2026, 3, 14),
        )
        html = pi_timeline_view(pi, [])
        # Raw <img tag must not appear - only escaped version

        """THEN the expected behaviour holds: sprint name escaped in pi view"""
        assert "<img src=" not in html, "Sprint name should be HTML-escaped in PI view"
        assert "&lt;img" in html


# ======================================================================
# JQL injection - project names with quotes escaped
# ======================================================================


class TestJQLInjection:
    """Tests for j q l injection."""

    """GIVEN j q l injection and the scenario: project name with double quote is escaped"""
    def test_project_name_with_double_quote_is_escaped(self) -> None:
        """WHEN the code under test is exercised for: project name with double quote is escaped"""
        from flowboard.infrastructure.jira.connector import JiraConnector

        config = load_config_from_dict(
            {
                "jira": {
                    "base_url": "https://test.atlassian.net",
                    "projects": ['MY"PROJECT'],
                }
            }
        )
        mock_client = MagicMock()
        connector = JiraConnector(mock_client, config)
        jql = connector._build_jql()
        # Invalid project keys (containing quotes) are now rejected entirely

        """THEN the expected behaviour holds: project name with double quote is escaped"""
        assert 'MY"PROJECT' not in jql, "Invalid project key must be rejected"
        # The JQL should be empty since the only project key was invalid
        assert jql == ""

    """GIVEN j q l injection and the scenario: normal project names unchanged"""
    def test_normal_project_names_unchanged(self) -> None:
        """WHEN the code under test is exercised for: normal project names unchanged"""
        from flowboard.infrastructure.jira.connector import JiraConnector

        config = load_config_from_dict(
            {
                "jira": {
                    "base_url": "https://test.atlassian.net",
                    "projects": ["PROJ1", "PROJ2"],
                }
            }
        )
        mock_client = MagicMock()
        connector = JiraConnector(mock_client, config)
        jql = connector._build_jql()

        """THEN the expected behaviour holds: normal project names unchanged"""
        assert '"PROJ1"' in jql
        assert '"PROJ2"' in jql


# ======================================================================
# Retry-After header - float parsing
# ======================================================================


class TestRetryAfterParsing:
    """Tests for retry after parsing."""

    """GIVEN retry after parsing and the scenario: fractional retry after no crash"""
    def test_fractional_retry_after_no_crash(self) -> None:
        """WHEN the code under test is exercised for: fractional retry after no crash"""
        import responses as resp_lib

        from flowboard.infrastructure.config.loader import JiraConfig
        from flowboard.infrastructure.jira.client import JiraClient

        cfg = JiraConfig(
            base_url="https://test.atlassian.net", auth_token="tok", auth_email="e@x.com"
        )
        client = JiraClient(cfg)

        """THEN the expected behaviour holds: fractional retry after no crash"""
        with resp_lib.RequestsMock() as rsps:
            # First call: 429 with fractional Retry-After
            rsps.add(
                resp_lib.GET,
                "https://test.atlassian.net/rest/api/2/serverInfo",
                json={"error": "rate limited"},
                status=429,
                headers={"Retry-After": "1.5"},
            )
            # Second call: success
            rsps.add(
                resp_lib.GET,
                "https://test.atlassian.net/rest/api/2/serverInfo",
                json={"serverTitle": "Jira"},
                status=200,
            )

            result = client.verify_connection()
            assert result["serverTitle"] == "Jira"

    """GIVEN retry after parsing and the scenario: malformed retry after uses fallback"""
    def test_malformed_retry_after_uses_fallback(self) -> None:
        """WHEN the code under test is exercised for: malformed retry after uses fallback"""
        import responses as resp_lib

        from flowboard.infrastructure.config.loader import JiraConfig
        from flowboard.infrastructure.jira.client import JiraClient

        cfg = JiraConfig(
            base_url="https://test.atlassian.net", auth_token="tok", auth_email="e@x.com"
        )
        client = JiraClient(cfg)

        """THEN the expected behaviour holds: malformed retry after uses fallback"""
        with resp_lib.RequestsMock() as rsps:
            rsps.add(
                resp_lib.GET,
                "https://test.atlassian.net/rest/api/2/serverInfo",
                json={"error": "rate limited"},
                status=429,
                headers={"Retry-After": "not-a-number"},
            )
            rsps.add(
                resp_lib.GET,
                "https://test.atlassian.net/rest/api/2/serverInfo",
                json={"serverTitle": "Jira"},
                status=200,
            )

            result = client.verify_connection()
            assert result["serverTitle"] == "Jira"


# ======================================================================
# Error response body no longer leaked
# ======================================================================


class TestErrorResponseSanitisation:
    """Tests for error response sanitisation."""

    """GIVEN error response sanitisation and the scenario: error detail does not contain response body"""
    def test_error_detail_does_not_contain_response_body(self) -> None:
        """WHEN the code under test is exercised for: error detail does not contain response body"""
        import responses as resp_lib

        from flowboard.infrastructure.config.loader import JiraConfig
        from flowboard.infrastructure.jira.client import JiraApiError, JiraClient

        cfg = JiraConfig(
            base_url="https://test.atlassian.net", auth_token="tok", auth_email="e@x.com"
        )
        client = JiraClient(cfg)

        sensitive_body = "java.lang.NullPointerException at com.atlassian.jira.internal.Secret"

        """THEN the expected behaviour holds: error detail does not contain response body"""
        with resp_lib.RequestsMock() as rsps:
            # 500 is not in _BACKOFF_CODES so it raises immediately (no retry)
            rsps.add(
                resp_lib.GET,
                "https://test.atlassian.net/rest/api/2/serverInfo",
                body=sensitive_body,
                status=500,
            )

            with pytest.raises(JiraApiError) as exc_info:
                client.verify_connection()

            error_msg = str(exc_info.value)
            assert "NullPointerException" not in error_msg
            assert "Secret" not in error_msg
            assert "500" in error_msg


# ======================================================================
# Connector narrows exception clause
# ======================================================================


class TestConnectorNarrowedExceptions:
    """Tests for connector narrowed exceptions."""

    """GIVEN connector narrowed exceptions and the scenario: memory error propagates"""
    def test_memory_error_propagates(self) -> None:
        """WHEN the code under test is exercised for: memory error propagates"""
        from flowboard.infrastructure.jira.connector import JiraConnector

        config = load_config_from_dict(
            {"jira": {"base_url": "https://test.atlassian.net", "boards": [1]}}
        )
        mock_client = MagicMock()
        mock_client.get_sprints.side_effect = MemoryError("OOM")

        connector = JiraConnector(mock_client, config)
        with pytest.raises(MemoryError):
            connector._fetch_sprints()


# ======================================================================
# BoardSnapshot.generated_at is now timezone-aware
# ======================================================================


class TestBoardSnapshotTimezone:
    """Tests for board snapshot timezone."""

    """GIVEN board snapshot timezone and the scenario: generated at is timezone aware"""
    def test_generated_at_is_timezone_aware(self) -> None:
        """WHEN the code under test is exercised for: generated at is timezone aware"""
        snap = BoardSnapshot()

        """THEN the expected behaviour holds: generated at is timezone aware"""
        assert snap.generated_at.tzinfo is not None, "generated_at must be timezone-aware"

    """GIVEN board snapshot timezone and the scenario: generated at is utc"""
    def test_generated_at_is_utc(self) -> None:
        """WHEN the code under test is exercised for: generated at is utc"""
        snap = BoardSnapshot()

        """THEN the expected behaviour holds: generated at is utc"""
        assert snap.generated_at.tzinfo == UTC

    """GIVEN board snapshot timezone and the scenario: age days with aware created"""
    def test_age_days_with_aware_created(self) -> None:
        """WHEN the code under test is exercised for: age days with aware created"""
        from datetime import timedelta

        issue = Issue(
            key="T-1",
            summary="Test",
            created=datetime.now(tz=UTC) - timedelta(days=5),
        )

        """THEN the expected behaviour holds: age days with aware created"""
        assert issue.age_days == 5


# ======================================================================
# Config file reads use explicit UTF-8 encoding
# ======================================================================


class TestConfigEncoding:
    """Tests for config encoding."""

    """GIVEN config encoding and the scenario: load config uses utf8"""
    def test_load_config_uses_utf8(self) -> None:
        """WHEN the code under test is exercised for: load config uses utf8"""
        import inspect

        from flowboard.infrastructure.config import loader

        source = inspect.getsource(loader.load_config)

        """THEN the expected behaviour holds: load config uses utf8"""
        assert 'encoding="utf-8"' in source or "encoding='utf-8'" in source

    """GIVEN config encoding and the scenario: schema loader uses utf8"""
    def test_schema_loader_uses_utf8(self) -> None:
        """WHEN the code under test is exercised for: schema loader uses utf8"""
        import inspect

        from flowboard.infrastructure.config import validator

        source = inspect.getsource(validator._load_schema)

        """THEN the expected behaviour holds: schema loader uses utf8"""
        assert 'encoding="utf-8"' in source or "encoding='utf-8'" in source


# ======================================================================
# CSV formula injection protection
# ======================================================================


class TestCSVFormulaInjection:
    """Tests for c s v formula injection."""

    """GIVEN c s v formula injection and the scenario: formula prefix escaped in workload"""
    def test_formula_prefix_escaped_in_workload(self) -> None:
        """WHEN the code under test is exercised for: formula prefix escaped in workload"""
        p = Person(account_id="u1", display_name="=HYPERLINK('http://evil.com')")
        wr = WorkloadRecord(person=p, team="+cmd", issue_count=1, story_points=1)
        snap = BoardSnapshot(workload_records=[wr])
        csv_str = export_workload_csv(snap)
        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)
        # Person name must have prefix quote

        """THEN the expected behaviour holds: formula prefix escaped in workload"""
        assert rows[1][0].startswith("'=")
        # Team must have prefix quote
        assert rows[1][1].startswith("'+")

    """GIVEN c s v formula injection and the scenario: formula prefix escaped in issues"""
    def test_formula_prefix_escaped_in_issues(self) -> None:
        """WHEN the code under test is exercised for: formula prefix escaped in issues"""
        issue = Issue(
            key="T-1",
            summary="=1+1",
            created=datetime.now(tz=UTC),
        )
        snap = BoardSnapshot(issues=[issue])
        csv_str = export_issues_csv(snap)
        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)

        """THEN the expected behaviour holds: formula prefix escaped in issues"""
        assert rows[1][1].startswith("'="), "Summary with = prefix must be escaped"

    """GIVEN c s v formula injection and the scenario: safe values unchanged in csv"""
    def test_safe_values_unchanged_in_csv(self) -> None:
        """WHEN the code under test is exercised for: safe values unchanged in csv"""
        p = Person(account_id="u1", display_name="Alice Johnson")
        wr = WorkloadRecord(person=p, team="alpha", issue_count=1, story_points=1)
        snap = BoardSnapshot(workload_records=[wr])
        csv_str = export_workload_csv(snap)
        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)

        """THEN the expected behaviour holds: safe values unchanged in csv"""
        assert rows[1][0] == "Alice Johnson"
        assert rows[1][1] == "alpha"

    """GIVEN c s v formula injection and the scenario: at prefix escaped"""
    def test_at_prefix_escaped(self) -> None:
        """WHEN the code under test is exercised for: at prefix escaped"""
        p = Person(account_id="u1", display_name="@SUM(A1:A10)")
        wr = WorkloadRecord(person=p, issue_count=1, story_points=1)
        snap = BoardSnapshot(workload_records=[wr])
        csv_str = export_workload_csv(snap)
        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)

        """THEN the expected behaviour holds: at prefix escaped"""
        assert rows[1][0].startswith("'@")

    """GIVEN c s v formula injection and the scenario: risks csv escapes formulas"""
    def test_risks_csv_escapes_formulas(self) -> None:
        """WHEN the code under test is exercised for: risks csv escapes formulas"""
        from flowboard.domain.models import RiskSignal
        from flowboard.shared.types import RiskCategory, RiskSeverity

        rs = RiskSignal(
            severity=RiskSeverity.HIGH,
            category=RiskCategory.OVERLOAD,
            title="-1+1",
            description="Normal",
            recommendation="+cmd|'/C calc'!A0",
        )
        snap = BoardSnapshot(risk_signals=[rs])
        csv_str = export_risks_csv(snap)
        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)

        """THEN the expected behaviour holds: risks csv escapes formulas"""
        assert rows[1][2].startswith("'-"), "Title with - prefix must be escaped"
        assert rows[1][4].startswith("'+"), "Recommendation with + prefix must be escaped"
