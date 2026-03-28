"""Capacity simulation / what-if planning engine.

Simulates how adding resources to teams/layers affects workload pressure,
collisions, timeline congestion, and delivery risk — without mutating
any real Jira data.  All computation is pure and deterministic.

Split into sub-modules for maintainability:
- simulation_models: dataclasses
- simulation_engine: internal computation functions

This module re-exports everything for backward compatibility.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from flowboard.domain.models import BoardSnapshot
from flowboard.domain.simulation_engine import (
    _compute_delta,
    _simulate_timeline,
    _simulate_workloads,
    compute_baseline_metrics,
    compute_recommendations,
    compute_team_impacts,
)
from flowboard.domain.simulation_models import (  # noqa: F401 - re-export
    MetricDelta,
    Recommendation,
    ResourceChange,
    ScenarioResult,
    SimulationMetrics,
    SimulationScenario,
    SimulationSuite,
    TeamImpact,
)

if TYPE_CHECKING:
    from flowboard.domain.models import Team
    from flowboard.infrastructure.config.loader import Thresholds


# ---------------------------------------------------------------------------
# Preset scenario builders
# ---------------------------------------------------------------------------


def build_preset_scenarios(teams: list[Team]) -> list[SimulationScenario]:
    """Create useful preset scenarios based on available teams."""
    team_keys = [t.key for t in teams] if teams else ["ui", "api", "db"]
    presets: list[SimulationScenario] = []

    for tk in team_keys:
        presets.append(
            SimulationScenario(
                id=f"plus1-{tk}",
                name=f"+1 {tk.upper()}",
                description=f"Add one resource to {tk.upper()} team",
                changes=(ResourceChange(team_key=tk, delta=1),),
                is_preset=True,
            )
        )

    if len(team_keys) >= 2:
        presets.append(
            SimulationScenario(
                id="balanced",
                name="Balanced Expansion",
                description="Add one resource to each team",
                changes=tuple(ResourceChange(team_key=tk, delta=1) for tk in team_keys),
                is_preset=True,
            )
        )

    if len(team_keys) >= 2:
        presets.append(
            SimulationScenario(
                id="focus-top2",
                name="Focus Top 2 Teams",
                description="Add 2 resources to the most loaded teams",
                changes=tuple(
                    ResourceChange(team_key=tk, delta=2 if i < 2 else 0)
                    for i, tk in enumerate(team_keys)
                    if i < 2
                ),
                is_preset=True,
            )
        )

    return presets


# ---------------------------------------------------------------------------
# Run full simulation
# ---------------------------------------------------------------------------


def run_scenario(
    snapshot: BoardSnapshot,
    scenario: SimulationScenario,
    baseline: SimulationMetrics,
    thresholds: Thresholds,
) -> ScenarioResult:
    """Run a single simulation scenario and compute results."""
    from flowboard.domain.timeline import build_assignee_timeline

    # Simulate workload redistribution
    sim_workloads, sim_metrics = _simulate_workloads(
        snapshot.workload_records,
        snapshot.teams,
        scenario,
        thresholds,
    )

    # Re-estimate collisions based on new workload
    # Use the actual overlap conflict count as basis, adjust proportionally
    orig_collisions = baseline.total_collisions
    orig_overloaded = baseline.overloaded_people
    new_overloaded = sim_metrics.overloaded_people

    # Collision reduction estimate: proportional to overload reduction
    if orig_overloaded > 0:
        collision_reduction_ratio = (orig_overloaded - new_overloaded) / orig_overloaded
    else:
        collision_reduction_ratio = 0.0
    estimated_collisions = max(0, round(orig_collisions * (1 - collision_reduction_ratio * 0.6)))

    # Build simulated timeline
    timeline_after = _simulate_timeline(snapshot, scenario)
    timeline_before = build_assignee_timeline(snapshot)

    # Count timeline overlaps in simulated state
    sim_tl_overlaps = sum(s.overlap_count for s in timeline_after.swimlanes)
    before_tl_overlaps = sum(s.overlap_count for s in timeline_before.swimlanes)

    sim_metrics = SimulationMetrics(
        total_collisions=estimated_collisions,
        overloaded_people=sim_metrics.overloaded_people,
        wip_violations=sim_metrics.wip_violations,
        timeline_overlaps=sim_tl_overlaps,
        avg_load_per_person=sim_metrics.avg_load_per_person,
        max_load_person=sim_metrics.max_load_person,
        avg_utilization_pct=sim_metrics.avg_utilization_pct,
        peak_concurrent_tasks=sim_metrics.peak_concurrent_tasks,
        blocked_work_items=sim_metrics.blocked_work_items,
        at_risk_teams=sim_metrics.at_risk_teams,
        total_story_points=sim_metrics.total_story_points,
        team_balance_score=sim_metrics.team_balance_score,
    )

    delta = _compute_delta(baseline, sim_metrics)

    # Impact score: weighted combination of improvements
    impact = 0.0
    impact += delta.overload_reduced * 15
    impact += delta.collisions_reduced * 10
    impact += delta.wip_violations_reduced * 8
    impact += delta.avg_load_reduction_pct * 0.5
    impact += delta.balance_improvement * 0.3
    impact += (before_tl_overlaps - sim_tl_overlaps) * 5
    impact = min(100.0, max(0.0, impact))

    return ScenarioResult(
        scenario=scenario,
        baseline=baseline,
        simulated=sim_metrics,
        delta=delta,
        simulated_workloads=sim_workloads,
        timeline_before=timeline_before,
        timeline_after=timeline_after,
        impact_score=round(impact, 1),
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def run_simulation_suite(
    snapshot: BoardSnapshot,
    thresholds: Thresholds,
    custom_scenarios: list[SimulationScenario] | None = None,
    *,
    t: Any = None,
) -> SimulationSuite:
    """Run the complete capacity simulation analysis.

    Computes baseline metrics, runs preset + custom scenarios,
    analyzes team impacts, and generates recommendations.
    """
    baseline = compute_baseline_metrics(snapshot, thresholds)

    # Build scenarios
    scenarios = build_preset_scenarios(snapshot.teams)
    if custom_scenarios:
        scenarios.extend(custom_scenarios)

    # Run each scenario
    results: list[ScenarioResult] = []
    for scenario in scenarios:
        result = run_scenario(snapshot, scenario, baseline, thresholds)
        results.append(result)

    # Sort by impact
    results.sort(key=lambda r: r.impact_score, reverse=True)

    # Team impact analysis
    team_impacts = compute_team_impacts(snapshot, thresholds)
    best_team = team_impacts[0] if team_impacts else None
    best_hire_team = best_team.team_key if best_team else ""
    best_hire_reason = best_team.recommendation if best_team else ""

    # Global recommendations
    global_recs = compute_recommendations(snapshot, baseline, team_impacts, thresholds, t=t)

    # Assumptions
    _t = t or (lambda key, **kw: kw.get("fallback", key))
    assumptions = [
        _t(
            "sim.assumption.full_capacity",
            fallback="New resources are assumed to have full capacity from day one",
        ),
        _t(
            "sim.assumption.proportional",
            fallback="Work is redistributed proportionally among all team members",
        ),
        _t(
            "sim.assumption.domain_specific",
            fallback="Resources are domain-specific (UI person works on UI tasks only)",
        ),
        _t(
            "sim.assumption.capacity_baseline",
            fallback="Capacity baseline: {capacity} SP per person per sprint",
        ).format(capacity=f"{thresholds.capacity_per_person:.0f}"),
        _t(
            "sim.assumption.overload_threshold",
            fallback="Overload threshold: {threshold} SP per person",
        ).format(threshold=f"{thresholds.overload_points:.0f}"),
        _t(
            "sim.assumption.wip_limit", fallback="WIP limit: {limit} concurrent items per person"
        ).format(limit=thresholds.wip_limit),
        _t(
            "sim.assumption.round_robin",
            fallback="Simulated timelines assume round-robin task redistribution",
        ),
        _t(
            "sim.assumption.collision_proportional",
            fallback="Collision estimates are proportional to workload reduction",
        ),
    ]

    return SimulationSuite(
        baseline=baseline,
        scenarios=results,
        team_impacts=team_impacts,
        best_hire_team=best_hire_team,
        best_hire_reason=best_hire_reason,
        global_recommendations=global_recs,
        assumptions=assumptions,
    )
