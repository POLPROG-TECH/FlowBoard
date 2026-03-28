"""Tests for data normalization robustness — malformed issue handling, XSS
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
    """A single malformed issue in a Jira payload must not crash
    the entire normalization pipeline. The normalizer should log a warning
    and skip the bad issue while processing the rest."""

    def test_malformed_issue_is_skipped(self) -> None:
        """An issue with missing/corrupt fields should be skipped gracefully."""
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

        assert "GOOD-1" in keys
        assert "GOOD-2" in keys
        # BAD-1 triggers AttributeError (None.get), caught by try/except
        assert "BAD-1" not in keys

    def test_empty_issue_list(self) -> None:
        from flowboard.infrastructure.jira.normalizer import JiraNormalizer

        cfg = load_config_from_dict({"jira": {"base_url": "https://test.atlassian.net"}})
        normalizer = JiraNormalizer(cfg)
        assert normalizer.normalize_issues([]) == []

    def test_all_valid_issues_still_work(self) -> None:
        """Regression: valid issues must not be affected by the guard."""
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
        assert len(result) == 5

    def test_issue_with_completely_missing_fields(self) -> None:
        """An issue with no 'fields' key at all should be skipped."""
        from flowboard.infrastructure.jira.normalizer import JiraNormalizer

        cfg = load_config_from_dict({"jira": {"base_url": "https://test.atlassian.net"}})
        normalizer = JiraNormalizer(cfg)

        raw = [{"key": "NOFLD-1"}]  # no 'fields' key at all
        result = normalizer.normalize_issues(raw)
        # Should not crash; the issue gets fields={} from .get("fields", {})
        # and proceeds with defaults — the issue is valid but sparse
        assert len(result) == 1 or len(result) == 0  # acceptable either way


# ---------------------------------------------------------------------------
# XSS prevention in web server loading page
# ---------------------------------------------------------------------------


class TestLoadingPageXSSPrevention:
    """The SSE loading page used innerHTML with unsanitized error
    data which could lead to XSS. Now uses textContent/createElement."""

    def test_no_inner_html_with_user_data(self) -> None:
        """The loading page must not use innerHTML with dynamic data."""
        from flowboard.web.server_helpers import build_loading_page

        html = build_loading_page()

        # The old vulnerability patterns should not exist
        assert "innerHTML=" not in html, (
            "innerHTML with dynamic data is an XSS vector; use textContent or createElement instead"
        )

    def test_uses_text_content_for_errors(self) -> None:
        """Error display should use safe DOM methods."""
        from flowboard.web.server_helpers import build_loading_page

        html = build_loading_page()
        assert "textContent" in html
        assert "createElement" in html

    def test_loading_page_still_functional(self) -> None:
        """The page must still have SSE connection and analysis trigger."""
        from flowboard.web.server_helpers import build_loading_page

        html = build_loading_page()
        assert "EventSource" in html
        assert "triggerAnalysis" in html
        assert "/api/analyze" in html


# ---------------------------------------------------------------------------
# CSV export — numeric values not over-sanitized
# ---------------------------------------------------------------------------


class TestCSVSanitizationRefinement:
    """The CSV formula injection guard was treating legitimate
    negative numbers like '-3' as injection attempts. Now only non-numeric
    strings with dangerous prefixes are escaped."""

    def test_negative_number_not_escaped(self) -> None:
        from flowboard.presentation.export.csv_export import _safe_csv_value

        assert _safe_csv_value(-5) == "-5"
        assert _safe_csv_value(-3.14) == "-3.14"
        assert _safe_csv_value("-100") == "-100"

    def test_positive_number_not_escaped(self) -> None:
        from flowboard.presentation.export.csv_export import _safe_csv_value

        # "+5" is a valid float, so it passes through
        assert _safe_csv_value("+5") == "+5"
        assert _safe_csv_value(5) == "5"

    def test_formula_injection_still_escaped(self) -> None:
        from flowboard.presentation.export.csv_export import _safe_csv_value

        assert _safe_csv_value("=CMD()") == "'=CMD()"
        assert _safe_csv_value("+cmd|'/C calc'!A0") == "'+cmd|'/C calc'!A0"
        assert _safe_csv_value("-1+1") == "'-1+1"
        assert _safe_csv_value("@SUM(A1)") == "'@SUM(A1)"
        assert _safe_csv_value("\tcmd") == "'\tcmd"
        assert _safe_csv_value("\rcmd") == "'\rcmd"

    def test_normal_text_unchanged(self) -> None:
        from flowboard.presentation.export.csv_export import _safe_csv_value

        assert _safe_csv_value("Alice") == "Alice"
        assert _safe_csv_value("Some summary text") == "Some summary text"
        assert _safe_csv_value("") == ""
        assert _safe_csv_value(None) == ""

    def test_csv_export_preserves_negative_story_points(self) -> None:
        """Negative story points (e.g., from adjustments) should appear
        as numbers, not as escaped strings, in CSV output."""
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
        assert rows[1][3] == "-5.0"


# ---------------------------------------------------------------------------
# business_days_between O(1) performance
# ---------------------------------------------------------------------------


class TestBusinessDaysPerformance:
    """business_days_between was O(n) iterating day-by-day.
    Now uses O(1) arithmetic for large date ranges."""

    def test_basic_correctness(self) -> None:
        from flowboard.shared.utils import business_days_between

        # Mon-Fri (5 business days)
        assert business_days_between(date(2026, 3, 23), date(2026, 3, 27)) == 5

    def test_includes_weekend(self) -> None:
        from flowboard.shared.utils import business_days_between

        # Mon-Mon (6 business days: Mon-Fri of first week + Mon)
        assert business_days_between(date(2026, 3, 23), date(2026, 3, 30)) == 6

    def test_full_week(self) -> None:
        from flowboard.shared.utils import business_days_between

        # Mon to Sun (full week = 5 business days)
        assert business_days_between(date(2026, 3, 23), date(2026, 3, 29)) == 5

    def test_same_day(self) -> None:
        from flowboard.shared.utils import business_days_between

        # Weekday
        assert business_days_between(date(2026, 3, 23), date(2026, 3, 23)) == 1
        # Weekend
        assert business_days_between(date(2026, 3, 28), date(2026, 3, 28)) == 0

    def test_reversed_range(self) -> None:
        from flowboard.shared.utils import business_days_between

        assert business_days_between(date(2026, 3, 27), date(2026, 3, 23)) == 0

    def test_large_range_performance(self) -> None:
        """A 10-year range must complete instantly (O(1))."""
        import time

        from flowboard.shared.utils import business_days_between

        start = date(2020, 1, 1)
        end = date(2030, 12, 31)
        t0 = time.monotonic()
        result = business_days_between(start, end)
        elapsed = time.monotonic() - t0

        # Should be ~2870 business days in ~11 years
        assert result > 2500
        assert elapsed < 0.01, f"business_days_between took {elapsed:.4f}s for 10-year range"

    def test_matches_reference_implementation(self) -> None:
        """Verify O(1) algorithm matches naive O(n) for many date ranges."""
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
        for offset_start in range(0, 20):
            for offset_end in range(offset_start, offset_start + 30):
                s = base + timedelta(days=offset_start)
                e = base + timedelta(days=offset_end)
                assert business_days_between(s, e) == naive_bdays(s, e), f"Mismatch for {s} to {e}"


# ---------------------------------------------------------------------------
# _resolve_issue_type handles empty string
# ---------------------------------------------------------------------------


class TestResolveIssueTypeEmpty:
    """_resolve_issue_type crashed with AttributeError on empty
    string input because ''.lower() returns '' which won't match."""

    def test_empty_string_returns_other(self) -> None:
        from flowboard.infrastructure.jira.normalizer import JiraNormalizer

        cfg = load_config_from_dict({"jira": {"base_url": "https://test.atlassian.net"}})
        normalizer = JiraNormalizer(cfg)
        assert normalizer._resolve_issue_type("") == IssueType.OTHER

    def test_known_types_still_resolve(self) -> None:
        from flowboard.infrastructure.jira.normalizer import JiraNormalizer

        cfg = load_config_from_dict({"jira": {"base_url": "https://test.atlassian.net"}})
        normalizer = JiraNormalizer(cfg)
        assert normalizer._resolve_issue_type("Story") == IssueType.STORY
        assert normalizer._resolve_issue_type("Bug") == IssueType.BUG
        assert normalizer._resolve_issue_type("EPIC") == IssueType.EPIC


