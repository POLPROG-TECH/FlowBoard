"""Tests for security and sanitization — XSS prevention across all components,
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
    """Verify that user-controlled content is HTML-escaped in all components."""

    XSS_SCRIPT = '<script>alert("xss")</script>'
    XSS_IMG = '<img src=x onerror=alert(1)>'
    XSS_ENCODED_SCRIPT = "&lt;script&gt;"  # what escaped version should contain

    def _make_person(self, name: str = "Alice") -> Person:
        return Person(account_id="u1", display_name=name, team="alpha")

    def _make_issue(self, key: str = "T-1", summary: str = "Test", assignee: Person | None = None) -> Issue:
        return Issue(
            key=key,
            summary=summary,
            issue_type=IssueType.STORY,
            status=IssueStatus.OTHER,
            status_category=StatusCategory.TODO,
            assignee=assignee or self._make_person(),
            created=datetime(2026, 3, 1, tzinfo=UTC),
        )

    def test_workload_table_escapes_person_name(self) -> None:
        p = self._make_person(self.XSS_SCRIPT)
        wr = WorkloadRecord(person=p, team="alpha", issue_count=1, story_points=5)
        html = workload_table([wr])
        assert "<script>" not in html
        assert self.XSS_ENCODED_SCRIPT in html

    def test_workload_table_escapes_team_name(self) -> None:
        p = self._make_person()
        wr = WorkloadRecord(person=p, team=self.XSS_SCRIPT, issue_count=1, story_points=5)
        html = workload_table([wr])
        assert "<script>" not in html

    def test_risk_table_escapes_title(self) -> None:
        signal = RiskSignal(
            severity=RiskSeverity.HIGH,
            category=RiskCategory.OVERLOAD,
            title=self.XSS_SCRIPT,
            description="Normal",
            recommendation="Normal",
        )
        html = risk_table([signal])
        assert "<script>" not in html
        assert self.XSS_ENCODED_SCRIPT in html

    def test_risk_table_escapes_recommendation(self) -> None:
        signal = RiskSignal(
            severity=RiskSeverity.HIGH,
            category=RiskCategory.OVERLOAD,
            title="Normal",
            description="Normal",
            recommendation=self.XSS_IMG,
        )
        html = risk_table([signal])
        # Ensure the raw <img tag is not present — only the escaped form
        assert "<img src=" not in html
        assert "&lt;img" in html

    def test_sprint_health_escapes_sprint_name(self) -> None:
        sp = Sprint(id=1, name=self.XSS_SCRIPT, state=SprintState.ACTIVE, start_date=date(2026, 3, 1), end_date=date(2026, 3, 14))
        sh = SprintHealth(sprint=sp, total_issues=10, done_issues=5)
        html = sprint_health_cards([sh])
        assert "<script>" not in html
        assert self.XSS_ENCODED_SCRIPT in html

    def test_roadmap_escapes_key(self) -> None:
        ri = RoadmapItem(key=self.XSS_SCRIPT, title="Normal", status=StatusCategory.TODO)
        html = roadmap_timeline([ri])
        assert "<script>" not in html

    def test_roadmap_escapes_owner_name(self) -> None:
        p = self._make_person(self.XSS_IMG)
        ri = RoadmapItem(key="E-1", title="Normal", owner=p, status=StatusCategory.TODO)
        html = roadmap_timeline([ri])
        # Raw <img tag must not appear — only escaped version
        assert "<img src=" not in html
        assert "&lt;img" in html

    def test_issues_table_escapes_key(self) -> None:
        issue = self._make_issue(key=self.XSS_SCRIPT)
        html = issues_table([issue])
        assert "<script>" not in html

    def test_issues_table_escapes_assignee_name(self) -> None:
        p = self._make_person(self.XSS_IMG)
        issue = self._make_issue(assignee=p)
        html = issues_table([issue])
        # Raw <img tag must not appear
        assert "<img src=" not in html
        assert "&lt;img" in html

    def test_issues_table_escapes_sprint_name(self) -> None:
        sp = Sprint(id=1, name=self.XSS_SCRIPT, state=SprintState.ACTIVE)
        issue = self._make_issue()
        issue.sprint = sp
        html = issues_table([issue])
        assert "<script>" not in html

    def test_conflict_list_escapes_description(self) -> None:
        c = OverlapConflict(
            category="resource_contention",
            severity=RiskSeverity.HIGH,
            description=self.XSS_SCRIPT,
            recommendation=self.XSS_IMG,
        )
        html = conflict_list([c])
        assert "<script>" not in html
        # Raw <img tag must not appear
        assert "<img src=" not in html

    def test_dependency_table_escapes_keys(self) -> None:
        dep = Dependency(
            source_key=self.XSS_SCRIPT,
            target_key=self.XSS_IMG,
            link_type=LinkType.BLOCKS,
            source_status=StatusCategory.TODO,
            target_status=StatusCategory.TODO,
        )
        snap = BoardSnapshot(dependencies=[dep])
        html = dependency_table(snap)
        assert "<script>" not in html
        # Raw <img tag must not appear
        assert "<img src=" not in html


# ======================================================================
# Connector re-raises JiraAuthError instead of swallowing it
# ======================================================================


class TestConnectorAuthErrorPropagation:
    """Verify that JiraAuthError is not swallowed during sprint fetching."""

    def test_auth_error_propagates_from_sprint_fetch(self) -> None:
        from flowboard.infrastructure.jira.client import JiraAuthError
        from flowboard.infrastructure.jira.connector import JiraConnector

        config = load_config_from_dict({"jira": {"base_url": "https://test.atlassian.net", "boards": [1]}})
        mock_client = MagicMock()
        mock_client.get_sprints.side_effect = JiraAuthError(401, "Unauthorized")

        connector = JiraConnector(mock_client, config)

        with pytest.raises(JiraAuthError):
            connector._fetch_sprints()

    def test_non_auth_errors_are_still_swallowed(self) -> None:
        from flowboard.infrastructure.jira.client import JiraApiError
        from flowboard.infrastructure.jira.connector import JiraConnector

        config = load_config_from_dict({"jira": {"base_url": "https://test.atlassian.net", "boards": [1]}})
        mock_client = MagicMock()
        mock_client.get_sprints.side_effect = JiraApiError(500, "Internal error")

        connector = JiraConnector(mock_client, config)
        # Should NOT raise — Jira API errors for individual boards are caught
        result = connector._fetch_sprints()
        assert result == []

    def test_unexpected_errors_propagate(self) -> None:
        """Narrowed except clause no longer swallows programming errors."""
        from flowboard.infrastructure.jira.connector import JiraConnector

        config = load_config_from_dict({"jira": {"base_url": "https://test.atlassian.net", "boards": [1]}})
        mock_client = MagicMock()
        mock_client.get_sprints.side_effect = RuntimeError("Bug in code")

        connector = JiraConnector(mock_client, config)
        with pytest.raises(RuntimeError, match="Bug in code"):
            connector._fetch_sprints()


# ======================================================================
# locale.getdefaultlocale() replaced with locale.getlocale()
# ======================================================================


class TestLocaleDetectionDeprecation:
    """Verify that detect_locale does not use the deprecated getdefaultlocale."""

    def test_detect_locale_does_not_use_deprecated_api(self) -> None:
        import inspect

        from flowboard.i18n.translator import detect_locale
        source = inspect.getsource(detect_locale)
        assert "getdefaultlocale" not in source, \
            "detect_locale still uses deprecated locale.getdefaultlocale()"

    def test_detect_locale_returns_valid_locale(self) -> None:
        from flowboard.i18n.translator import detect_locale
        result = detect_locale()
        assert result in ("en", "pl")

    def test_detect_locale_no_deprecation_warnings(self) -> None:
        import warnings

        from flowboard.i18n.translator import detect_locale
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            detect_locale()
            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) == 0, \
                f"detect_locale raised DeprecationWarning: {deprecation_warnings}"


# ======================================================================
# CSV export writes empty string instead of "None" for missing team
# ======================================================================


class TestCSVExportNoneHandling:
    """Verify that None values in CSV export become empty strings, not 'None'."""

    def test_none_team_in_workload_csv(self) -> None:
        p = Person(account_id="u1", display_name="Alice")
        wr = WorkloadRecord(person=p, issue_count=5, story_points=10)
        # Force team to None to simulate edge case
        wr.team = None  # type: ignore[assignment]
        snap = BoardSnapshot(workload_records=[wr])
        csv_str = export_workload_csv(snap)
        assert "None" not in csv_str, "CSV should not contain 'None' string"

    def test_empty_team_in_workload_csv(self) -> None:
        p = Person(account_id="u1", display_name="Alice")
        wr = WorkloadRecord(person=p, team="", issue_count=5, story_points=10)
        snap = BoardSnapshot(workload_records=[wr])
        csv_str = export_workload_csv(snap)
        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)
        assert rows[1][1] == "", "Empty team should be empty string in CSV"

    def test_valid_team_in_workload_csv(self) -> None:
        p = Person(account_id="u1", display_name="Alice")
        wr = WorkloadRecord(person=p, team="alpha", issue_count=5, story_points=10)
        snap = BoardSnapshot(workload_records=[wr])
        csv_str = export_workload_csv(snap)
        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)
        assert rows[1][1] == "alpha"


# ======================================================================
# timedelta import moved to module level in utils.py
# ======================================================================


class TestUtilsImportFix:
    """Verify timedelta is imported at module level."""

    def test_timedelta_at_module_level(self) -> None:
        import inspect

        from flowboard.shared import utils
        source = inspect.getsource(utils.business_days_between)
        # The function body should NOT contain 'from datetime import timedelta'
        assert "from datetime import timedelta" not in source, \
            "timedelta should be imported at module level, not inside function"

    def test_business_days_between_still_works(self) -> None:
        from flowboard.shared.utils import business_days_between
        # Mon-Fri: 5 business days
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
    """Verify PI timeline view properly escapes all dynamic content."""

    def test_pi_name_escaped(self) -> None:
        from flowboard.domain.pi import PISnapshot, PISprintSlot
        slot = PISprintSlot(
            index=1, name="Sprint 1", start_date=date(2026, 3, 2),
            end_date=date(2026, 3, 13), is_current=True,
            working_days_total=10, working_days_elapsed=5, working_days_remaining=5,
        )
        pi = PISnapshot(
            name='<script>alert(1)</script>',
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
        assert "<script>" not in html, "PI name should be HTML-escaped"
        assert "&lt;script&gt;" in html

    def test_sprint_name_escaped_in_pi_view(self) -> None:
        from flowboard.domain.pi import PISnapshot, PISprintSlot
        slot = PISprintSlot(
            index=1, name='<img src=x onerror=alert(1)>',
            start_date=date(2026, 3, 2), end_date=date(2026, 3, 13),
            is_current=False, working_days_total=10,
            working_days_elapsed=10, working_days_remaining=0,
        )
        pi = PISnapshot(
            name="PI 1", start_date=date(2026, 3, 2),
            end_date=date(2026, 3, 13), sprints=[slot],
            total_working_days=10, elapsed_working_days=10,
            remaining_working_days=0, progress_pct=100.0,
            today=date(2026, 3, 14),
        )
        html = pi_timeline_view(pi, [])
        # Raw <img tag must not appear — only escaped version
        assert "<img src=" not in html, "Sprint name should be HTML-escaped in PI view"
        assert "&lt;img" in html


# ======================================================================
# JQL injection — project names with quotes escaped
# ======================================================================


class TestJQLInjection:
    """Verify JQL construction escapes special characters in project names."""

    def test_project_name_with_double_quote_is_escaped(self) -> None:
        from flowboard.infrastructure.jira.connector import JiraConnector

        config = load_config_from_dict({
            "jira": {
                "base_url": "https://test.atlassian.net",
                "projects": ['MY"PROJECT'],
            }
        })
        mock_client = MagicMock()
        connector = JiraConnector(mock_client, config)
        jql = connector._build_jql()
        # Invalid project keys (containing quotes) are now rejected entirely
        assert 'MY"PROJECT' not in jql, "Invalid project key must be rejected"
        # The JQL should be empty since the only project key was invalid
        assert jql == ""

    def test_normal_project_names_unchanged(self) -> None:
        from flowboard.infrastructure.jira.connector import JiraConnector

        config = load_config_from_dict({
            "jira": {
                "base_url": "https://test.atlassian.net",
                "projects": ["PROJ1", "PROJ2"],
            }
        })
        mock_client = MagicMock()
        connector = JiraConnector(mock_client, config)
        jql = connector._build_jql()
        assert '"PROJ1"' in jql
        assert '"PROJ2"' in jql


# ======================================================================
# Retry-After header — float parsing
# ======================================================================


class TestRetryAfterParsing:
    """Verify Retry-After header handles fractional and malformed values."""

    def test_fractional_retry_after_no_crash(self) -> None:
        """float('1.5') must not crash like int('1.5') did."""
        import responses as resp_lib

        from flowboard.infrastructure.config.loader import JiraConfig
        from flowboard.infrastructure.jira.client import JiraClient

        cfg = JiraConfig(base_url="https://test.atlassian.net", auth_token="tok", auth_email="e@x.com")
        client = JiraClient(cfg)

        with resp_lib.RequestsMock() as rsps:
            # First call: 429 with fractional Retry-After
            rsps.add(resp_lib.GET, "https://test.atlassian.net/rest/api/2/serverInfo",
                     json={"error": "rate limited"}, status=429,
                     headers={"Retry-After": "1.5"})
            # Second call: success
            rsps.add(resp_lib.GET, "https://test.atlassian.net/rest/api/2/serverInfo",
                     json={"serverTitle": "Jira"}, status=200)

            result = client.verify_connection()
            assert result["serverTitle"] == "Jira"

    def test_malformed_retry_after_uses_fallback(self) -> None:
        """Non-numeric Retry-After must not crash; fallback to exponential backoff."""
        import responses as resp_lib

        from flowboard.infrastructure.config.loader import JiraConfig
        from flowboard.infrastructure.jira.client import JiraClient

        cfg = JiraConfig(base_url="https://test.atlassian.net", auth_token="tok", auth_email="e@x.com")
        client = JiraClient(cfg)

        with resp_lib.RequestsMock() as rsps:
            rsps.add(resp_lib.GET, "https://test.atlassian.net/rest/api/2/serverInfo",
                     json={"error": "rate limited"}, status=429,
                     headers={"Retry-After": "not-a-number"})
            rsps.add(resp_lib.GET, "https://test.atlassian.net/rest/api/2/serverInfo",
                     json={"serverTitle": "Jira"}, status=200)

            result = client.verify_connection()
            assert result["serverTitle"] == "Jira"


# ======================================================================
# Error response body no longer leaked
# ======================================================================


class TestErrorResponseSanitisation:
    """Verify API error exceptions don't leak server internals."""

    def test_error_detail_does_not_contain_response_body(self) -> None:
        import responses as resp_lib

        from flowboard.infrastructure.config.loader import JiraConfig
        from flowboard.infrastructure.jira.client import JiraApiError, JiraClient

        cfg = JiraConfig(base_url="https://test.atlassian.net", auth_token="tok", auth_email="e@x.com")
        client = JiraClient(cfg)

        sensitive_body = "java.lang.NullPointerException at com.atlassian.jira.internal.Secret"
        with resp_lib.RequestsMock() as rsps:
            # 500 is not in _BACKOFF_CODES so it raises immediately (no retry)
            rsps.add(resp_lib.GET, "https://test.atlassian.net/rest/api/2/serverInfo",
                     body=sensitive_body, status=500)

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
    """Verify system-level errors now propagate from sprint fetch."""

    def test_memory_error_propagates(self) -> None:
        from flowboard.infrastructure.jira.connector import JiraConnector

        config = load_config_from_dict({"jira": {"base_url": "https://test.atlassian.net", "boards": [1]}})
        mock_client = MagicMock()
        mock_client.get_sprints.side_effect = MemoryError("OOM")

        connector = JiraConnector(mock_client, config)
        with pytest.raises(MemoryError):
            connector._fetch_sprints()


