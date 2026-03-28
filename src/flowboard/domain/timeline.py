"""Timeline data preparation for Gantt-style views.

Groups issues by assignee, team, or epic and computes date ranges,
overlap detection, and layout positions for rendering interactive
timeline visualizations.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flowboard.domain.models import BoardSnapshot, Issue

# ---------------------------------------------------------------------------
# Named constants (extracted from magic numbers)
# ---------------------------------------------------------------------------

DEFAULT_ISSUE_DURATION_DAYS = 14
"""Fallback duration when an issue has no end date."""

OVERLAP_CRITICAL_COUNT = 4
"""Number of concurrent bars to trigger 'critical' severity."""

OVERLAP_HIGH_COUNT = 3
"""Number of concurrent bars to trigger 'high' severity."""

MAX_EXECUTIVE_SWIMLANES = 15
"""Maximum swimlanes shown in executive timeline mode."""

DATE_RANGE_PADDING_DAYS = 3
"""Extra days added to each end of the computed timeline range."""


class TimelineMode(StrEnum):
    """Display modes for the timeline view."""

    ASSIGNEE = "assignee"
    TEAM = "team"
    EPIC = "epic"
    CONFLICT = "conflict"
    EXECUTIVE = "executive"
    ROADMAP = "roadmap"


@dataclass(frozen=True, slots=True)
class TimelineBar:
    """A single bar in the timeline representing one issue or epic."""

    key: str
    label: str
    assignee: str
    team: str
    start: date
    end: date
    progress_pct: float = 0.0
    story_points: float = 0.0
    is_blocked: bool = False
    is_done: bool = False
    issue_type: str = ""
    priority: str = ""
    epic_key: str = ""
    sprint_name: str = ""


@dataclass(slots=True)
class TimelineSwimlane:
    """A row (swimlane) in the timeline — grouped by person, team, or epic."""

    key: str
    label: str
    bars: list[TimelineBar] = field(default_factory=list)
    overlap_count: int = 0
    total_points: float = 0.0


@dataclass(frozen=True, slots=True)
class OverlapMarker:
    """A time range where multiple bars overlap for the same swimlane."""

    swimlane_key: str
    start: date
    end: date
    bar_keys: tuple[str, ...]
    severity: str = "medium"  # low, medium, high, critical


@dataclass(slots=True)
class TimelineData:
    """Complete timeline dataset ready for rendering."""

    mode: TimelineMode
    swimlanes: list[TimelineSwimlane] = field(default_factory=list)
    overlaps: list[OverlapMarker] = field(default_factory=list)
    range_start: date = field(default_factory=date.today)
    range_end: date = field(default_factory=date.today)
    total_days: int = 0
    sprint_boundaries: list[tuple[str, date, date]] = field(default_factory=list)


def _issue_date_range(issue: Issue) -> tuple[date, date] | None:
    """Extract a usable date range for a single issue.

    Uses created→due_date, falls back to sprint dates, and finally
    uses created→created+14d as a last resort.  Returns ``None`` only
    when no start date can be inferred at all.
    """
    start: date | None = None
    end: date | None = None

    if issue.created:
        start = issue.created.date() if isinstance(issue.created, datetime) else issue.created
    if issue.due_date:
        end = issue.due_date

    if issue.sprint:
        if issue.sprint.start_date and not start:
            start = issue.sprint.start_date
        if issue.sprint.end_date and not end:
            end = issue.sprint.end_date

    if start is None:
        return None

    if end is None or end <= start:
        end = start + timedelta(days=DEFAULT_ISSUE_DURATION_DAYS)

    return start, end


def _detect_overlaps(
    bars: list[TimelineBar],
    swimlane_key: str,
) -> list[OverlapMarker]:
    """Find overlapping time ranges within a swimlane."""
    if len(bars) < 2:
        return []

    sorted_bars = sorted(bars, key=lambda b: b.start)
    markers: list[OverlapMarker] = []
    active: list[TimelineBar] = []

    for bar in sorted_bars:
        # Remove bars that ended before this bar starts
        active = [a for a in active if a.end > bar.start]
        active.append(bar)

        if len(active) >= 2:
            overlap_start = bar.start
            overlap_end = min(a.end for a in active)
            if overlap_end > overlap_start:
                severity = (
                    "critical"
                    if len(active) >= OVERLAP_CRITICAL_COUNT
                    else "high"
                    if len(active) >= OVERLAP_HIGH_COUNT
                    else "medium"
                )
                markers.append(
                    OverlapMarker(
                        swimlane_key=swimlane_key,
                        start=overlap_start,
                        end=overlap_end,
                        bar_keys=tuple(a.key for a in active),
                        severity=severity,
                    )
                )

    # Deduplicate overlapping markers
    seen: set[tuple[str, ...]] = set()
    unique: list[OverlapMarker] = []
    for m in markers:
        sig = m.bar_keys
        if sig not in seen:
            seen.add(sig)
            unique.append(m)
    return unique


def _make_bar(issue: Issue, start: date, end: date) -> TimelineBar:
    """Create a TimelineBar from a domain Issue."""
    pct = 100.0 if issue.is_done else 50.0 if issue.is_in_progress else 0.0
    return TimelineBar(
        key=issue.key,
        label=issue.summary[:60],
        assignee=issue.assignee.display_name if issue.assignee else "__unassigned__",
        team=issue.assignee.team if issue.assignee else "",
        start=start,
        end=end,
        progress_pct=pct,
        story_points=issue.story_points,
        is_blocked=issue.is_blocked,
        is_done=issue.is_done,
        issue_type=issue.issue_type.value,
        priority=issue.priority.value,
        epic_key=issue.epic_key,
        sprint_name=issue.sprint.name if issue.sprint else "",
    )


def _compute_range(bars: list[TimelineBar]) -> tuple[date, date]:
    """Compute the global date range across all bars with padding."""
    if not bars:
        today = date.today()
        return today - timedelta(days=7), today + timedelta(days=30)
    earliest = min(b.start for b in bars)
    latest = max(b.end for b in bars)
    padding = timedelta(days=DATE_RANGE_PADDING_DAYS)
    return earliest - padding, latest + padding


def _sprint_boundaries(snapshot: BoardSnapshot) -> list[tuple[str, date, date]]:
    """Extract sprint boundaries for overlay markers."""
    bounds = []
    for sp in snapshot.sprints:
        if sp.start_date and sp.end_date:
            bounds.append((sp.name, sp.start_date, sp.end_date))
    return sorted(bounds, key=lambda x: x[1])


def build_assignee_timeline(snapshot: BoardSnapshot) -> TimelineData:
    """Build timeline grouped by assignee — shows personal workload over time."""
    groups: dict[str, list[TimelineBar]] = defaultdict(list)
    all_bars: list[TimelineBar] = []

    for issue in snapshot.issues:
        rng = _issue_date_range(issue)
        if rng is None:
            continue
        bar = _make_bar(issue, rng[0], rng[1])
        groups[bar.assignee].append(bar)
        all_bars.append(bar)

    swimlanes = []
    all_overlaps: list[OverlapMarker] = []
    for name in sorted(groups.keys()):
        bars = groups[name]
        overlaps = _detect_overlaps(bars, name)
        all_overlaps.extend(overlaps)
        swimlanes.append(
            TimelineSwimlane(
                key=name,
                label=name,
                bars=sorted(bars, key=lambda b: b.start),
                overlap_count=len(overlaps),
                total_points=sum(b.story_points for b in bars),
            )
        )

    # Sort by most overlaps first (most overloaded at top)
    swimlanes.sort(key=lambda s: (-s.overlap_count, s.label))

    rng_start, rng_end = _compute_range(all_bars)
    return TimelineData(
        mode=TimelineMode.ASSIGNEE,
        swimlanes=swimlanes,
        overlaps=all_overlaps,
        range_start=rng_start,
        range_end=rng_end,
        total_days=(rng_end - rng_start).days,
        sprint_boundaries=_sprint_boundaries(snapshot),
    )


def build_team_timeline(snapshot: BoardSnapshot) -> TimelineData:
    """Build timeline grouped by team — shows team-level workstreams."""
    groups: dict[str, list[TimelineBar]] = defaultdict(list)
    all_bars: list[TimelineBar] = []

    for issue in snapshot.issues:
        rng = _issue_date_range(issue)
        if rng is None:
            continue
        bar = _make_bar(issue, rng[0], rng[1])
        team_name = bar.team or "__no_team__"
        groups[team_name].append(bar)
        all_bars.append(bar)

    swimlanes = []
    all_overlaps: list[OverlapMarker] = []
    for name in sorted(groups.keys()):
        bars = groups[name]
        overlaps = _detect_overlaps(bars, name)
        all_overlaps.extend(overlaps)
        swimlanes.append(
            TimelineSwimlane(
                key=name,
                label=name,
                bars=sorted(bars, key=lambda b: b.start),
                overlap_count=len(overlaps),
                total_points=sum(b.story_points for b in bars),
            )
        )

    rng_start, rng_end = _compute_range(all_bars)
    return TimelineData(
        mode=TimelineMode.TEAM,
        swimlanes=swimlanes,
        overlaps=all_overlaps,
        range_start=rng_start,
        range_end=rng_end,
        total_days=(rng_end - rng_start).days,
        sprint_boundaries=_sprint_boundaries(snapshot),
    )


def build_epic_timeline(snapshot: BoardSnapshot) -> TimelineData:
    """Build timeline from roadmap items — epic-level time ranges."""
    from flowboard.domain.models import StatusCategory

    all_bars: list[TimelineBar] = []
    swimlanes: list[TimelineSwimlane] = []

    for ri in snapshot.roadmap_items:
        start = ri.start_date or date.today()
        end = ri.target_date or (start + timedelta(days=30))
        if end <= start:
            end = start + timedelta(days=DEFAULT_ISSUE_DURATION_DAYS)
        bar = TimelineBar(
            key=ri.key,
            label=ri.title[:60],
            assignee=ri.owner.display_name if ri.owner else "__unassigned__",
            team=ri.team,
            start=start,
            end=end,
            progress_pct=ri.progress_pct,
            story_points=ri.total_points,
            is_blocked=False,
            is_done=ri.status == StatusCategory.DONE,
            issue_type="Epic",
            priority="",
            epic_key=ri.key,
        )
        all_bars.append(bar)
        swimlanes.append(
            TimelineSwimlane(
                key=ri.key,
                label=f"{ri.key}: {ri.title[:45]}",
                bars=[bar],
                total_points=ri.total_points,
            )
        )

    # Detect overlaps across all epics for the same team
    team_groups: dict[str, list[TimelineBar]] = defaultdict(list)
    for bar in all_bars:
        team_groups[bar.team or "__no_team__"].append(bar)
    all_overlaps: list[OverlapMarker] = []
    for team_key, bars in team_groups.items():
        all_overlaps.extend(_detect_overlaps(bars, team_key))

    rng_start, rng_end = _compute_range(all_bars)
    return TimelineData(
        mode=TimelineMode.EPIC,
        swimlanes=swimlanes,
        overlaps=all_overlaps,
        range_start=rng_start,
        range_end=rng_end,
        total_days=(rng_end - rng_start).days,
        sprint_boundaries=_sprint_boundaries(snapshot),
    )


def build_conflict_timeline(snapshot: BoardSnapshot) -> TimelineData:
    """Build timeline highlighting only conflicting/overlapping work.

    Shows only swimlanes where overlaps were detected, making conflicts
    immediately visible.
    """
    full = build_assignee_timeline(snapshot)
    conflict_swimlanes = [s for s in full.swimlanes if s.overlap_count > 0]
    conflict_overlaps = [
        o for o in full.overlaps if any(s.key == o.swimlane_key for s in conflict_swimlanes)
    ]

    if not conflict_swimlanes:
        return TimelineData(
            mode=TimelineMode.CONFLICT,
            range_start=full.range_start,
            range_end=full.range_end,
            total_days=full.total_days,
            sprint_boundaries=full.sprint_boundaries,
        )

    return TimelineData(
        mode=TimelineMode.CONFLICT,
        swimlanes=conflict_swimlanes,
        overlaps=conflict_overlaps,
        range_start=full.range_start,
        range_end=full.range_end,
        total_days=full.total_days,
        sprint_boundaries=full.sprint_boundaries,
    )


def build_executive_timeline(snapshot: BoardSnapshot) -> TimelineData:
    """Build a compact executive timeline — top-level summary.

    Shows only epics/roadmap items if available, otherwise shows
    team-aggregated work in a compact form (max 15 swimlanes).
    """
    if snapshot.roadmap_items:
        data = build_epic_timeline(snapshot)
    else:
        data = build_team_timeline(snapshot)

    # Cap swimlanes for executive readability
    data.swimlanes = data.swimlanes[:MAX_EXECUTIVE_SWIMLANES]
    data.mode = TimelineMode.EXECUTIVE
    return data


def build_roadmap_timeline(snapshot: BoardSnapshot) -> TimelineData:
    """Build a timeline from roadmap items (epics/initiatives) over time.

    Each roadmap item becomes a bar grouped by team (or ungrouped).
    Overlapping roadmap items within the same team are detected.
    """
    from flowboard.domain.models import StatusCategory

    all_bars: list[TimelineBar] = []
    groups: dict[str, list[TimelineBar]] = defaultdict(list)

    for ri in snapshot.roadmap_items:
        if not ri.start_date or not ri.target_date:
            continue
        start = ri.start_date
        end = (
            ri.target_date
            if ri.target_date > ri.start_date
            else ri.start_date + timedelta(days=DEFAULT_ISSUE_DURATION_DAYS)
        )

        pct = ri.progress_pct
        is_done = ri.status == StatusCategory.DONE
        bar = TimelineBar(
            key=ri.key,
            label=ri.title[:60],
            assignee=ri.owner.display_name if ri.owner else "—",
            team=ri.team or "__no_team__",
            start=start,
            end=end,
            progress_pct=pct,
            story_points=ri.total_points,
            is_blocked=any(r.severity in ("critical", "high") for r in ri.risk_signals),
            is_done=is_done,
            issue_type="Epic",
            priority="",
            epic_key=ri.key,
            sprint_name="",
        )
        group_key = ri.team or "__no_team__"
        groups[group_key].append(bar)
        all_bars.append(bar)

    if not all_bars:
        today = date.today()
        return TimelineData(
            mode=TimelineMode.ROADMAP,
            range_start=today - timedelta(days=7),
            range_end=today + timedelta(days=30),
        )

    range_start, range_end = _compute_range(all_bars)
    total_days = max((range_end - range_start).days, 1)

    swimlanes: list[TimelineSwimlane] = []
    all_overlaps: list[OverlapMarker] = []

    for group_key in sorted(groups.keys()):
        bars = sorted(groups[group_key], key=lambda b: b.start)
        overlaps = _detect_overlaps(bars, group_key)
        all_overlaps.extend(overlaps)
        pts = sum(b.story_points for b in bars)
        swimlanes.append(
            TimelineSwimlane(
                key=group_key,
                label=group_key,
                bars=bars,
                overlap_count=len(overlaps),
                total_points=pts,
            )
        )

    return TimelineData(
        mode=TimelineMode.ROADMAP,
        swimlanes=swimlanes,
        overlaps=all_overlaps,
        range_start=range_start,
        range_end=range_end,
        total_days=total_days,
        sprint_boundaries=_sprint_boundaries(snapshot),
    )


def build_timeline(
    snapshot: BoardSnapshot,
    mode: TimelineMode = TimelineMode.ASSIGNEE,
) -> TimelineData:
    """Build timeline data for the requested mode."""
    builders = {
        TimelineMode.ASSIGNEE: build_assignee_timeline,
        TimelineMode.TEAM: build_team_timeline,
        TimelineMode.EPIC: build_epic_timeline,
        TimelineMode.CONFLICT: build_conflict_timeline,
        TimelineMode.EXECUTIVE: build_executive_timeline,
        TimelineMode.ROADMAP: build_roadmap_timeline,
    }
    builder = builders.get(mode, build_assignee_timeline)
    return builder(snapshot)
