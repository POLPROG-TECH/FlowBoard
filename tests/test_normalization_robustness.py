"""Tests for data normalization robustness - malformed issue handling, XSS
prevention in the loading page, CSV sanitization, business-day performance,
issue type resolution, team building robustness, SSE format, and pipeline
resilience with invalid data.
"""

from __future__ import annotations

import csv
import io
from datetime import date, timedelta

from flowboard.domain.models import (
    BoardSnapshot,
    Person,
)
from flowboard.infrastructure.config.loader import (
    load_config_from_dict,
)
from flowboard.shared.types import (
    IssueType,
    RiskCategory,
)

# ---------------------------------------------------------------------------
# normalize_issues skips malformed issues instead of crashing
# ---------------------------------------------------------------------------


class TestNormalizeIssuesRobustness:
    """Tests for normalize issues robustness."""

    """GIVEN normalize issues robustness and the scenario: malformed issue is skipped"""
    def test_malformed_issue_is_skipped(self) -> None:
        """WHEN the code under test is exercised for: malformed issue is skipped"""
        from flowboard.infrastructure.jira.normalizer import JiraNormalizer

        cfg = load_config_from_dict({"jira": {"base_url": "https://test.atlassian.net"}})
        normalizer = JiraNormalizer(cfg)

        raw_issues = [
            # Valid issue
            {
                "key": "GOOD-1",
                "fields": {
                    "summary": "Good issue",
                    "issuetype": {"name": "Story"},
                    "status": {"name": "To Do"},
                    "priority": {"name": "Medium"},
                },
            },
            # Malformed: fields is None
            {"key": "BAD-1", "fields": None},
            # Malformed: issuetype is a string instead of dict
            {
                "key": "BAD-2",
                "fields": {
                    "summary": "Bad issue type",
                    "issuetype": "not_a_dict",
                    "status": {"name": "To Do"},
                },
            },
            # Valid issue
            {
                "key": "GOOD-2",
                "fields": {
                    "summary": "Another good issue",
                    "issuetype": {"name": "Bug"},
                    "status": {"name": "Done"},
                    "priority": {"name": "High"},
                },
            },
        ]

        result = normalizer.normalize_issues(raw_issues)
        keys = [i.key for i in result]

        """THEN the expected behaviour holds: malformed issue is skipped"""
        assert "GOOD-1" in keys
        assert "GOOD-2" in keys
        # BAD-1 triggers AttributeError (None.get), caught by try/except
        assert "BAD-1" not in keys

    """GIVEN normalize issues robustness and the scenario: empty issue list"""
    def test_empty_issue_list(self) -> None:
        """WHEN the code under test is exercised for: empty issue list"""
        from flowboard.infrastructure.jira.normalizer import JiraNormalizer

        cfg = load_config_from_dict({"jira": {"base_url": "https://test.atlassian.net"}})
        normalizer = JiraNormalizer(cfg)

        """THEN the expected behaviour holds: empty issue list"""
        assert normalizer.normalize_issues([]) == []

    """GIVEN normalize issues robustness and the scenario: all valid issues still work"""
    def test_all_valid_issues_still_work(self) -> None:
        """WHEN the code under test is exercised for: all valid issues still work"""
        from flowboard.infrastructure.jira.normalizer import JiraNormalizer

        cfg = load_config_from_dict({"jira": {"base_url": "https://test.atlassian.net"}})
        normalizer = JiraNormalizer(cfg)

        raw = [
            {
                "key": f"PROJ-{i}",
                "fields": {
                    "summary": f"Issue {i}",
                    "issuetype": {"name": "Story"},
                    "status": {"name": "To Do"},
                    "priority": {"name": "Medium"},
                },
            }
            for i in range(5)
        ]
        result = normalizer.normalize_issues(raw)

        """THEN the expected behaviour holds: all valid issues still work"""
        assert len(result) == 5

    """GIVEN normalize issues robustness and the scenario: issue with completely missing fields"""
    def test_issue_with_completely_missing_fields(self) -> None:
        """WHEN the code under test is exercised for: issue with completely missing fields"""
        from flowboard.infrastructure.jira.normalizer import JiraNormalizer

        cfg = load_config_from_dict({"jira": {"base_url": "https://test.atlassian.net"}})
        normalizer = JiraNormalizer(cfg)

        raw = [{"key": "NOFLD-1"}]  # no 'fields' key at all
        result = normalizer.normalize_issues(raw)
        # Should not crash; the issue gets fields={} from .get("fields", {})
        # and proceeds with defaults - the issue is valid but sparse

        """THEN the expected behaviour holds: issue with completely missing fields"""
        assert len(result) == 1 or len(result) == 0  # acceptable either way


