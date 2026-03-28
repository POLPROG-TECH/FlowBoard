"""Data structures for the capacity simulation engine."""

from __future__ import annotations

from dataclasses import dataclass, field

from flowboard.domain.timeline import TimelineData
from flowboard.shared.types import RiskSeverity

# ---------------------------------------------------------------------------
# Simulation data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ResourceChange:
    """A single resource addition/removal for a team/layer."""

    team_key: str
    delta: int  # positive = add, negative = remove


@dataclass(frozen=True, slots=True)
class SimulationScenario:
    """A named what-if scenario with one or more resource changes."""

    id: str
    name: str
    description: str
    changes: tuple[ResourceChange, ...]
    is_preset: bool = False


@dataclass(frozen=True, slots=True)
class SimulationMetrics:
    """Aggregate metrics for one state (baseline or simulated)."""

    total_collisions: int = 0
    overloaded_people: int = 0
    wip_violations: int = 0
    timeline_overlaps: int = 0
    avg_load_per_person: float = 0.0
    max_load_person: float = 0.0
    avg_utilization_pct: float = 0.0
    peak_concurrent_tasks: int = 0
    blocked_work_items: int = 0
    at_risk_teams: int = 0
    total_story_points: float = 0.0
    team_balance_score: float = 0.0  # 0-100, higher = more balanced


@dataclass(frozen=True, slots=True)
class MetricDelta:
    """Change between baseline and simulated metrics."""

    collisions_reduced: int = 0
    overload_reduced: int = 0
    wip_violations_reduced: int = 0
    timeline_overlaps_reduced: int = 0
    avg_load_reduction_pct: float = 0.0
    peak_load_reduction_pct: float = 0.0
    utilization_improvement_pct: float = 0.0
    risk_teams_reduced: int = 0
    balance_improvement: float = 0.0


@dataclass(frozen=True, slots=True)
class Recommendation:
    """An actionable planning suggestion."""

    priority: int  # 1 = highest
    severity: RiskSeverity
    title: str
    description: str
    team_key: str = ""
    impact_score: float = 0.0  # 0-100


@dataclass(slots=True)
class ScenarioResult:
    """Complete result of running one simulation scenario."""

    scenario: SimulationScenario
    baseline: SimulationMetrics = field(default_factory=SimulationMetrics)
    simulated: SimulationMetrics = field(default_factory=SimulationMetrics)
    delta: MetricDelta = field(default_factory=MetricDelta)
    recommendations: list[Recommendation] = field(default_factory=list)
    simulated_workloads: list[dict[str, object]] = field(default_factory=list)
    timeline_before: TimelineData | None = None
    timeline_after: TimelineData | None = None
    impact_score: float = 0.0  # overall scenario impact 0-100


@dataclass(slots=True)
class TeamImpact:
    """Per-team impact analysis for the 'where to add' recommendation."""

    team_key: str
    team_name: str
    current_load: float
    current_members: int
    load_per_person: float
    collision_contribution: int
    overloaded_members: int
    impact_score: float  # higher = more benefit from adding here
    recommendation: str = ""


@dataclass(slots=True)
class SimulationSuite:
    """Complete simulation output embedded in the dashboard."""

    baseline: SimulationMetrics
    scenarios: list[ScenarioResult] = field(default_factory=list)
    team_impacts: list[TeamImpact] = field(default_factory=list)
    best_hire_team: str = ""
    best_hire_reason: str = ""
    global_recommendations: list[Recommendation] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