# ======================================================================
# BoardSnapshot.generated_at is now timezone-aware
# ======================================================================


class TestBoardSnapshotTimezone:
    """Verify generated_at uses UTC timezone."""

    def test_generated_at_is_timezone_aware(self) -> None:
        snap = BoardSnapshot()
        assert snap.generated_at.tzinfo is not None, \
            "generated_at must be timezone-aware"

    def test_generated_at_is_utc(self) -> None:
        snap = BoardSnapshot()
        assert snap.generated_at.tzinfo == UTC

    def test_age_days_with_aware_created(self) -> None:
        """Issue with tz-aware created no longer risks TypeError."""
        from datetime import timedelta
        issue = Issue(
            key="T-1", summary="Test",
            created=datetime.now(tz=UTC) - timedelta(days=5),
        )
        assert issue.age_days == 5


# ======================================================================
# Config file reads use explicit UTF-8 encoding
# ======================================================================


class TestConfigEncoding:
    """Verify config and schema loading specify encoding."""

    def test_load_config_uses_utf8(self) -> None:
        import inspect

        from flowboard.infrastructure.config import loader
        source = inspect.getsource(loader.load_config)
        assert 'encoding="utf-8"' in source or "encoding='utf-8'" in source

    def test_schema_loader_uses_utf8(self) -> None:
        import inspect

        from flowboard.infrastructure.config import validator
        source = inspect.getsource(validator._load_schema)
        assert 'encoding="utf-8"' in source or "encoding='utf-8'" in source


