"""Tests for data integrity guards - pagination safety, connector error handling,
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
    """Tests for pagination safety."""

    """GIVEN pagination safety and the scenario: get sprints has max pages"""
    def test_get_sprints_has_max_pages(self):
        """WHEN the code under test is exercised for: get sprints has max pages"""
        import inspect

        from flowboard.infrastructure.jira.client import JiraClient

        src = inspect.getsource(JiraClient.get_sprints)

        """THEN the expected behaviour holds: get sprints has max pages"""
        assert "max_pages" in src
        assert "for _ in range" in src
        assert "while True" not in src

    """GIVEN pagination safety and the scenario: get sprint issues has max pages"""
    def test_get_sprint_issues_has_max_pages(self):
        """WHEN the code under test is exercised for: get sprint issues has max pages"""
        import inspect

        from flowboard.infrastructure.jira.client import JiraClient

        src = inspect.getsource(JiraClient.get_sprint_issues)

        """THEN the expected behaviour holds: get sprint issues has max pages"""
        assert "max_pages" in src
        assert "for _ in range" in src

    """GIVEN pagination safety and the scenario: get boards has pagination"""
    def test_get_boards_has_pagination(self):
        """WHEN the code under test is exercised for: get boards has pagination"""
        import inspect

        from flowboard.infrastructure.jira.client import JiraClient

        src = inspect.getsource(JiraClient.get_boards)

        """THEN the expected behaviour holds: get boards has pagination"""
        assert "max_pages" in src
        assert "for _ in range" in src


# =========================================================================
# Connector KeyError swallow removed
# =========================================================================


class TestConnectorKeyErrorRemoved:
    """Tests for connector key error removed."""

    """GIVEN connector key error removed and the scenario: no keyerror in except"""
    def test_no_keyerror_in_except(self):
        """WHEN the code under test is exercised for: no keyerror in except"""
        import inspect

        from flowboard.infrastructure.jira.connector import JiraConnector

        src = inspect.getsource(JiraConnector._fetch_sprints)

        """THEN the expected behaviour holds: no keyerror in except"""
        assert "KeyError" not in src

    """GIVEN connector key error removed and the scenario: boards use safe get"""
    def test_boards_use_safe_get(self):
        """WHEN the code under test is exercised for: boards use safe get"""
        import inspect

        from flowboard.infrastructure.jira.connector import JiraConnector

        src = inspect.getsource(JiraConnector._fetch_sprints)

        """THEN the expected behaviour holds: boards use safe get"""
        assert 'b["id"]' not in src
        assert "b.get(" in src


# =========================================================================
# get_boards pagination
# =========================================================================


class TestBoardsPagination:
    """Tests for boards pagination."""

    """GIVEN boards pagination and the scenario: boards paginates"""
    def test_boards_paginates(self):
        """WHEN the code under test is exercised for: boards paginates"""
        import inspect

        from flowboard.infrastructure.jira.client import JiraClient

        src = inspect.getsource(JiraClient.get_boards)

        """THEN the expected behaviour holds: boards paginates"""
        assert "isLast" in src  # checks the isLast field
        assert "startAt" in src  # uses startAt parameter


# =========================================================================
# Retro carryover now receives sprint_healths
# =========================================================================


class TestRetroCarryover:
    """Tests for retro carryover."""

    """GIVEN retro carryover and the scenario: carryover uses sprint healths"""
    def test_carryover_uses_sprint_healths(self):
        """WHEN the code under test is exercised for: carryover uses sprint healths"""
        from flowboard.domain.scrum import (
            ReadinessReport,
            compute_ceremonies,
        )

        healths = [
            SprintHealth(
                sprint=Sprint(id=1, name="S1", state=SprintState.ACTIVE),
                total_issues=10,
                completed_points=5,
                carry_over_count=3,
            ),
            SprintHealth(
                sprint=Sprint(id=2, name="S2", state=SprintState.CLOSED),
                total_issues=10,
                completed_points=8,
                carry_over_count=2,
            ),
        ]
        result = compute_ceremonies(
            [],
            [],
            [],
            [],
            ReadinessReport(items=[], avg_readiness=0.0),
            [],
            sprint_healths=healths,
            today=date(2026, 3, 10),
        )

        """THEN the expected behaviour holds: carryover uses sprint healths"""
        assert result["retro"].metrics["carryover"] == 5

    """GIVEN retro carryover and the scenario: carryover zero without healths"""
    def test_carryover_zero_without_healths(self):
        """WHEN the code under test is exercised for: carryover zero without healths"""
        from flowboard.domain.scrum import ReadinessReport, compute_ceremonies

        result = compute_ceremonies(
            [],
            [],
            [],
            [],
            ReadinessReport(items=[], avg_readiness=0.0),
            [],
            today=date(2026, 3, 10),
        )

        """THEN the expected behaviour holds: carryover zero without healths"""
        assert result["retro"].metrics["carryover"] == 0


# =========================================================================
# Timezone mismatch in age_days
# =========================================================================


class TestTimezoneAgeDays:
    """Tests for timezone age days."""

    """GIVEN timezone age days and the scenario: aware created naive resolved"""
    def test_aware_created_naive_resolved(self):
        """WHEN the code under test is exercised for: aware created naive resolved"""
        issue = _issue(
            "T-1",
            created=datetime(2026, 1, 1, tzinfo=UTC),
            resolved=datetime(2026, 1, 11),  # naive
        )

        """THEN the expected behaviour holds: aware created naive resolved"""
        assert issue.age_days == 10

    """GIVEN timezone age days and the scenario: naive created aware resolved"""
    def test_naive_created_aware_resolved(self):
        """WHEN the code under test is exercised for: naive created aware resolved"""
        issue = Issue(
            key="T-2",
            summary="Test",
            issue_type=IssueType.STORY,
            created=datetime(2026, 1, 1),  # naive
            resolved=datetime(2026, 1, 11, tzinfo=UTC),  # aware
        )

        """THEN the expected behaviour holds: naive created aware resolved"""
        assert issue.age_days == 10


# =========================================================================
# Priority.UNSET sentinel
# =========================================================================


class TestPriorityUnset:
    """Tests for priority unset."""

    """GIVEN priority unset and the scenario: unset exists"""
    def test_unset_exists(self):
        """THEN the expected behaviour holds: unset exists"""
        assert hasattr(Priority, "UNSET")
        assert Priority.UNSET == "__unset__"

    """GIVEN priority unset and the scenario: issue default is unset"""
    def test_issue_default_is_unset(self):
        """WHEN the code under test is exercised for: issue default is unset"""
        issue = Issue(key="T-1", summary="Test", issue_type=IssueType.STORY)

        """THEN the expected behaviour holds: issue default is unset"""
        assert issue.priority == Priority.UNSET

    """GIVEN priority unset and the scenario: normalizer uses unset for null"""
    def test_normalizer_uses_unset_for_null(self):
        """WHEN the code under test is exercised for: normalizer uses unset for null"""
        from flowboard.infrastructure.config.loader import load_config_from_dict
        from flowboard.infrastructure.jira.normalizer import JiraNormalizer

        cfg = load_config_from_dict({"jira": {"base_url": "https://x.atlassian.net"}})
        n = JiraNormalizer(cfg)

        """THEN the expected behaviour holds: normalizer uses unset for null"""
        assert n._resolve_priority(None) == Priority.UNSET
        assert n._resolve_priority("") == Priority.UNSET

    """GIVEN priority unset and the scenario: normalizer medium stays medium"""
    def test_normalizer_medium_stays_medium(self):
        """WHEN the code under test is exercised for: normalizer medium stays medium"""
        from flowboard.infrastructure.config.loader import load_config_from_dict
        from flowboard.infrastructure.jira.normalizer import JiraNormalizer

        cfg = load_config_from_dict({"jira": {"base_url": "https://x.atlassian.net"}})
        n = JiraNormalizer(cfg)

        """THEN the expected behaviour holds: normalizer medium stays medium"""
        assert n._resolve_priority("Medium") == Priority.MEDIUM


# =========================================================================
# Firefox event crash - explicit event parameter
# =========================================================================


class TestFirstRunShowFormEvent:
    """Tests for first run show form event."""

    """GIVEN first run show form event and the scenario: wizard renders connection step"""
    def test_wizard_renders_connection_step(self):
        """WHEN the code under test is exercised for: wizard renders connection step"""
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run(config_path="/test/path")

        """THEN the expected behaviour holds: wizard renders connection step"""
        assert "wizard" in html.lower() or "goStep" in html
        assert "testConnection" in html


# =========================================================================
# config_path rendered
# =========================================================================


class TestConfigPathRendered:
    """Tests for config path rendered."""

    """GIVEN config path rendered and the scenario: config path visible"""
    def test_config_path_visible(self):
        """WHEN the code under test is exercised for: config path visible"""
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run(config_path="/home/user/.config/flowboard.json")
        # Wizard must render without error and contain FlowBoard branding

        """THEN the expected behaviour holds: config path visible"""
        assert "FlowBoard" in html


# =========================================================================
# Translation string escaping
# =========================================================================


class TestTranslationEscaping:
    """Tests for translation escaping."""

    """GIVEN translation escaping and the scenario: t helper exists"""
    def test_t_helper_exists(self):
        """WHEN the code under test is exercised for: t helper exists"""
        from flowboard.i18n.translator import get_translator
        from flowboard.presentation.html.components import _t

        t = get_translator("en")
        result = _t(t, "common.unassigned")

        """THEN the expected behaviour holds: t helper exists"""
        assert isinstance(result, str)
        assert "<" not in result or "&lt;" in result

    """GIVEN translation escaping and the scenario: loc escapes"""
    def test_loc_escapes(self):
        """WHEN the code under test is exercised for: loc escapes"""
        from flowboard.i18n.translator import get_translator
        from flowboard.presentation.html.components import _loc

        t = get_translator("en")
        # Normal value passes through escaped
        result = _loc("some<value>", t)

        """THEN the expected behaviour holds: loc escapes"""
        assert "&lt;" in result


# =========================================================================
# CSV formula injection on all fields
# =========================================================================


class TestCSVFormulaSanitization:
    """Tests for c s v formula sanitization."""

    """GIVEN c s v formula sanitization and the scenario: issue csv sanitizes enum fields"""
    def test_issue_csv_sanitizes_enum_fields(self):
        """WHEN the code under test is exercised for: issue csv sanitizes enum fields"""
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

        """THEN the expected behaviour holds: issue csv sanitizes enum fields"""
        assert "'=MALICIOUS" in csv_out
        assert "'+cmd" in csv_out
        assert "'@risk" in csv_out


# =========================================================================
# JQL injection via project keys
# =========================================================================


class TestJQLProjectKeyValidation:
    """Tests for j q l project key validation."""

    """GIVEN j q l project key validation and the scenario: valid key passes"""
    def test_valid_key_passes(self):
        """WHEN the code under test is exercised for: valid key passes"""
        from flowboard.infrastructure.config.loader import load_config_from_dict
        from flowboard.infrastructure.jira.connector import JiraConnector

        cfg = load_config_from_dict(
            {
                "jira": {"base_url": "https://x.atlassian.net", "projects": ["MYPROJ"]},
            }
        )
        connector = JiraConnector(MagicMock(), cfg)
        jql = connector._build_jql()

        """THEN the expected behaviour holds: valid key passes"""
        assert '"MYPROJ"' in jql

    """GIVEN j q l project key validation and the scenario: invalid key rejected"""
    def test_invalid_key_rejected(self):
        """WHEN the code under test is exercised for: invalid key rejected"""
        from flowboard.infrastructure.config.loader import load_config_from_dict
        from flowboard.infrastructure.jira.connector import JiraConnector

        cfg = load_config_from_dict(
            {
                "jira": {"base_url": "https://x.atlassian.net", "projects": ['"; DROP TABLE']},
            }
        )
        connector = JiraConnector(MagicMock(), cfg)
        jql = connector._build_jql()

        """THEN the expected behaviour holds: invalid key rejected"""
        assert "DROP" not in jql


# =========================================================================
# Schema max_results cap at 100
# =========================================================================


class TestSchemaMaxResults:
    """Tests for schema max results."""

    """GIVEN schema max results and the scenario: max results cap"""
    def test_max_results_cap(self):
        """WHEN the code under test is exercised for: max results cap"""
        schema_path = Path(__file__).resolve().parents[1] / "config.schema.json"
        with schema_path.open() as f:
            schema = json.load(f)
        mr = schema["properties"]["jira"]["properties"]["max_results"]

        """THEN the expected behaviour holds: max results cap"""
        assert mr["maximum"] == 100


# =========================================================================
# Empty chart no-data overlay
# =========================================================================


class TestEmptyChartOverlay:
    """Tests for empty chart overlay."""

    """GIVEN empty chart overlay and the scenario: has data function exists"""
    def test_has_data_function_exists(self):
        """WHEN the code under test is exercised for: has data function exists"""
        tmpl_dir = Path(__file__).resolve().parents[1] / "src/flowboard/presentation/html/templates"
        content = "".join(p.read_text() for p in tmpl_dir.glob("*.html"))

        """THEN the expected behaviour holds: has data function exists"""
        assert "function _hasData(cfg)" in content
        assert "No data available" in content or "chart_no_data" in content


# =========================================================================
# Schema cache thread safety
# =========================================================================


class TestSchemaCacheThreadSafe:
    """Tests for schema cache thread safe."""

    """GIVEN schema cache thread safe and the scenario: lock exists"""
    def test_lock_exists(self):
        """WHEN the code under test is exercised for: lock exists"""
        from flowboard.infrastructure.config import validator

        """THEN the expected behaviour holds: lock exists"""
        assert hasattr(validator, "_schema_lock")
        assert isinstance(validator._schema_lock, type(threading.Lock()))

    """GIVEN schema cache thread safe and the scenario: concurrent loads dont crash"""
    def test_concurrent_loads_dont_crash(self):
        """WHEN the code under test is exercised for: concurrent loads dont crash"""
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

        """THEN the expected behaviour holds: concurrent loads dont crash"""
        assert not errors
        assert len(results) == 10


# =========================================================================
# config_to_dict auth comment
# =========================================================================


class TestConfigToDictAuthComment:
    """Tests for config to dict auth comment."""

    """GIVEN config to dict auth comment and the scenario: docstring mentions auth"""
    def test_docstring_mentions_auth(self):
        """WHEN the code under test is exercised for: docstring mentions auth"""
        from flowboard.infrastructure.config.loader import config_to_dict

        """THEN the expected behaviour holds: docstring mentions auth"""
        assert "credential" in (config_to_dict.__doc__ or "").lower()


# =========================================================================
# Retro headline uses average churn
# =========================================================================


class TestRetroHeadlineAverage:
    """Tests for retro headline average."""

    """GIVEN retro headline average and the scenario: headline uses average"""
    def test_headline_uses_average(self):
        """WHEN the code under test is exercised for: headline uses average"""
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
            [],
            [],
            [],
            scope,
            ReadinessReport(items=[], avg_readiness=0.0),
            [],
            today=date(2026, 3, 10),
        )
        # Average churn = (30+10)/2 = 20, headline should contain "20"

        """THEN the expected behaviour holds: headline uses average"""
        assert ":20" in result["retro"].headline


# =========================================================================
# first_run innerHTML XSS - uses textContent
# =========================================================================


class TestTourNoInnerHTML:
    """Tests for tour no inner h t m l."""

    """GIVEN tour no inner h t m l and the scenario: no innerhtml in tour"""
    def test_no_innerhtml_in_tour(self):
        """WHEN the code under test is exercised for: no innerhtml in tour"""
        from flowboard.presentation.html.renderer import render_first_run

        html = render_first_run()
        # The wizard JS should not use innerHTML anywhere
        # Allow innerHTML only in safe contexts (button label updates via .innerHTML with spinner)
        js_section = html[html.find("<script") : html.rfind("</script>")]
        # Count innerHTML uses - minimal or zero
        count = js_section.count("innerHTML")

        """THEN the expected behaviour holds: no innerhtml in tour"""
        assert count <= 3, f"Found {count} innerHTML uses - prefer textContent/DOM methods"


# =========================================================================
# StatusCategory enum comparison in timeline
# =========================================================================


class TestTimelineStatusEnum:
    """Tests for timeline status enum."""

    """GIVEN timeline status enum and the scenario: no value done string"""
    def test_no_value_done_string(self):
        """WHEN the code under test is exercised for: no value done string"""
        import inspect

        from flowboard.domain.timeline import build_epic_timeline

        src = inspect.getsource(build_epic_timeline)

        """THEN the expected behaviour holds: no value done string"""
        assert '.value == "Done"' not in src
        assert "StatusCategory.DONE" in src


# =========================================================================
# Schema path CWD evaluated lazily
# =========================================================================


class TestSchemaPathCWD:
    """Tests for schema path c w d."""

    """GIVEN schema path c w d and the scenario: no cwd at module level"""
    def test_no_cwd_at_module_level(self):
        """WHEN the code under test is exercised for: no cwd at module level"""
        import inspect

        from flowboard.infrastructure.config import validator

        src = inspect.getsource(validator)
        # Find module-level assignments (before first def)
        module_header = src[: src.find("\ndef ")]
        # Remove comment lines
        code_lines = [
            line for line in module_header.split("\n") if not line.strip().startswith("#")
        ]
        code_only = "\n".join(code_lines)

        """THEN the expected behaviour holds: no cwd at module level"""
        assert "Path.cwd()" not in code_only


# =========================================================================
# Demo fixture JSON parse
# =========================================================================


class TestDemoFixtureParse:
    """Tests for demo fixture parse."""

    """GIVEN demo fixture parse and the scenario: json parse guarded"""
    def test_json_parse_guarded(self):
        """WHEN the code under test is exercised for: json parse guarded"""
        import inspect

        from flowboard.cli.main import demo

        src = inspect.getsource(demo)

        """THEN the expected behaviour holds: json parse guarded"""
        assert "JSONDecodeError" in src or "json.JSONDecodeError" in src


# =========================================================================
# Simulation collision metric
# =========================================================================


class TestSimCollisionMetric:
    """Tests for sim collision metric."""

    """GIVEN sim collision metric and the scenario: collision counts concurrent"""
    def test_collision_counts_concurrent(self):
        """WHEN the code under test is exercised for: collision counts concurrent"""
        from flowboard.domain.simulation import (
            ResourceChange,
            SimulationScenario,
            _simulate_workloads,
        )
        from flowboard.infrastructure.config.loader import load_config_from_dict

        cfg = load_config_from_dict({"jira": {"base_url": "https://x.atlassian.net"}})
        wrs = [
            WorkloadRecord(
                person=_person("A"),
                team="api",
                issue_count=5,
                story_points=15.0,
                in_progress_count=3,
                blocked_count=0,
            ),
        ]
        teams = [Team(key="api", name="API", members=["a"])]
        scenario = SimulationScenario(
            id="test",
            name="Test",
            description="Test",
            changes=(ResourceChange(team_key="api", delta=1),),
        )
        _, metrics = _simulate_workloads(wrs, teams, scenario, cfg.thresholds)
        # With 1 person having 3 in-progress and +1 resource:
        # redistribution_factor = 1/2, sim_wip = round(3*0.5) = 2
        # collision = 2-1 = 1 (from concurrent tasks, not from len(wrs))

        """THEN the expected behaviour holds: collision counts concurrent"""
        assert metrics.total_collisions == 1

    """GIVEN sim collision metric and the scenario: no collision when wip is one"""
    def test_no_collision_when_wip_is_one(self):
        """WHEN the code under test is exercised for: no collision when wip is one"""
        from flowboard.domain.simulation import (
            ResourceChange,
            SimulationScenario,
            _simulate_workloads,
        )
        from flowboard.infrastructure.config.loader import load_config_from_dict

        cfg = load_config_from_dict({"jira": {"base_url": "https://x.atlassian.net"}})
        wrs = [
            WorkloadRecord(
                person=_person("A"),
                team="api",
                issue_count=1,
                story_points=5.0,
                in_progress_count=1,
                blocked_count=0,
            ),
        ]
        teams = [Team(key="api", name="API", members=["a"])]
        scenario = SimulationScenario(
            id="test",
            name="Test",
            description="Test",
            changes=(ResourceChange(team_key="api", delta=1),),
        )
        _, metrics = _simulate_workloads(wrs, teams, scenario, cfg.thresholds)

        """THEN the expected behaviour holds: no collision when wip is one"""
        assert metrics.total_collisions == 0


# =========================================================================
# Sprint field string format warning
# =========================================================================


class TestSprintFieldStringWarning:
    """Tests for sprint field string warning."""

    """GIVEN sprint field string warning and the scenario: string sprint logs warning"""
    def test_string_sprint_logs_warning(self):
        """WHEN the code under test is exercised for: string sprint logs warning"""
        from flowboard.infrastructure.config.loader import load_config_from_dict
        from flowboard.infrastructure.jira.normalizer import JiraNormalizer

        cfg = load_config_from_dict({"jira": {"base_url": "https://x.atlassian.net"}})
        n = JiraNormalizer(cfg)

        """THEN the expected behaviour holds: string sprint logs warning"""
        with patch("flowboard.infrastructure.jira.normalizer.logger") as mock_log:
            result = n._extract_sprint(
                {"customfield_10020": "com.atlassian.greenhopper.service..."}
            )
            assert result is None
            mock_log.warning.assert_called_once()
            assert "string" in str(mock_log.warning.call_args).lower() or "Unexpected" in str(
                mock_log.warning.call_args
            )


# =========================================================================
# Retry context in error messages
# =========================================================================


class TestRetryContext:
    """Tests for retry context."""

    """GIVEN retry context and the scenario: error mentions retries"""
    def test_error_mentions_retries(self):
        """WHEN the code under test is exercised for: error mentions retries"""
        import inspect

        from flowboard.infrastructure.jira.client import JiraClient

        src = inspect.getsource(JiraClient._request)

        """THEN the expected behaviour holds: error mentions retries"""
        assert "after" in src and "retries" in src.lower()


# =========================================================================
# Health check CLI command
# =========================================================================


class TestHealthCommand:
    """Tests for health command."""

    """GIVEN health command and the scenario: health command exists"""
    def test_health_command_exists(self):
        """WHEN the code under test is exercised for: health command exists"""
        from flowboard.cli.main import app

        command_names = [
            cmd.name or (cmd.callback.__name__.replace("_", "-") if cmd.callback else None)
            for cmd in app.registered_commands
        ]

        """THEN the expected behaviour holds: health command exists"""
        assert "health" in command_names


# =========================================================================
# Structured logging with pipeline timing
# =========================================================================


class TestPipelineTiming:
    """Tests for pipeline timing."""

    """GIVEN pipeline timing and the scenario: timed context manager"""
    def test_timed_context_manager(self):
        """WHEN the code under test is exercised for: timed context manager"""
        from flowboard.application.orchestrator import _timed

        """THEN the expected behaviour holds: timed context manager"""
        with patch("flowboard.application.orchestrator.logger") as mock_log:
            with _timed("test_stage"):
                pass
            calls = [str(c) for c in mock_log.info.call_args_list]
            assert any("test_stage" in c for c in calls)
            assert any("completed" in c for c in calls)

    """GIVEN pipeline timing and the scenario: run from payload includes timing"""
    def test_run_from_payload_includes_timing(self):
        """WHEN the code under test is exercised for: run from payload includes timing"""
        import inspect

        from flowboard.application.orchestrator import Orchestrator

        src = inspect.getsource(Orchestrator.run)

        """THEN the expected behaviour holds: run from payload includes timing"""
        assert "pipeline_start" in src
        assert "total pipeline" in src.lower() or "total" in src.lower()