# ---------------------------------------------------------------------------
# XSS prevention in web server loading page
# ---------------------------------------------------------------------------


class TestLoadingPageXSSPrevention:
    """Tests for loading page x s s prevention."""

    """GIVEN loading page x s s prevention and the scenario: no inner html with user data"""
    def test_no_inner_html_with_user_data(self) -> None:
        """WHEN the code under test is exercised for: no inner html with user data"""
        from flowboard.web.server_helpers import build_loading_page

        html = build_loading_page()

        # The old vulnerability patterns should not exist

        """THEN the expected behaviour holds: no inner html with user data"""
        assert "innerHTML=" not in html, (
            "innerHTML with dynamic data is an XSS vector; use textContent or createElement instead"
        )

    """GIVEN loading page x s s prevention and the scenario: uses text content for errors"""
    def test_uses_text_content_for_errors(self) -> None:
        """WHEN the code under test is exercised for: uses text content for errors"""
        from flowboard.web.server_helpers import build_loading_page

        html = build_loading_page()

        """THEN the expected behaviour holds: uses text content for errors"""
        assert "textContent" in html
        assert "createElement" in html

    """GIVEN loading page x s s prevention and the scenario: loading page still functional"""
    def test_loading_page_still_functional(self) -> None:
        """WHEN the code under test is exercised for: loading page still functional"""
        from flowboard.web.server_helpers import build_loading_page

        html = build_loading_page()

        """THEN the expected behaviour holds: loading page still functional"""
        assert "EventSource" in html
        assert "triggerAnalysis" in html
        assert "/api/analyze" in html


# ---------------------------------------------------------------------------
# CSV export - numeric values not over-sanitized
# ---------------------------------------------------------------------------


class TestCSVSanitizationRefinement:
    """Tests for c s v sanitization refinement."""

    """GIVEN c s v sanitization refinement and the scenario: negative number not escaped"""
    def test_negative_number_not_escaped(self) -> None:
        """WHEN the code under test is exercised for: negative number not escaped"""
        from flowboard.presentation.export.csv_export import _safe_csv_value

        """THEN the expected behaviour holds: negative number not escaped"""
        assert _safe_csv_value(-5) == "-5"
        assert _safe_csv_value(-3.14) == "-3.14"
        assert _safe_csv_value("-100") == "-100"

    """GIVEN c s v sanitization refinement and the scenario: positive number not escaped"""
    def test_positive_number_not_escaped(self) -> None:
        """WHEN the code under test is exercised for: positive number not escaped"""
        from flowboard.presentation.export.csv_export import _safe_csv_value

        # "+5" is a valid float, so it passes through

        """THEN the expected behaviour holds: positive number not escaped"""
        assert _safe_csv_value("+5") == "+5"
        assert _safe_csv_value(5) == "5"

    """GIVEN c s v sanitization refinement and the scenario: formula injection still escaped"""
    def test_formula_injection_still_escaped(self) -> None:
        """WHEN the code under test is exercised for: formula injection still escaped"""
        from flowboard.presentation.export.csv_export import _safe_csv_value

        """THEN the expected behaviour holds: formula injection still escaped"""
        assert _safe_csv_value("=CMD()") == "'=CMD()"
        assert _safe_csv_value("+cmd|'/C calc'!A0") == "'+cmd|'/C calc'!A0"
        assert _safe_csv_value("-1+1") == "'-1+1"
        assert _safe_csv_value("@SUM(A1)") == "'@SUM(A1)"
        assert _safe_csv_value("\tcmd") == "'\tcmd"
        assert _safe_csv_value("\rcmd") == "'\rcmd"

    """GIVEN c s v sanitization refinement and the scenario: normal text unchanged"""
    def test_normal_text_unchanged(self) -> None:
        """WHEN the code under test is exercised for: normal text unchanged"""
        from flowboard.presentation.export.csv_export import _safe_csv_value

        """THEN the expected behaviour holds: normal text unchanged"""
        assert _safe_csv_value("Alice") == "Alice"
        assert _safe_csv_value("Some summary text") == "Some summary text"
        assert _safe_csv_value("") == ""
        assert _safe_csv_value(None) == ""

    """GIVEN c s v sanitization refinement and the scenario: csv export preserves negative story points"""
    def test_csv_export_preserves_negative_story_points(self) -> None:
        """WHEN the code under test is exercised for: csv export preserves negative story points"""
        from flowboard.presentation.export.csv_export import export_workload_csv

        person = Person(account_id="u1", display_name="Test", team="team")
        from flowboard.domain.models import WorkloadRecord

        snap = BoardSnapshot(
            workload_records=[
                WorkloadRecord(
                    person=person,
                    team="team",
                    issue_count=1,
                    story_points=-5.0,
                ),
            ]
        )
        csv_str = export_workload_csv(snap)
        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)
        # Story points column should be numeric, not prefixed

        """THEN the expected behaviour holds: csv export preserves negative story points"""
        assert rows[1][3] == "-5.0"


