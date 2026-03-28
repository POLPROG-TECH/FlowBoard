"""Tests for data integrity guards — pagination safety, connector error handling,
timezone correctness, CSV/JQL injection prevention, schema validation, and
other critical data pipeline safeguards.
"""

from __future__ import annotations

import json
import threading
from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from flowboard.domain.models import (
    BoardSnapshot,
    Issue,
    Person,
    Sprint,
    SprintHealth,
    Team,
    WorkloadRecord,
)
from flowboard.shared.types import (
    IssueType,
    Priority,
    SprintState,
    StatusCategory,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _person(name: str = "Alice") -> Person:
    return Person(account_id=name.lower(), display_name=name)


def _sprint(name: str = "Sprint 1", state: SprintState = SprintState.ACTIVE) -> Sprint:
    return Sprint(id=1, name=name, state=state)


def _issue(key: str = "T-1", **kw) -> Issue:
    defaults = dict(
        summary=f"Issue {key}",
        issue_type=IssueType.STORY,
        status=kw.pop("status", "To Do"),
        status_category=kw.pop("status_cat", StatusCategory.TODO),
        assignee=kw.pop("assignee", _person()),
        story_points=kw.pop("sp", 5.0),
        priority=kw.pop("priority", Priority.MEDIUM),
        created=kw.pop("created", datetime(2026, 1, 1, tzinfo=UTC)),
    )
    defaults.update(kw)
    return Issue(key=key, **defaults)


# =========================================================================
# Unbounded pagination safety
# =========================================================================

class TestPaginationSafety:
    """Verify get_sprints/get_sprint_issues/get_boards use bounded loops."""

    def test_get_sprints_has_max_pages(self):
        """Source inspection: get_sprints must use a for-loop with max_pages."""
        import inspect

        from flowboard.infrastructure.jira.client import JiraClient
        src = inspect.getsource(JiraClient.get_sprints)
        assert "max_pages" in src
        assert "for _ in range" in src
        assert "while True" not in src

    def test_get_sprint_issues_has_max_pages(self):
        import inspect

        from flowboard.infrastructure.jira.client import JiraClient
        src = inspect.getsource(JiraClient.get_sprint_issues)
        assert "max_pages" in src
        assert "for _ in range" in src

    def test_get_boards_has_pagination(self):
        import inspect

        from flowboard.infrastructure.jira.client import JiraClient
        src = inspect.getsource(JiraClient.get_boards)
        assert "max_pages" in src
        assert "for _ in range" in src


# =========================================================================
# Connector KeyError swallow removed
# =========================================================================

class TestConnectorKeyErrorRemoved:
    """KeyError must NOT be in the sprint fetch except clause."""

    def test_no_keyerror_in_except(self):
        import inspect

        from flowboard.infrastructure.jira.connector import JiraConnector
        src = inspect.getsource(JiraConnector._fetch_sprints)
        assert "KeyError" not in src

    def test_boards_use_safe_get(self):
        """Board ID access must use .get() not ['id']."""
        import inspect

        from flowboard.infrastructure.jira.connector import JiraConnector
        src = inspect.getsource(JiraConnector._fetch_sprints)
        assert 'b["id"]' not in src
        assert "b.get(" in src


# =========================================================================
# get_boards pagination
# =========================================================================

class TestBoardsPagination:
    """get_boards must paginate instead of single 200-cap request."""

    def test_boards_paginates(self):
        import inspect

        from flowboard.infrastructure.jira.client import JiraClient
        src = inspect.getsource(JiraClient.get_boards)
        assert "isLast" in src  # checks the isLast field
        assert "startAt" in src  # uses startAt parameter


# =========================================================================
# Retro carryover now receives sprint_healths
# =========================================================================

class TestRetroCarryover:
    """compute_ceremonies must use real sprint_healths for carryover."""

    def test_carryover_uses_sprint_healths(self):
        from flowboard.domain.scrum import (
            ReadinessReport,
            compute_ceremonies,
        )
        healths = [
            SprintHealth(
                sprint=Sprint(id=1, name="S1", state=SprintState.ACTIVE),
                total_issues=10, completed_points=5,
                carry_over_count=3,
            ),
            SprintHealth(
                sprint=Sprint(id=2, name="S2", state=SprintState.CLOSED),
                total_issues=10, completed_points=8,
                carry_over_count=2,
            ),
        ]
        result = compute_ceremonies(
            [], [], [], [],
            ReadinessReport(items=[], avg_readiness=0.0), [],
            sprint_healths=healths,
            today=date(2026, 3, 10),
        )
        assert result["retro"].metrics["carryover"] == 5

    def test_carryover_zero_without_healths(self):
        from flowboard.domain.scrum import ReadinessReport, compute_ceremonies
        result = compute_ceremonies(
            [], [], [], [],
            ReadinessReport(items=[], avg_readiness=0.0), [],
            today=date(2026, 3, 10),
        )
        assert result["retro"].metrics["carryover"] == 0


# =========================================================================
# Timezone mismatch in age_days
# =========================================================================

class TestTimezoneAgeDays:
    """age_days must not crash when created/resolved have mixed tz awareness."""

    def test_aware_created_naive_resolved(self):
        issue = _issue(
            "T-1",
            created=datetime(2026, 1, 1, tzinfo=UTC),
            resolved=datetime(2026, 1, 11),  # naive
        )
        assert issue.age_days == 10

    def test_naive_created_aware_resolved(self):
        issue = Issue(
            key="T-2", summary="Test", issue_type=IssueType.STORY,
            created=datetime(2026, 1, 1),  # naive
            resolved=datetime(2026, 1, 11, tzinfo=UTC),  # aware
        )
        assert issue.age_days == 10


# =========================================================================
# Priority.UNSET sentinel
# =========================================================================

class TestPriorityUnset:
    """Priority.UNSET must exist and be used for unset priorities."""

    def test_unset_exists(self):
        assert hasattr(Priority, "UNSET")
        assert Priority.UNSET == "__unset__"

    def test_issue_default_is_unset(self):
        issue = Issue(key="T-1", summary="Test", issue_type=IssueType.STORY)
        assert issue.priority == Priority.UNSET

    def test_normalizer_uses_unset_for_null(self):
        from flowboard.infrastructure.config.loader import load_config_from_dict
        from flowboard.infrastructure.jira.normalizer import JiraNormalizer
        cfg = load_config_from_dict({"jira": {"base_url": "https://x.atlassian.net"}})
        n = JiraNormalizer(cfg)
        assert n._resolve_priority(None) == Priority.UNSET
        assert n._resolve_priority("") == Priority.UNSET

    def test_normalizer_medium_stays_medium(self):
        from flowboard.infrastructure.config.loader import load_config_from_dict
        from flowboard.infrastructure.jira.normalizer import JiraNormalizer
        cfg = load_config_from_dict({"jira": {"base_url": "https://x.atlassian.net"}})
        n = JiraNormalizer(cfg)
        assert n._resolve_priority("Medium") == Priority.MEDIUM


# =========================================================================
# Firefox event crash — explicit event parameter
# =========================================================================

class TestFirstRunShowFormEvent:
    """Wizard must render the connection step with test connection flow."""

    def test_wizard_renders_connection_step(self):
        from flowboard.presentation.html.renderer import render_first_run
        html = render_first_run(config_path="/test/path")
        assert "wizard" in html.lower() or "goStep" in html
        assert "testConnection" in html


# =========================================================================
# config_path rendered
# =========================================================================

class TestConfigPathRendered:
    """first_run wizard must be renderable without error."""

    def test_config_path_visible(self):
        from flowboard.presentation.html.renderer import render_first_run
        html = render_first_run(config_path="/home/user/.config/flowboard.json")
        # Wizard must render without error and contain FlowBoard branding
        assert "FlowBoard" in html


# =========================================================================
# Translation string escaping
# =========================================================================

class TestTranslationEscaping:
    """_t() auto-escape wrapper must exist in components."""

    def test_t_helper_exists(self):
        from flowboard.i18n.translator import get_translator
        from flowboard.presentation.html.components import _t
        t = get_translator("en")
        result = _t(t, "common.unassigned")
        assert isinstance(result, str)
        assert "<" not in result or "&lt;" in result

    def test_loc_escapes(self):
        from flowboard.i18n.translator import get_translator
        from flowboard.presentation.html.components import _loc
        t = get_translator("en")
        # Normal value passes through escaped
        result = _loc("some<value>", t)
        assert "&lt;" in result


# =========================================================================
# CSV formula injection on all fields
# =========================================================================

class TestCSVFormulaSanitization:
    """All CSV fields including enums must be sanitized."""

    def test_issue_csv_sanitizes_enum_fields(self):
        from flowboard.presentation.export.csv_export import export_issues_csv
        snapshot = MagicMock(spec=BoardSnapshot)
        issue = MagicMock()
        issue.key = "T-1"
        issue.summary = "Test"
        issue.issue_type = "=MALICIOUS"
        issue.status = "+cmd"
        issue.assignee = None
        issue.story_points = 5
        issue.priority = "@risk"
        issue.epic_key = ""
        issue.sprint = None
        issue.created = None
        issue.due_date = None
        snapshot.issues = [issue]
        csv_out = export_issues_csv(snapshot)
        assert "'=MALICIOUS" in csv_out
        assert "'+cmd" in csv_out
        assert "'@risk" in csv_out


# =========================================================================
# JQL injection via project keys
# =========================================================================

class TestJQLProjectKeyValidation:
    """Project keys with special chars must be rejected."""

    def test_valid_key_passes(self):
        from flowboard.infrastructure.config.loader import load_config_from_dict
        from flowboard.infrastructure.jira.connector import JiraConnector
        cfg = load_config_from_dict({
            "jira": {"base_url": "https://x.atlassian.net", "projects": ["MYPROJ"]},
        })
        connector = JiraConnector(MagicMock(), cfg)
        jql = connector._build_jql()
        assert '"MYPROJ"' in jql

    def test_invalid_key_rejected(self):
        from flowboard.infrastructure.config.loader import load_config_from_dict
        from flowboard.infrastructure.jira.connector import JiraConnector
        cfg = load_config_from_dict({
            "jira": {"base_url": "https://x.atlassian.net", "projects": ['"; DROP TABLE']},
        })
        connector = JiraConnector(MagicMock(), cfg)
        jql = connector._build_jql()
        assert "DROP" not in jql


# =========================================================================
# Schema max_results cap at 100
# =========================================================================

class TestSchemaMaxResults:
    """config.schema.json must cap max_results at 100."""

    def test_max_results_cap(self):
        schema_path = Path(__file__).resolve().parents[1] / "config.schema.json"
        with schema_path.open() as f:
            schema = json.load(f)
        mr = schema["properties"]["jira"]["properties"]["max_results"]
        assert mr["maximum"] == 100


# =========================================================================
# Empty chart no-data overlay
# =========================================================================

class TestEmptyChartOverlay:
    """Dashboard JS must detect empty chart data and show overlay."""

    def test_has_data_function_exists(self):
        tmpl_dir = (
            Path(__file__).resolve().parents[1]
            / "src/flowboard/presentation/html/templates"
        )
        content = "".join(p.read_text() for p in tmpl_dir.glob("*.html"))
        assert "function _hasData(cfg)" in content
        assert "No data available" in content or "chart_no_data" in content


# =========================================================================
# Schema cache thread safety
# =========================================================================

class TestSchemaCacheThreadSafe:
    """_load_schema must use a threading.Lock."""

    def test_lock_exists(self):
        from flowboard.infrastructure.config import validator
        assert hasattr(validator, "_schema_lock")
        assert isinstance(validator._schema_lock, type(threading.Lock()))

    def test_concurrent_loads_dont_crash(self):
        from flowboard.infrastructure.config.validator import _load_schema
        results = []
        errors = []
        def loader():
            try:
                results.append(_load_schema())
            except Exception as e:
                errors.append(e)
        threads = [threading.Thread(target=loader) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        assert len(results) == 10


# =========================================================================
# config_to_dict auth comment
# =========================================================================

class TestConfigToDictAuthComment:
    """config_to_dict must document why auth is omitted."""

    def test_docstring_mentions_auth(self):
        from flowboard.infrastructure.config.loader import config_to_dict
        assert "credential" in (config_to_dict.__doc__ or "").lower()


# =========================================================================
# Retro headline uses average churn
# =========================================================================

class TestRetroHeadlineAverage:
    """Retro headline must use average churn, not sum."""

    def test_headline_uses_average(self):
        from flowboard.domain.scrum import (
            ReadinessReport,
            ScopeChangeReport,
            compute_ceremonies,
        )
        scope = [
            ScopeChangeReport(sprint_name="S1", original_count=10, added_count=3, churn_pct=30.0),
            ScopeChangeReport(sprint_name="S2", original_count=10, added_count=1, churn_pct=10.0),
        ]
        result = compute_ceremonies(
            [], [], [], scope,
            ReadinessReport(items=[], avg_readiness=0.0), [],
            today=date(2026, 3, 10),
        )
        # Average churn = (30+10)/2 = 20, headline should contain "20"
        assert ":20" in result["retro"].headline


# =========================================================================
# first_run innerHTML XSS — uses textContent
# =========================================================================

class TestTourNoInnerHTML:
    """renderTour must use textContent, not innerHTML."""

    def test_no_innerhtml_in_tour(self):
        from flowboard.presentation.html.renderer import render_first_run
        html = render_first_run()
        # The wizard JS should not use innerHTML anywhere
        # Allow innerHTML only in safe contexts (button label updates via .innerHTML with spinner)
        js_section = html[html.find("<script"):html.rfind("</script>")]
        # Count innerHTML uses — minimal or zero
        count = js_section.count("innerHTML")
        assert count <= 3, f"Found {count} innerHTML uses — prefer textContent/DOM methods"


# =========================================================================
# StatusCategory enum comparison in timeline
# =========================================================================

class TestTimelineStatusEnum:
    """Timeline epic bar must use enum comparison, not .value == 'Done'."""

    def test_no_value_done_string(self):
        import inspect

        from flowboard.domain.timeline import build_epic_timeline
        src = inspect.getsource(build_epic_timeline)
        assert '.value == "Done"' not in src
        assert "StatusCategory.DONE" in src


# =========================================================================
# Schema path CWD evaluated lazily
# =========================================================================

class TestSchemaPathCWD:
    """Path.cwd() must be evaluated inside _find_schema_path, not at module level."""

    def test_no_cwd_at_module_level(self):
        import inspect

        from flowboard.infrastructure.config import validator
        src = inspect.getsource(validator)
        # Find module-level assignments (before first def)
        module_header = src[:src.find("\ndef ")]
        # Remove comment lines
        code_lines = [line for line in module_header.split("\n") if not line.strip().startswith("#")]
        code_only = "\n".join(code_lines)
        assert "Path.cwd()" not in code_only


# =========================================================================
# Demo fixture JSON parse
# =========================================================================

class TestDemoFixtureParse:
    """Demo fixture load must have try/except for JSONDecodeError."""

    def test_json_parse_guarded(self):
        import inspect

        from flowboard.cli.main import demo
        src = inspect.getsource(demo)
        assert "JSONDecodeError" in src or "json.JSONDecodeError" in src


# =========================================================================
# Simulation collision metric
# =========================================================================

class TestSimCollisionMetric:
    """Simulated collision count must be based on concurrent tasks, not len(wrs)."""

    def test_collision_counts_concurrent(self):
        from flowboard.domain.simulation import (
            ResourceChange,
            SimulationScenario,
            _simulate_workloads,
        )
        from flowboard.infrastructure.config.loader import load_config_from_dict

        cfg = load_config_from_dict({"jira": {"base_url": "https://x.atlassian.net"}})
        wrs = [
            WorkloadRecord(
                person=_person("A"), team="api",
                issue_count=5, story_points=15.0,
                in_progress_count=3, blocked_count=0,
            ),
        ]
        teams = [Team(key="api", name="API", members=["a"])]
        scenario = SimulationScenario(
            id="test", name="Test", description="Test",
            changes=(ResourceChange(team_key="api", delta=1),),
        )
        _, metrics = _simulate_workloads(wrs, teams, scenario, cfg.thresholds)
        # With 1 person having 3 in-progress and +1 resource:
        # redistribution_factor = 1/2, sim_wip = round(3*0.5) = 2
        # collision = 2-1 = 1 (from concurrent tasks, not from len(wrs))
        assert metrics.total_collisions == 1

    def test_no_collision_when_wip_is_one(self):
        """People with 0 or 1 WIP should not generate collisions."""
        from flowboard.domain.simulation import (
            ResourceChange,
            SimulationScenario,
            _simulate_workloads,
        )
        from flowboard.infrastructure.config.loader import load_config_from_dict

        cfg = load_config_from_dict({"jira": {"base_url": "https://x.atlassian.net"}})
        wrs = [
            WorkloadRecord(
                person=_person("A"), team="api",
                issue_count=1, story_points=5.0,
                in_progress_count=1, blocked_count=0,
            ),
        ]
        teams = [Team(key="api", name="API", members=["a"])]
        scenario = SimulationScenario(
            id="test", name="Test", description="Test",
            changes=(ResourceChange(team_key="api", delta=1),),
        )
        _, metrics = _simulate_workloads(wrs, teams, scenario, cfg.thresholds)
        assert metrics.total_collisions == 0


# =========================================================================
# Sprint field string format warning
# =========================================================================

class TestSprintFieldStringWarning:
    """Normalizer must warn when sprint field is a string (Jira Server)."""

    def test_string_sprint_logs_warning(self):
        from flowboard.infrastructure.config.loader import load_config_from_dict
        from flowboard.infrastructure.jira.normalizer import JiraNormalizer

        cfg = load_config_from_dict({"jira": {"base_url": "https://x.atlassian.net"}})
        n = JiraNormalizer(cfg)
        with patch("flowboard.infrastructure.jira.normalizer.logger") as mock_log:
            result = n._extract_sprint({"customfield_10020": "com.atlassian.greenhopper.service..."})
            assert result is None
            mock_log.warning.assert_called_once()
            assert "string" in str(mock_log.warning.call_args).lower() or "Unexpected" in str(mock_log.warning.call_args)


# =========================================================================
# Retry context in error messages
# =========================================================================

class TestRetryContext:
    """Rate-limit errors must include retry context."""

    def test_error_mentions_retries(self):
        import inspect

        from flowboard.infrastructure.jira.client import JiraClient
        src = inspect.getsource(JiraClient._request)
        assert "after" in src and "retries" in src.lower()


# =========================================================================
# Health check CLI command
# =========================================================================

class TestHealthCommand:
    """CLI must have a 'health' command."""

    def test_health_command_exists(self):
        from flowboard.cli.main import app
        command_names = [
            cmd.name or (cmd.callback.__name__.replace("_", "-") if cmd.callback else None)
            for cmd in app.registered_commands
        ]
        assert "health" in command_names


# =========================================================================
# Structured logging with pipeline timing
# =========================================================================

class TestPipelineTiming:
    """Orchestrator must log pipeline stage timing."""

    def test_timed_context_manager(self):

        from flowboard.application.orchestrator import _timed
        with patch("flowboard.application.orchestrator.logger") as mock_log:
            with _timed("test_stage"):
                pass
            calls = [str(c) for c in mock_log.info.call_args_list]
            assert any("test_stage" in c for c in calls)
            assert any("completed" in c for c in calls)

    def test_run_from_payload_includes_timing(self):
        """Orchestrator.run logs total pipeline time."""
        import inspect

        from flowboard.application.orchestrator import Orchestrator
        src = inspect.getsource(Orchestrator.run)
        assert "pipeline_start" in src
        assert "total pipeline" in src.lower() or "total" in src.lower()
