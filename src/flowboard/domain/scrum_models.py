"""Data structures for Scrum-oriented analytics."""

from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class GoalItem:
    """A sprint-goal-critical issue."""

    key: str
    summary: str
    status: str
    assignee: str
    story_points: float
    is_blocked: bool
    is_at_risk: bool


@dataclass(slots=True)
class SprintGoalReport:
    """Health assessment of a sprint's goal."""

    sprint_name: str
    sprint_state: str
    total_goal_items: int = 0
    completed: int = 0
    in_progress: int = 0
    blocked: int = 0
    not_started: int = 0
    completion_pct: float = 0.0
    health: str = "on_track"  # on_track | at_risk | off_track
    goal_items: list[GoalItem] = field(default_factory=list)


@dataclass(slots=True)
class ScopeChangeReport:
    """Tracks scope churn during a sprint."""

    sprint_name: str
    original_count: int = 0
    added_count: int = 0
    removed_estimate: int = 0
    sp_original: float = 0.0
    sp_added: float = 0.0
    churn_pct: float = 0.0
    stability: str = "stable"  # stable | moderate | unstable
    added_items: list[GoalItem] = field(default_factory=list)


@dataclass(slots=True)
class BlockerItem:
    """A blocked issue with aging information."""

    key: str
    summary: str
    assignee: str
    team: str
    blocked_days: int
    severity: str  # warning | critical | escalate
    sprint_name: str


@dataclass(slots=True)
class BacklogQualityReport:
    """Backlog hygiene assessment for Product Owners."""

    total_backlog: int = 0
    no_estimate: int = 0
    no_assignee: int = 0
    no_epic: int = 0
    stale_count: int = 0
    no_priority: int = 0
    quality_score: float = 0.0
    grade: str = "C"


@dataclass(slots=True)
class ReadinessItem:
    """Sprint-readiness assessment for a single backlog item."""

    key: str
    summary: str
    has_estimate: bool
    has_assignee: bool
    has_epic: bool
    has_priority: bool
    is_small_enough: bool
    readiness_pct: float
    missing: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ReadinessReport:
    """Overall sprint readiness assessment."""

    total_candidates: int = 0
    ready_count: int = 0
    partial_count: int = 0
    not_ready_count: int = 0
    avg_readiness: float = 0.0
    items: list[ReadinessItem] = field(default_factory=list)


@dataclass(slots=True)
class DeliveryRiskItem:
    """Delivery risk forecast for an epic or initiative."""

    key: str
    title: str
    risk_score: float
    factors: list[str] = field(default_factory=list)
    level: str = "low"  # low | medium | high | critical


@dataclass(slots=True)
class DependencyHeatCell:
    """Single cell in the dependency heatmap."""

    from_team: str
    to_team: str
    count: int = 0
    blocked_count: int = 0


@dataclass(slots=True)
class CapacityRow:
    """Capacity vs commitment for one team."""

    team: str
    capacity_sp: float = 0.0
    committed_sp: float = 0.0
    in_progress_sp: float = 0.0
    done_sp: float = 0.0
    blocked_sp: float = 0.0
    utilization_pct: float = 0.0
    status: str = "balanced"  # balanced | over | under


@dataclass(slots=True)
class CeremonySummary:
    """Pre-computed data for a Scrum ceremony."""

    ceremony: str
    headline: str = ""
    metrics: dict[str, object] = field(default_factory=dict)
    items: list[GoalItem] = field(default_factory=list)


@dataclass(slots=True)
class EpicProgress:
    """Value-delivery progress for one epic/initiative."""

    key: str
    title: str
    team: str
    total_issues: int = 0
    done_issues: int = 0
    in_progress: int = 0
    blocked: int = 0
    total_sp: float = 0.0
    done_sp: float = 0.0
    completion_pct: float = 0.0
    status: str = "on_track"  # on_track | slipping | at_risk | done


@dataclass(slots=True)
class ProductProgressReport:
    """Product-level progress for Product Owners."""

    epics: list[EpicProgress] = field(default_factory=list)
    overall_completion: float = 0.0
    on_track: int = 0
    slipping: int = 0
    at_risk: int = 0
    done: int = 0


@dataclass(slots=True)
class ScrumInsights:
    """Container for all Scrum-oriented analytics."""

    sprint_goals: list[SprintGoalReport] = field(default_factory=list)
    scope_changes: list[ScopeChangeReport] = field(default_factory=list)
    blockers: list[BlockerItem] = field(default_factory=list)
    backlog_quality: BacklogQualityReport = field(default_factory=BacklogQualityReport)
    readiness: ReadinessReport = field(default_factory=ReadinessReport)
    delivery_risks: list[DeliveryRiskItem] = field(default_factory=list)
    dependency_heat: list[DependencyHeatCell] = field(default_factory=list)
    dependency_teams: list[str] = field(default_factory=list)
    capacity: list[CapacityRow] = field(default_factory=list)
    ceremonies: dict[str, CeremonySummary] = field(default_factory=dict)
    product_progress: ProductProgressReport = field(
        default_factory=ProductProgressReport,
    )