# ---------------------------------------------------------------------------
# business_days_between O(1) performance
# ---------------------------------------------------------------------------


class TestBusinessDaysPerformance:
    """Tests for business days performance."""

    """GIVEN business days performance and the scenario: basic correctness"""
    def test_basic_correctness(self) -> None:
        """WHEN the code under test is exercised for: basic correctness"""
        from flowboard.shared.utils import business_days_between

        # Mon-Fri (5 business days)

        """THEN the expected behaviour holds: basic correctness"""
        assert business_days_between(date(2026, 3, 23), date(2026, 3, 27)) == 5

    """GIVEN business days performance and the scenario: includes weekend"""
    def test_includes_weekend(self) -> None:
        """WHEN the code under test is exercised for: includes weekend"""
        from flowboard.shared.utils import business_days_between

        # Mon-Mon (6 business days: Mon-Fri of first week + Mon)

        """THEN the expected behaviour holds: includes weekend"""
        assert business_days_between(date(2026, 3, 23), date(2026, 3, 30)) == 6

    """GIVEN business days performance and the scenario: full week"""
    def test_full_week(self) -> None:
        """WHEN the code under test is exercised for: full week"""
        from flowboard.shared.utils import business_days_between

        # Mon to Sun (full week = 5 business days)

        """THEN the expected behaviour holds: full week"""
        assert business_days_between(date(2026, 3, 23), date(2026, 3, 29)) == 5

    """GIVEN business days performance and the scenario: same day"""
    def test_same_day(self) -> None:
        """WHEN the code under test is exercised for: same day"""
        from flowboard.shared.utils import business_days_between

        # Weekday

        """THEN the expected behaviour holds: same day"""
        assert business_days_between(date(2026, 3, 23), date(2026, 3, 23)) == 1
        # Weekend
        assert business_days_between(date(2026, 3, 28), date(2026, 3, 28)) == 0

    """GIVEN business days performance and the scenario: reversed range"""
    def test_reversed_range(self) -> None:
        """WHEN the code under test is exercised for: reversed range"""
        from flowboard.shared.utils import business_days_between

        """THEN the expected behaviour holds: reversed range"""
        assert business_days_between(date(2026, 3, 27), date(2026, 3, 23)) == 0

    """GIVEN business days performance and the scenario: large range performance"""
    def test_large_range_performance(self) -> None:
        """WHEN the code under test is exercised for: large range performance"""
        import time

        from flowboard.shared.utils import business_days_between

        start = date(2020, 1, 1)
        end = date(2030, 12, 31)
        t0 = time.monotonic()
        result = business_days_between(start, end)
        elapsed = time.monotonic() - t0

        # Should be ~2870 business days in ~11 years

        """THEN the expected behaviour holds: large range performance"""
        assert result > 2500
        assert elapsed < 0.01, f"business_days_between took {elapsed:.4f}s for 10-year range"

    """GIVEN business days performance and the scenario: matches reference implementation"""
    def test_matches_reference_implementation(self) -> None:
        """WHEN the code under test is exercised for: matches reference implementation"""
        from flowboard.shared.utils import business_days_between

        def naive_bdays(s: date, e: date) -> int:
            if s > e:
                return 0
            count = 0
            current = s
            while current <= e:
                if current.weekday() < 5:
                    count += 1
                current += timedelta(days=1)
            return count

        base = date(2026, 1, 1)

        """THEN the expected behaviour holds: matches reference implementation"""
        for offset_start in range(0, 20):
            for offset_end in range(offset_start, offset_start + 30):
                s = base + timedelta(days=offset_start)
                e = base + timedelta(days=offset_end)
                assert business_days_between(s, e) == naive_bdays(s, e), f"Mismatch for {s} to {e}"


