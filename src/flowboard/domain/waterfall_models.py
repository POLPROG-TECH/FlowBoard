"""Waterfall-specific domain models.

These data classes hold the results of Waterfall analytics: phases,
milestones, critical path, and the aggregate WaterfallInsights container.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(slots=True)
class Phase:
    """A project phase (e.g., Requirements, Design, Implementation, Testing)."""

    key: str
    name: str
    start_date: date | None = None
    end_date: date | None = None
    progress_pct: float = 0.0
    total_issues: int = 0
    done_issues: int = 0
    in_progress_issues: int = 0
    blocked_issues: int = 0
    status: str = "on_track"  # on_track | at_risk | delayed | completed


@dataclass(slots=True)
class Milestone:
    """A project milestone or gate review."""

    key: str
    name: str
    target_date: date | None = None
    actual_date: date | None = None
    status: str = "upcoming"  # upcoming | on_track | at_risk | missed | completed
    dependencies_met: bool = True
    blocking_issues: int = 0


@dataclass(slots=True)
class CriticalPathItem:
    """An item on the critical path — delay here delays the whole project."""

    key: str
    summary: str
    phase: str = ""
    start_date: date | None = None
    end_date: date | None = None
    slack_days: int = 0
    is_critical: bool = True
    assignee: str = ""


@dataclass(slots=True)
class PhaseProgress:
    """Summary progress across all phases."""

    total_phases: int = 0
    completed_phases: int = 0
    current_phase: str = ""
    overall_progress_pct: float = 0.0
    on_track: int = 0
    at_risk: int = 0
    delayed: int = 0


@dataclass(slots=True)
class WaterfallInsights:
    """Container for all Waterfall-oriented analytics.

    Parallel to :class:`ScrumInsights` and :class:`KanbanInsights`.
    """

    phases: list[Phase] = field(default_factory=list)
    milestones: list[Milestone] = field(default_factory=list)
    critical_path: list[CriticalPathItem] = field(default_factory=list)
    phase_progress: PhaseProgress = field(default_factory=PhaseProgress)