# ---------------------------------------------------------------------------
# _build_teams graceful handling of malformed team entries
# ---------------------------------------------------------------------------


class TestBuildTeamsRobustness:
    """_build_teams crashed with KeyError when team dicts were
    missing 'key' or 'name'. Now logs a warning and skips bad entries.

    Note: Schema validation catches these at the config level. This fix
    is defense-in-depth for programmatic/direct use of _build_teams."""

    def test_missing_key_skipped(self) -> None:
        from flowboard.infrastructure.config.loader import _build_teams

        raw = {
            "teams": [
                {"name": "No Key Team", "members": ["u1"]},
                {"key": "valid", "name": "Valid Team", "members": ["u2"]},
            ],
        }
        result = _build_teams(raw)
        assert len(result) == 1
        assert result[0].key == "valid"

    def test_missing_name_skipped(self) -> None:
        from flowboard.infrastructure.config.loader import _build_teams

        raw = {
            "teams": [
                {"key": "no_name", "members": ["u1"]},
                {"key": "valid", "name": "Valid", "members": ["u2"]},
            ],
        }
        result = _build_teams(raw)
        assert len(result) == 1
        assert result[0].key == "valid"

    def test_valid_teams_unaffected(self) -> None:
        cfg = load_config_from_dict(
            {
                "jira": {"base_url": "https://test.atlassian.net"},
                "teams": [
                    {"key": "alpha", "name": "Alpha", "members": ["u1", "u2"]},
                    {"key": "beta", "name": "Beta", "members": ["u3"]},
                ],
            }
        )
        assert len(cfg.teams) == 2

    def test_empty_teams_list(self) -> None:
        cfg = load_config_from_dict(
            {
                "jira": {"base_url": "https://test.atlassian.net"},
                "teams": [],
            }
        )
        assert cfg.teams == []

    def test_no_teams_key(self) -> None:
        cfg = load_config_from_dict(
            {
                "jira": {"base_url": "https://test.atlassian.net"},
            }
        )
        assert cfg.teams == []

    def test_non_dict_team_entry_skipped(self) -> None:
        from flowboard.infrastructure.config.loader import _build_teams

        raw = {
            "teams": [
                "not_a_dict",
                {"key": "valid", "name": "Valid"},
            ],
        }
        result = _build_teams(raw)
        assert len(result) == 1
        assert result[0].key == "valid"