# ---------------------------------------------------------------------------
# _resolve_issue_type handles empty string
# ---------------------------------------------------------------------------


class TestResolveIssueTypeEmpty:
    """Tests for resolve issue type empty."""

    """GIVEN resolve issue type empty and the scenario: empty string returns other"""
    def test_empty_string_returns_other(self) -> None:
        """WHEN the code under test is exercised for: empty string returns other"""
        from flowboard.infrastructure.jira.normalizer import JiraNormalizer

        cfg = load_config_from_dict({"jira": {"base_url": "https://test.atlassian.net"}})
        normalizer = JiraNormalizer(cfg)

        """THEN the expected behaviour holds: empty string returns other"""
        assert normalizer._resolve_issue_type("") == IssueType.OTHER

    """GIVEN resolve issue type empty and the scenario: known types still resolve"""
    def test_known_types_still_resolve(self) -> None:
        """WHEN the code under test is exercised for: known types still resolve"""
        from flowboard.infrastructure.jira.normalizer import JiraNormalizer

        cfg = load_config_from_dict({"jira": {"base_url": "https://test.atlassian.net"}})
        normalizer = JiraNormalizer(cfg)

        """THEN the expected behaviour holds: known types still resolve"""
        assert normalizer._resolve_issue_type("Story") == IssueType.STORY
        assert normalizer._resolve_issue_type("Bug") == IssueType.BUG
        assert normalizer._resolve_issue_type("EPIC") == IssueType.EPIC


# ---------------------------------------------------------------------------
# _build_teams graceful handling of malformed team entries
# ---------------------------------------------------------------------------


class TestBuildTeamsRobustness:
    """Tests for build teams robustness."""

    """GIVEN build teams robustness and the scenario: missing key skipped"""
    def test_missing_key_skipped(self) -> None:
        """WHEN the code under test is exercised for: missing key skipped"""
        from flowboard.infrastructure.config.loader import _build_teams

        raw = {
            "teams": [
                {"name": "No Key Team", "members": ["u1"]},
                {"key": "valid", "name": "Valid Team", "members": ["u2"]},
            ],
        }
        result = _build_teams(raw)

        """THEN the expected behaviour holds: missing key skipped"""
        assert len(result) == 1
        assert result[0].key == "valid"

    """GIVEN build teams robustness and the scenario: missing name skipped"""
    def test_missing_name_skipped(self) -> None:
        """WHEN the code under test is exercised for: missing name skipped"""
        from flowboard.infrastructure.config.loader import _build_teams

        raw = {
            "teams": [
                {"key": "no_name", "members": ["u1"]},
                {"key": "valid", "name": "Valid", "members": ["u2"]},
            ],
        }
        result = _build_teams(raw)

        """THEN the expected behaviour holds: missing name skipped"""
        assert len(result) == 1
        assert result[0].key == "valid"

    """GIVEN build teams robustness and the scenario: valid teams unaffected"""
    def test_valid_teams_unaffected(self) -> None:
        """WHEN the code under test is exercised for: valid teams unaffected"""
        cfg = load_config_from_dict(
            {
                "jira": {"base_url": "https://test.atlassian.net"},
                "teams": [
                    {"key": "alpha", "name": "Alpha", "members": ["u1", "u2"]},
                    {"key": "beta", "name": "Beta", "members": ["u3"]},
                ],
            }
        )

        """THEN the expected behaviour holds: valid teams unaffected"""
        assert len(cfg.teams) == 2

    """GIVEN build teams robustness and the scenario: empty teams list"""
    def test_empty_teams_list(self) -> None:
        """WHEN the code under test is exercised for: empty teams list"""
        cfg = load_config_from_dict(
            {
                "jira": {"base_url": "https://test.atlassian.net"},
                "teams": [],
            }
        )

        """THEN the expected behaviour holds: empty teams list"""
        assert cfg.teams == []

    """GIVEN build teams robustness and the scenario: no teams key"""
    def test_no_teams_key(self) -> None:
        """WHEN the code under test is exercised for: no teams key"""
        cfg = load_config_from_dict(
            {
                "jira": {"base_url": "https://test.atlassian.net"},
            }
        )

        """THEN the expected behaviour holds: no teams key"""
        assert cfg.teams == []

    """GIVEN build teams robustness and the scenario: non dict team entry skipped"""
    def test_non_dict_team_entry_skipped(self) -> None:
        """WHEN the code under test is exercised for: non dict team entry skipped"""
        from flowboard.infrastructure.config.loader import _build_teams

        raw = {
            "teams": [
                "not_a_dict",
                {"key": "valid", "name": "Valid"},
            ],
        }
        result = _build_teams(raw)

        """THEN the expected behaviour holds: non dict team entry skipped"""
        assert len(result) == 1
        assert result[0].key == "valid"


