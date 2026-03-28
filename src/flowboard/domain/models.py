"""Core domain models for FlowBoard.

These dataclasses represent the normalized internal model — independent of
any specific Jira API response shape.  All analytics, presentation, and
export layers work with these objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from flowboard.shared.types import (
    IssueStatus,
    IssueType,
    LinkType,
    Priority,
    RiskCategory,
    RiskSeverity,
    SprintState,
    StatusCategory,
)

if TYPE_CHECKING:
    from flowboard.domain.kanban_models import KanbanInsights
    from flowboard.domain.pi import PISnapshot
    from flowboard.domain.scrum import ScrumInsights
    from flowboard.domain.simulation import SimulationSuite
    from flowboard.domain.waterfall_models import WaterfallInsights

# ---------------------------------------------------------------------------
# People & Teams
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Person:
    account_id: str
    display_name: str
    email: str = ""
    team: str = ""
    avatar_url: str = ""


@dataclass(frozen=True, slots=True)
class Team:
    key: str
    name: str
    members: tuple[str, ...] = ()  # account_ids


# ---------------------------------------------------------------------------
# Sprints
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Sprint:
    id: int
    name: str
    board_id: int = 0
    state: SprintState = SprintState.FUTURE
    start_date: date | None = None
    end_date: date | None = None
    goal: str = ""


# ---------------------------------------------------------------------------
# Issues (unified)
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Issue:
    key: str
    summary: str
    issue_type: IssueType = IssueType.OTHER
    status: IssueStatus = IssueStatus.OTHER
    status_category: StatusCategory = StatusCategory.TODO
    assignee: Person | None = None
    reporter: Person | None = None
    story_points: float = 0.0
    priority: Priority = Priority.UNSET
    epic_key: str = ""
    sprint: Sprint | None = None
    labels: list[str] = field(default_factory=list)
    components: list[str] = field(default_factory=list)
    fix_versions: list[str] = field(default_factory=list)
    created: datetime | None = None
    updated: datetime | None = None
    resolved: datetime | None = None
    due_date: date | None = None
    parent_key: str = ""
    project_key: str = ""
    links: list[IssueLink] = field(default_factory=list)

    @property
    def is_done(self) -> bool:
        return self.status_category == StatusCategory.DONE

    @property
    def is_in_progress(self) -> bool:
        return self.status_category == StatusCategory.IN_PROGRESS

    @property
    def is_blocked(self) -> bool:
        return any(
            lnk.link_type in (LinkType.IS_BLOCKED_BY, LinkType.DEPENDS_ON) and not lnk.is_resolved
            for lnk in self.links
        )

    @property
    def age_days(self) -> int | None:
        if self.created is None:
            return None
        end = self._resolve_end_date()
        delta = (end - self.created).days
        return max(0, delta)

    def _resolve_end_date(self) -> datetime:
        """Return the appropriate end date for age calculation."""
        if not self.resolved:
            return datetime.now(tz=UTC) if self.created.tzinfo else datetime.now()
        end = self.resolved
        if self.created.tzinfo and not end.tzinfo:
            return end.replace(tzinfo=UTC)
        if not self.created.tzinfo and end.tzinfo:
            return end.replace(tzinfo=None)
        return end


# ---------------------------------------------------------------------------
# Issue links / dependencies
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class IssueLink:
    target_key: str
    link_type: LinkType
    is_resolved: bool = False
    target_summary: str = ""
    target_status: str = ""


@dataclass(frozen=True, slots=True)
class Dependency:
    source_key: str
    target_key: str
    link_type: LinkType
    source_summary: str = ""
    target_summary: str = ""
    source_status: StatusCategory = StatusCategory.TODO
    target_status: StatusCategory = StatusCategory.TODO

    @property
    def is_blocking(self) -> bool:
        return (
            self.link_type in (LinkType.BLOCKS, LinkType.IS_DEPENDED_ON_BY)
            and self.target_status != StatusCategory.DONE
        )


# ---------------------------------------------------------------------------
# Workload & Capacity
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class WorkloadRecord:
    person: Person
    team: str = ""
    issue_count: int = 0
    story_points: float = 0.0
    by_type: dict[IssueType, int] = field(default_factory=dict)
    by_status: dict[StatusCategory, int] = field(default_factory=dict)
    by_priority: dict[Priority, int] = field(default_factory=dict)
    in_progress_count: int = 0
    blocked_count: int = 0


@dataclass(slots=True)
class TeamWorkload:
    team: Team
    total_issues: int = 0
    total_story_points: float = 0.0
    member_workloads: list[WorkloadRecord] = field(default_factory=list)
    by_status: dict[StatusCategory, int] = field(default_factory=dict)
    wip_count: int = 0


@dataclass(slots=True)
class CapacityRecord:
    person: Person
    team: str = ""
    allocated_points: float = 0.0
    completed_points: float = 0.0
    remaining_points: float = 0.0

    @property
    def utilization_pct(self) -> float:
        if self.allocated_points == 0:
            return 0.0
        return min(100.0, (self.completed_points / self.allocated_points) * 100)


# ---------------------------------------------------------------------------
# Risk signals
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RiskSignal:
    severity: RiskSeverity
    category: RiskCategory
    title: str
    description: str
    affected_keys: tuple[str, ...] = ()
    recommendation: str = ""


# ---------------------------------------------------------------------------
# Roadmap
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class RoadmapItem:
    key: str
    title: str
    team: str = ""
    owner: Person | None = None
    start_date: date | None = None
    target_date: date | None = None
    status: StatusCategory = StatusCategory.TODO
    progress_pct: float = 0.0
    child_count: int = 0
    done_count: int = 0
    total_points: float = 0.0
    completed_points: float = 0.0
    dependency_keys: list[str] = field(default_factory=list)
    risk_signals: list[RiskSignal] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Sprint health
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class SprintHealth:
    sprint: Sprint
    total_issues: int = 0
    done_issues: int = 0
    in_progress_issues: int = 0
    todo_issues: int = 0
    blocked_issues: int = 0
    total_points: float = 0.0
    completed_points: float = 0.0
    carry_over_count: int = 0
    aging_issues: int = 0  # issues open longer than threshold
    by_type: dict[IssueType, int] = field(default_factory=dict)
    by_assignee: dict[str, int] = field(default_factory=dict)

    @property
    def completion_pct(self) -> float:
        if self.total_issues == 0:
            return 0.0
        return (self.done_issues / self.total_issues) * 100

    @property
    def points_completion_pct(self) -> float:
        if self.total_points == 0:
            return 0.0
        return (self.completed_points / self.total_points) * 100


# ---------------------------------------------------------------------------
# Overlap / conflict
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class OverlapConflict:
    category: str  # e.g. "resource_contention", "timeline_overlap"
    severity: RiskSeverity
    description: str
    affected_keys: tuple[str, ...] = ()
    affected_people: tuple[str, ...] = ()
    recommendation: str = ""


# ---------------------------------------------------------------------------
# Aggregated board snapshot (top-level container)
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class BoardSnapshot:
    """Complete analytical snapshot used by the presentation layer."""

    generated_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    title: str = "FlowBoard Dashboard"
    projects: list[str] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    sprints: list[Sprint] = field(default_factory=list)
    teams: list[Team] = field(default_factory=list)
    people: list[Person] = field(default_factory=list)
    roadmap_items: list[RoadmapItem] = field(default_factory=list)
    sprint_health: list[SprintHealth] = field(default_factory=list)
    workload_records: list[WorkloadRecord] = field(default_factory=list)
    team_workloads: list[TeamWorkload] = field(default_factory=list)
    capacity_records: list[CapacityRecord] = field(default_factory=list)
    dependencies: list[Dependency] = field(default_factory=list)
    risk_signals: list[RiskSignal] = field(default_factory=list)
    overlap_conflicts: list[OverlapConflict] = field(default_factory=list)
    # PI snapshot is set when PI config is enabled.
    pi_snapshot: PISnapshot | None = None
    # Capacity simulation suite (populated when simulation is enabled).
    simulation: SimulationSuite | None = None
    scrum_insights: ScrumInsights | None = None
    kanban_insights: KanbanInsights | None = None
    waterfall_insights: WaterfallInsights | None = None