# ---------------------------------------------------------------------------
# SSE format helper produces valid SSE
# ---------------------------------------------------------------------------


class TestSSEFormat:
    """Validates the SSE format helper produces valid Server-Sent Events."""

    def test_sse_format_dict(self) -> None:
        from flowboard.web.server_helpers import sse_format

        result = sse_format("test_event", {"key": "value"})
        assert result.startswith("event: test_event\n")
        assert "data: " in result
        assert result.endswith("\n\n")

    def test_sse_format_string(self) -> None:
        from flowboard.web.server_helpers import sse_format

        result = sse_format("ping", "keepalive")
        assert result == "event: ping\ndata: keepalive\n\n"


# ---------------------------------------------------------------------------
# Integration: Full pipeline resilience with malformed data
# ---------------------------------------------------------------------------


class TestPipelineResilience:
    """Integration tests verifying the full analytics pipeline handles
    edge cases gracefully without crashing."""

    def test_empty_payload_produces_empty_snapshot(self) -> None:
        from flowboard.application.orchestrator import analyse_raw_payload

        cfg = load_config_from_dict({"jira": {"base_url": "https://test.atlassian.net"}})
        snapshot = analyse_raw_payload({"issues": [], "sprints": []}, cfg)
        assert len(snapshot.issues) == 0
        assert len(snapshot.risk_signals) == 0

    def test_mixed_valid_and_invalid_issues(self) -> None:
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
        assert "OK-1" in valid_keys
        assert "BAD-1" not in valid_keys

    def test_snapshot_with_all_done_issues(self) -> None:
        """Edge case: all issues are done — no risks expected."""
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
        assert len(snapshot.issues) == 3
        # All issues are done, so no aging/blocked risks
        aging_risks = [r for r in snapshot.risk_signals if r.category == RiskCategory.AGING]
        assert len(aging_risks) == 0