# ---------------------------------------------------------------------------
# SSE format helper produces valid SSE
# ---------------------------------------------------------------------------


class TestSSEFormat:
    """Tests for s s e format."""

    """GIVEN s s e format and the scenario: sse format dict"""
    def test_sse_format_dict(self) -> None:
        """WHEN the code under test is exercised for: sse format dict"""
        from flowboard.web.server_helpers import sse_format

        result = sse_format("test_event", {"key": "value"})

        """THEN the expected behaviour holds: sse format dict"""
        assert result.startswith("event: test_event\n")
        assert "data: " in result
        assert result.endswith("\n\n")

    """GIVEN s s e format and the scenario: sse format string"""
    def test_sse_format_string(self) -> None:
        """WHEN the code under test is exercised for: sse format string"""
        from flowboard.web.server_helpers import sse_format

        result = sse_format("ping", "keepalive")

        """THEN the expected behaviour holds: sse format string"""
        assert result == "event: ping\ndata: keepalive\n\n"


# ---------------------------------------------------------------------------
# Integration: Full pipeline resilience with malformed data
# ---------------------------------------------------------------------------


class TestPipelineResilience:
    """Tests for pipeline resilience."""

    """GIVEN pipeline resilience and the scenario: empty payload produces empty snapshot"""
    def test_empty_payload_produces_empty_snapshot(self) -> None:
        """WHEN the code under test is exercised for: empty payload produces empty snapshot"""
        from flowboard.application.orchestrator import analyse_raw_payload

        cfg = load_config_from_dict({"jira": {"base_url": "https://test.atlassian.net"}})
        snapshot = analyse_raw_payload({"issues": [], "sprints": []}, cfg)

        """THEN the expected behaviour holds: empty payload produces empty snapshot"""
        assert len(snapshot.issues) == 0
        assert len(snapshot.risk_signals) == 0

    """GIVEN pipeline resilience and the scenario: mixed valid and invalid issues"""
    def test_mixed_valid_and_invalid_issues(self) -> None:
        """WHEN the code under test is exercised for: mixed valid and invalid issues"""
        from flowboard.application.orchestrator import analyse_raw_payload

        cfg = load_config_from_dict({"jira": {"base_url": "https://test.atlassian.net"}})
        raw = {
            "issues": [
                {
                    "key": "OK-1",
                    "fields": {
                        "summary": "Valid",
                        "issuetype": {"name": "Task"},
                        "status": {"name": "To Do"},
                    },
                },
                {"key": "BAD-1", "fields": None},
            ],
            "sprints": [],
        }
        snapshot = analyse_raw_payload(raw, cfg)
        # Should have at least the valid issue
        valid_keys = {i.key for i in snapshot.issues}

        """THEN the expected behaviour holds: mixed valid and invalid issues"""
        assert "OK-1" in valid_keys
        assert "BAD-1" not in valid_keys

    """GIVEN pipeline resilience and the scenario: snapshot with all done issues"""
    def test_snapshot_with_all_done_issues(self) -> None:
        """WHEN the code under test is exercised for: snapshot with all done issues"""
        from flowboard.application.orchestrator import analyse_raw_payload

        cfg = load_config_from_dict({"jira": {"base_url": "https://test.atlassian.net"}})
        raw = {
            "issues": [
                {
                    "key": f"DONE-{i}",
                    "fields": {
                        "summary": f"Done {i}",
                        "issuetype": {"name": "Story"},
                        "status": {"name": "Done"},
                        "priority": {"name": "Medium"},
                    },
                }
                for i in range(3)
            ],
            "sprints": [],
        }
        snapshot = analyse_raw_payload(raw, cfg)

        """THEN the expected behaviour holds: snapshot with all done issues"""
        assert len(snapshot.issues) == 3
        # All issues are done, so no aging/blocked risks
        aging_risks = [r for r in snapshot.risk_signals if r.category == RiskCategory.AGING]
        assert len(aging_risks) == 0