# ======================================================================
# CSV formula injection protection
# ======================================================================


class TestCSVFormulaInjection:
    """Verify dangerous cell prefixes are neutralised in CSV exports."""

    def test_formula_prefix_escaped_in_workload(self) -> None:
        p = Person(account_id="u1", display_name="=HYPERLINK('http://evil.com')")
        wr = WorkloadRecord(person=p, team="+cmd", issue_count=1, story_points=1)
        snap = BoardSnapshot(workload_records=[wr])
        csv_str = export_workload_csv(snap)
        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)
        # Person name must have prefix quote
        assert rows[1][0].startswith("'=")
        # Team must have prefix quote
        assert rows[1][1].startswith("'+")

    def test_formula_prefix_escaped_in_issues(self) -> None:
        issue = Issue(
            key="T-1",
            summary="=1+1",
            created=datetime.now(tz=UTC),
        )
        snap = BoardSnapshot(issues=[issue])
        csv_str = export_issues_csv(snap)
        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)
        assert rows[1][1].startswith("'="), "Summary with = prefix must be escaped"

    def test_safe_values_unchanged_in_csv(self) -> None:
        p = Person(account_id="u1", display_name="Alice Johnson")
        wr = WorkloadRecord(person=p, team="alpha", issue_count=1, story_points=1)
        snap = BoardSnapshot(workload_records=[wr])
        csv_str = export_workload_csv(snap)
        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)
        assert rows[1][0] == "Alice Johnson"
        assert rows[1][1] == "alpha"

    def test_at_prefix_escaped(self) -> None:
        p = Person(account_id="u1", display_name="@SUM(A1:A10)")
        wr = WorkloadRecord(person=p, issue_count=1, story_points=1)
        snap = BoardSnapshot(workload_records=[wr])
        csv_str = export_workload_csv(snap)
        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)
        assert rows[1][0].startswith("'@")

    def test_risks_csv_escapes_formulas(self) -> None:
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
        assert rows[1][2].startswith("'-"), "Title with - prefix must be escaped"
        assert rows[1][4].startswith("'+"), "Recommendation with + prefix must be escaped"
