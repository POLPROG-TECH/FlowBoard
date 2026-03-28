"""Kanban-specific domain models.

These data classes hold the results of Kanban analytics: cycle time,
lead time, throughput, WIP snapshots, flow efficiency, and the
aggregate KanbanInsights container.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(slots=True)
class CycleTimeRecord:
    """Cycle time measurement for a single completed issue."""

    key: str
    summary: str
    issue_type: str = ""
    assignee: str = ""
    team: str = ""
    cycle_time_days: float = 0.0  # time in IN_PROGRESS → DONE
    lead_time_days: float = 0.0  # time from CREATED → DONE
    started: date | None = None
    completed: date | None = None


@dataclass(slots=True)
class ThroughputRecord:
    """Number of items completed in a time bucket (day/week)."""

    period_start: date = field(default_factory=date.today)
    period_end: date = field(default_factory=date.today)
    count: int = 0
    story_points: float = 0.0


@dataclass(slots=True)
class WIPSnapshot:
    """Work-in-progress snapshot at a point in time."""

    date: date = field(default_factory=date.today)
    wip_count: int = 0
    wip_by_team: dict[str, int] = field(default_factory=dict)
    wip_by_person: dict[str, int] = field(default_factory=dict)
    violations: list[str] = field(default_factory=list)  # people/teams over limit


@dataclass(slots=True)
class CFDDataPoint:
    """A single data point for a Cumulative Flow Diagram."""

    date: date = field(default_factory=date.today)
    todo: int = 0
    in_progress: int = 0
    done: int = 0


@dataclass(slots=True)
class FlowMetrics:
    """Aggregate flow metrics for the current analysis window."""

    avg_cycle_time: float = 0.0
    median_cycle_time: float = 0.0
    p85_cycle_time: float = 0.0
    avg_lead_time: float = 0.0
    throughput_per_week: float = 0.0
    flow_efficiency: float = 0.0  # active time / total lead time (0-1)
    current_wip: int = 0
    wip_limit: int = 5
    wip_violations: int = 0


@dataclass(slots=True)
class KanbanInsights:
    """Container for all Kanban-oriented analytics.

    Parallel to :class:`ScrumInsights` — holds methodology-specific
    computed metrics for Kanban teams.
    """

    flow_metrics: FlowMetrics = field(default_factory=FlowMetrics)
    cycle_times: list[CycleTimeRecord] = field(default_factory=list)
    throughput: list[ThroughputRecord] = field(default_factory=list)
    wip_snapshot: WIPSnapshot = field(default_factory=WIPSnapshot)
    cfd_data: list[CFDDataPoint] = field(default_factory=list)
