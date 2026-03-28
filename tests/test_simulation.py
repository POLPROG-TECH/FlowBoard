"""Tests for the capacity simulation / what-if planning engine."""

from __future__ import annotations

from datetime import UTC, date, datetime

from flowboard.domain.models import (
    BoardSnapshot,
    CapacityRecord,
    Issue,
    OverlapConflict,
    Person,
    Team,
    WorkloadRecord,
)
from flowboard.domain.simulation import (
    ResourceChange,
    SimulationMetrics,
    SimulationScenario,
    SimulationSuite,
    TeamImpact,
    build_preset_scenarios,
    compute_baseline_metrics,
    compute_recommendations,
    compute_team_impacts,
    run_scenario,
    run_simulation_suite,
)
from flowboard.infrastructure.config.loader import Thresholds, load_config_from_dict
from flowboard.presentation.html.components import simulation_view
from flowboard.shared.types import (
    IssueType,
    Priority,
    RiskSeverity,
    StatusCategory,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _person(name: str, team: str = "alpha") -> Person:
    return Person(account_id=name.lower(), display_name=name, team=team)


def _issue(
    key: str,
    assignee: Person,
    sp: float = 5.0,
    status: StatusCategory = StatusCategory.IN_PROGRESS,
    created: datetime | None = None,
    due: date | None = None,
) -> Issue:
    return Issue(
        key=key,
        summary=f"Issue {key}",
        issue_type=IssueType.STORY,
        status_category=status,
        assignee=assignee,
        story_points=sp,
        priority=Priority.MEDIUM,
        created=created or datetime(2026, 3, 1, tzinfo=UTC),
        due_date=due or date(2026, 3, 15),
    )


def _thresholds(**kwargs) -> Thresholds:
    defaults = {
        "overload_points": 15.0,
        "overload_issues": 5,
        "wip_limit": 3,
        "aging_days": 14,
        "capacity_per_person": 13.0,
    }
    defaults.update(kwargs)
    return Thresholds(**defaults)


def _snapshot(
    issues: list[Issue] | None = None,
    teams: list[Team] | None = None,
    workloads: list[WorkloadRecord] | None = None,
    conflicts: list[OverlapConflict] | None = None,
    capacity: list[CapacityRecord] | None = None,
) -> BoardSnapshot:
    return BoardSnapshot(
        issues=issues or [],
        teams=teams or [],
        workload_records=workloads or [],
        overlap_conflicts=conflicts or [],
        capacity_records=capacity or [],
    )


# ---------------------------------------------------------------------------
# Preset scenario generation
# ---------------------------------------------------------------------------

class TestPresetScenarios:
    def test_creates_per_team_presets(self) -> None:
        teams = [
            Team(key="ui", name="UI"),
            Team(key="api", name="API"),
            Team(key="db", name="DB"),
        ]
        presets = build_preset_scenarios(teams)
        names = [p.name for p in presets]
        assert "+1 UI" in names
        assert "+1 API" in names
        assert "+1 DB" in names

    def test_includes_balanced_expansion(self) -> None:
        teams = [Team(key="ui", name="UI"), Team(key="api", name="API")]
        presets = build_preset_scenarios(teams)
        balanced = [p for p in presets if p.id == "balanced"]
        assert len(balanced) == 1
        assert len(balanced[0].changes) == 2

    def test_all_presets_are_marked(self) -> None:
        teams = [Team(key="x", name="X")]
        presets = build_preset_scenarios(teams)
        assert all(p.is_preset for p in presets)

    def test_empty_teams_uses_defaults(self) -> None:
        presets = build_preset_scenarios([])
        assert len(presets) >= 3
        keys = {rc.team_key for p in presets for rc in p.changes}
        assert "ui" in keys
        assert "api" in keys
        assert "db" in keys

    def test_focus_top2_preset(self) -> None:
        teams = [Team(key="a", name="A"), Team(key="b", name="B"), Team(key="c", name="C")]
        presets = build_preset_scenarios(teams)
        focus = [p for p in presets if p.id == "focus-top2"]
        assert len(focus) == 1
        assert all(rc.delta == 2 for rc in focus[0].changes)


# ---------------------------------------------------------------------------
# Baseline metrics computation
# ---------------------------------------------------------------------------

class TestBaselineMetrics:
    def test_basic_metrics(self) -> None:
        alice = _person("Alice", "ui")
        bob = _person("Bob", "api")
        wrs = [
            WorkloadRecord(person=alice, team="ui", issue_count=4, story_points=20.0, in_progress_count=2),
            WorkloadRecord(person=bob, team="api", issue_count=3, story_points=10.0, in_progress_count=1),
        ]
        snap = _snapshot(workloads=wrs)
        th = _thresholds(overload_points=15.0)
        m = compute_baseline_metrics(snap, th)

        assert m.overloaded_people == 1  # Alice > 15
        assert m.avg_load_per_person == 15.0
        assert m.max_load_person == 20.0
        assert m.total_story_points == 30.0

    def test_wip_violations(self) -> None:
        alice = _person("Alice")
        wrs = [WorkloadRecord(person=alice, team="a", in_progress_count=5)]
        snap = _snapshot(workloads=wrs)
        th = _thresholds(wip_limit=3)
        m = compute_baseline_metrics(snap, th)
        assert m.wip_violations == 1

    def test_empty_workloads(self) -> None:
        snap = _snapshot()
        th = _thresholds()
        m = compute_baseline_metrics(snap, th)
        assert m.total_collisions == 0
        assert m.overloaded_people == 0
        assert m.avg_load_per_person == 0.0

    def test_balance_score_perfect(self) -> None:
        alice = _person("Alice")
        bob = _person("Bob")
        wrs = [
            WorkloadRecord(person=alice, story_points=10.0),
            WorkloadRecord(person=bob, story_points=10.0),
        ]
        snap = _snapshot(workloads=wrs)
        th = _thresholds()
        m = compute_baseline_metrics(snap, th)
        assert m.team_balance_score == 100.0

    def test_balance_score_imbalanced(self) -> None:
        alice = _person("Alice")
        bob = _person("Bob")
        wrs = [
            WorkloadRecord(person=alice, story_points=40.0),
            WorkloadRecord(person=bob, story_points=5.0),
        ]
        snap = _snapshot(workloads=wrs)
        th = _thresholds()
        m = compute_baseline_metrics(snap, th)
        assert m.team_balance_score < 50.0

    def test_collision_count(self) -> None:
        conflicts = [
            OverlapConflict(category="resource_contention", severity=RiskSeverity.HIGH, description="x"),
            OverlapConflict(category="timeline_overlap", severity=RiskSeverity.MEDIUM, description="y"),
        ]
        snap = _snapshot(conflicts=conflicts)
        th = _thresholds()
        m = compute_baseline_metrics(snap, th)
        assert m.total_collisions == 2
        assert m.timeline_overlaps == 2


# ---------------------------------------------------------------------------
# Team impact analysis
# ---------------------------------------------------------------------------

class TestTeamImpacts:
    def test_highest_impact_sorted_first(self) -> None:
        alice = _person("Alice", "ui")
        bob = _person("Bob", "api")
        wrs = [
            WorkloadRecord(person=alice, team="ui", story_points=30.0, in_progress_count=6),
            WorkloadRecord(person=bob, team="api", story_points=5.0, in_progress_count=1),
        ]
        teams = [Team(key="ui", name="UI"), Team(key="api", name="API")]
        snap = _snapshot(workloads=wrs, teams=teams)
        th = _thresholds(overload_points=15.0)
        impacts = compute_team_impacts(snap, th)
        assert impacts[0].team_key == "ui"
        assert impacts[0].impact_score > impacts[1].impact_score

    def test_overloaded_members_counted(self) -> None:
        alice = _person("Alice", "ui")
        bob = _person("Bob", "ui")
        wrs = [
            WorkloadRecord(person=alice, team="ui", story_points=25.0),
            WorkloadRecord(person=bob, team="ui", story_points=20.0),
        ]
        teams = [Team(key="ui", name="UI")]
        snap = _snapshot(workloads=wrs, teams=teams)
        th = _thresholds(overload_points=15.0)
        impacts = compute_team_impacts(snap, th)
        assert impacts[0].overloaded_members == 2

    def test_recommendation_for_top_team(self) -> None:
        alice = _person("Alice", "api")
        wrs = [WorkloadRecord(person=alice, team="api", story_points=25.0, in_progress_count=4)]
        teams = [Team(key="api", name="API")]
        snap = _snapshot(workloads=wrs, teams=teams)
        th = _thresholds(overload_points=15.0)
        impacts = compute_team_impacts(snap, th)
        assert impacts[0].recommendation  # should have a recommendation


# ---------------------------------------------------------------------------
# Scenario execution
# ---------------------------------------------------------------------------

class TestRunScenario:
    def test_scenario_reduces_overload(self) -> None:
        alice = _person("Alice", "ui")
        bob = _person("Bob", "ui")
        wrs = [
            WorkloadRecord(person=alice, team="ui", issue_count=6, story_points=25.0, in_progress_count=4),
            WorkloadRecord(person=bob, team="ui", issue_count=5, story_points=20.0, in_progress_count=3),
        ]
        issues = [
            _issue("T-1", alice, 10.0),
            _issue("T-2", alice, 8.0),
            _issue("T-3", alice, 7.0),
            _issue("T-4", bob, 10.0),
            _issue("T-5", bob, 10.0),
        ]
        teams = [Team(key="ui", name="UI")]
        snap = _snapshot(issues=issues, teams=teams, workloads=wrs)
        th = _thresholds(overload_points=15.0)
        baseline = compute_baseline_metrics(snap, th)

        scenario = SimulationScenario(
            id="plus1-ui", name="+1 UI", description="Add 1 UI",
            changes=(ResourceChange(team_key="ui", delta=1),),
        )
        result = run_scenario(snap, scenario, baseline, th)

        # After adding a person, load per person should decrease
        assert result.simulated.avg_load_per_person < baseline.avg_load_per_person
        assert result.simulated.overloaded_people <= baseline.overloaded_people

    def test_scenario_has_timeline(self) -> None:
        alice = _person("Alice", "api")
        issues = [_issue("T-1", alice, 8.0)]
        wrs = [WorkloadRecord(person=alice, team="api", issue_count=1, story_points=8.0)]
        teams = [Team(key="api", name="API")]
        snap = _snapshot(issues=issues, teams=teams, workloads=wrs)
        th = _thresholds()
        baseline = compute_baseline_metrics(snap, th)

        scenario = SimulationScenario(
            id="plus1-api", name="+1 API", description="test",
            changes=(ResourceChange(team_key="api", delta=1),),
        )
        result = run_scenario(snap, scenario, baseline, th)
        assert result.timeline_before is not None
        assert result.timeline_after is not None

    def test_impact_score_non_negative(self) -> None:
        snap = _snapshot(teams=[Team(key="x", name="X")])
        th = _thresholds()
        baseline = compute_baseline_metrics(snap, th)
        scenario = SimulationScenario(
            id="test", name="Test", description="test",
            changes=(ResourceChange(team_key="x", delta=1),),
        )
        result = run_scenario(snap, scenario, baseline, th)
        assert result.impact_score >= 0.0


# ---------------------------------------------------------------------------
# Full simulation suite
# ---------------------------------------------------------------------------

class TestSimulationSuite:
    def test_suite_runs_with_teams(self) -> None:
        alice = _person("Alice", "ui")
        bob = _person("Bob", "api")
        wrs = [
            WorkloadRecord(person=alice, team="ui", issue_count=5, story_points=20.0, in_progress_count=3),
            WorkloadRecord(person=bob, team="api", issue_count=3, story_points=10.0, in_progress_count=1),
        ]
        issues = [_issue("T-1", alice, 10.0), _issue("T-2", alice, 10.0), _issue("T-3", bob, 10.0)]
        teams = [Team(key="ui", name="UI"), Team(key="api", name="API")]
        snap = _snapshot(issues=issues, teams=teams, workloads=wrs)
        th = _thresholds(overload_points=15.0)

        suite = run_simulation_suite(snap, th)
        assert isinstance(suite, SimulationSuite)
        assert suite.baseline.total_story_points > 0
        assert len(suite.scenarios) > 0
        assert len(suite.team_impacts) > 0
        assert suite.best_hire_team in ("ui", "api")
        assert suite.assumptions  # should list assumptions

    def test_suite_sorted_by_impact(self) -> None:
        alice = _person("Alice", "ui")
        wrs = [WorkloadRecord(person=alice, team="ui", issue_count=5, story_points=25.0, in_progress_count=4)]
        issues = [_issue(f"T-{i}", alice, 5.0) for i in range(5)]
        teams = [Team(key="ui", name="UI"), Team(key="api", name="API")]
        snap = _snapshot(issues=issues, teams=teams, workloads=wrs)
        th = _thresholds(overload_points=15.0)

        suite = run_simulation_suite(snap, th)
        scores = [s.impact_score for s in suite.scenarios]
        assert scores == sorted(scores, reverse=True)

    def test_suite_empty_teams(self) -> None:
        snap = _snapshot()
        th = _thresholds()
        suite = run_simulation_suite(snap, th)
        assert isinstance(suite, SimulationSuite)
        # Should still have default presets
        assert len(suite.scenarios) >= 3


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

class TestRecommendations:
    def test_best_hire_recommendation(self) -> None:
        impacts = [
            TeamImpact(
                team_key="ui", team_name="UI", current_load=30.0,
                current_members=2, load_per_person=15.0,
                collision_contribution=3, overloaded_members=1,
                impact_score=65.0, recommendation="Add here",
            ),
        ]
        snap = _snapshot()
        baseline = SimulationMetrics(total_collisions=5, overloaded_people=2)
        th = _thresholds()
        recs = compute_recommendations(snap, baseline, impacts, th)
        assert len(recs) > 0
        assert any("UI" in r.title for r in recs)

    def test_overload_warning(self) -> None:
        alice = _person("Alice")
        wrs = [WorkloadRecord(person=alice, story_points=40.0)]
        snap = _snapshot(workloads=wrs)
        baseline = SimulationMetrics()
        th = _thresholds(overload_points=15.0)
        recs = compute_recommendations(snap, baseline, [], th)
        assert any("Alice" in r.title for r in recs)

    def test_blocked_cluster_warning(self) -> None:
        alice = _person("Alice")
        from flowboard.domain.models import IssueLink
        from flowboard.shared.types import LinkType
        blocked_issues = [
            Issue(
                key=f"B-{i}", summary=f"Blocked {i}",
                story_points=3.0, assignee=alice,
                links=[IssueLink(target_key=f"X-{i}", link_type=LinkType.IS_BLOCKED_BY)],
                created=datetime(2026, 3, 1, tzinfo=UTC),
            )
            for i in range(5)
        ]
        snap = _snapshot(issues=blocked_issues)
        recs = compute_recommendations(snap, SimulationMetrics(), [], _thresholds())
        assert any("blocked" in r.title.lower() for r in recs)


# ---------------------------------------------------------------------------
# Component rendering
# ---------------------------------------------------------------------------

class TestSimulationViewComponent:
    def test_renders_none_gracefully(self) -> None:
        html = simulation_view(None)
        assert "empty-state" in html

    def test_renders_suite(self) -> None:
        alice = _person("Alice", "ui")
        bob = _person("Bob", "api")
        wrs = [
            WorkloadRecord(person=alice, team="ui", issue_count=5, story_points=20.0, in_progress_count=3),
            WorkloadRecord(person=bob, team="api", issue_count=3, story_points=10.0, in_progress_count=1),
        ]
        issues = [_issue("T-1", alice, 10.0), _issue("T-2", bob, 10.0)]
        teams = [Team(key="ui", name="UI"), Team(key="api", name="API")]
        snap = _snapshot(issues=issues, teams=teams, workloads=wrs)
        th = _thresholds(overload_points=15.0)
        suite = run_simulation_suite(snap, th)

        html = simulation_view(suite)
        assert "sim-disclaimer" in html
        assert "sim-view-btn" in html
        assert "sim-chip" in html
        assert "sim-comparison-table" in html
        assert "+1 UI" in html or "+1 API" in html

    def test_best_hire_rendered(self) -> None:
        alice = _person("Alice", "ui")
        wrs = [WorkloadRecord(person=alice, team="ui", issue_count=5, story_points=25.0, in_progress_count=4)]
        issues = [_issue(f"T-{i}", alice, 5.0) for i in range(5)]
        teams = [Team(key="ui", name="UI")]
        snap = _snapshot(issues=issues, teams=teams, workloads=wrs)
        th = _thresholds(overload_points=10.0)
        suite = run_simulation_suite(snap, th)

        html = simulation_view(suite)
        assert "sim-best-hire" in html
        assert "UI" in html

    def test_timeline_panels_rendered(self) -> None:
        alice = _person("Alice", "ui")
        issues = [
            _issue("T-1", alice, 5.0, due=date(2026, 3, 20)),
            _issue("T-2", alice, 5.0, due=date(2026, 3, 25)),
        ]
        wrs = [WorkloadRecord(person=alice, team="ui", issue_count=2, story_points=10.0, in_progress_count=2)]
        teams = [Team(key="ui", name="UI")]
        snap = _snapshot(issues=issues, teams=teams, workloads=wrs)
        suite = run_simulation_suite(snap, _thresholds())

        html = simulation_view(suite)
        assert "simPanel-timeline" in html
        assert "sim-mini-tl" in html


# ---------------------------------------------------------------------------
# Integration: simulation in board snapshot via analytics
# ---------------------------------------------------------------------------

class TestSimulationIntegration:
    def test_snapshot_includes_simulation_when_enabled(self) -> None:
        from flowboard.domain.analytics import build_board_snapshot

        alice = _person("Alice", "alpha")
        bob = _person("Bob", "beta")
        issues = [
            _issue("T-1", alice, 10.0),
            _issue("T-2", bob, 8.0),
        ]
        teams = [Team(key="alpha", name="Alpha"), Team(key="beta", name="Beta")]
        config = load_config_from_dict({
            "jira": {"base_url": "https://test.atlassian.net"},
            "teams": [
                {"key": "alpha", "name": "Alpha", "members": ["alice"]},
                {"key": "beta", "name": "Beta", "members": ["bob"]},
            ],
            "simulation": {"enabled": True},
        })
        snap = build_board_snapshot(
            issues=issues, sprints=[], teams=teams,
            roadmap_items=[], dependencies=[], people=[alice, bob],
            config=config,
        )
        assert snap.simulation is not None
        assert isinstance(snap.simulation, SimulationSuite)
        assert len(snap.simulation.scenarios) > 0

    def test_snapshot_no_simulation_when_disabled(self) -> None:
        from flowboard.domain.analytics import build_board_snapshot

        config = load_config_from_dict({
            "jira": {"base_url": "https://test.atlassian.net"},
            "simulation": {"enabled": False},
        })
        snap = build_board_snapshot(
            issues=[], sprints=[], teams=[],
            roadmap_items=[], dependencies=[], people=[],
            config=config,
        )
        assert snap.simulation is None


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class TestSimulationConfig:
    def test_default_enabled(self) -> None:
        cfg = load_config_from_dict({"jira": {"base_url": "https://x.atlassian.net"}})
        assert cfg.simulation.enabled is True

    def test_explicit_disabled(self) -> None:
        cfg = load_config_from_dict({
            "jira": {"base_url": "https://x.atlassian.net"},
            "simulation": {"enabled": False},
        })
        assert cfg.simulation.enabled is False
