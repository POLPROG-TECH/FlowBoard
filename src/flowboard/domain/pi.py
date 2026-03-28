"""Program Increment (PI) domain logic.

Computes sprint boundaries, business-day arithmetic, and PI-level
snapshots used by the presentation layer.  All dates respect a
configurable set of working days (default Mon-Fri).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

# ISO weekday: 1=Monday … 7=Sunday (matches Python's date.isoweekday())
DEFAULT_WORKING_DAYS: frozenset[int] = frozenset({1, 2, 3, 4, 5})


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class PISprintSlot:
    """One sprint slot inside a PI."""
    index: int  # 1-based (1 … sprints_per_pi)
    name: str
    start_date: date
    end_date: date
    is_current: bool
    working_days_total: int
    working_days_elapsed: int
    working_days_remaining: int


@dataclass(slots=True)
class PISnapshot:
    """Complete PI-level snapshot for the presentation layer."""
    name: str
    start_date: date
    end_date: date
    sprints: list[PISprintSlot] = field(default_factory=list)
    current_sprint_index: int | None = None  # 1-based, None if outside PI
    total_working_days: int = 0
    elapsed_working_days: int = 0
    remaining_working_days: int = 0
    progress_pct: float = 0.0
    today: date = field(default_factory=date.today)


# ---------------------------------------------------------------------------
# Business-day helpers
# ---------------------------------------------------------------------------

def _to_wd_set(working_days: list[int] | frozenset[int] | None) -> frozenset[int]:
    if working_days is None:
        return DEFAULT_WORKING_DAYS
    result = frozenset(working_days) if not isinstance(working_days, frozenset) else working_days
    if not result:
        raise ValueError("working_days cannot be empty — at least one weekday (1–7) is required")
    return result


def is_working_day(d: date, working_days: frozenset[int] | None = None) -> bool:
    """Return True if *d* falls on a configured working day."""
    wd = working_days or DEFAULT_WORKING_DAYS
    return d.isoweekday() in wd


def add_business_days(start: date, num_days: int, working_days: list[int] | None = None) -> date:
    """Advance *num_days* working days from *start* (inclusive counting).

    Returns the date that is *num_days* working days after (and including)
    *start*.  If *start* itself is a working day it counts as day 1.
    """
    wd = _to_wd_set(working_days)
    if num_days <= 0:
        return start
    current = start
    counted = 0
    while True:
        if current.isoweekday() in wd:
            counted += 1
            if counted == num_days:
                return current
        current += timedelta(days=1)
    # unreachable but keeps type checkers happy
    return current  # pragma: no cover


def count_working_days(start: date, end: date, working_days: list[int] | None = None) -> int:
    """Count working days in the range [start, end] inclusive."""
    wd = _to_wd_set(working_days)
    if start > end:
        return 0
    count = 0
    current = start
    while current <= end:
        if current.isoweekday() in wd:
            count += 1
        current += timedelta(days=1)
    return count


# ---------------------------------------------------------------------------
# Sprint boundary computation
# ---------------------------------------------------------------------------

def compute_sprint_boundaries(
    pi_start: date,
    sprint_length: int = 10,
    num_sprints: int = 5,
    working_days: list[int] | None = None,
) -> list[tuple[date, date]]:
    """Return a list of (start_date, end_date) tuples for each sprint.

    Each sprint spans *sprint_length* working days.  Sprint N+1 starts
    on the next working day after sprint N ends.
    """
    wd = _to_wd_set(working_days)
    boundaries: list[tuple[date, date]] = []
    current_start = pi_start

    # Advance to the first working day if pi_start isn't one
    while current_start.isoweekday() not in wd:
        current_start += timedelta(days=1)

    for _ in range(num_sprints):
        end = add_business_days(current_start, sprint_length, list(wd))
        boundaries.append((current_start, end))
        # Next sprint starts on the next working day after end
        nxt = end + timedelta(days=1)
        while nxt.isoweekday() not in wd:
            nxt += timedelta(days=1)
        current_start = nxt

    return boundaries


# ---------------------------------------------------------------------------
# PI snapshot computation
# ---------------------------------------------------------------------------

def compute_pi_snapshot(
    name: str,
    pi_start_iso: str,
    *,
    sprint_length: int = 10,
    num_sprints: int = 5,
    working_days: list[int] | None = None,
    today: date | None = None,
    sprint_name_prefix: str = "Sprint",
) -> PISnapshot:
    """Build a full PI snapshot from configuration values."""
    today = today or date.today()

    # Normalise date string: support single-digit month/day (e.g. "2026-3-1")
    try:
        pi_start = date.fromisoformat(pi_start_iso)
    except ValueError:
        # Attempt zero-padding as a fallback
        try:
            parts = pi_start_iso.split("-")
            pi_start = date(int(parts[0]), int(parts[1]), int(parts[2]))
        except (ValueError, IndexError) as exc:
            raise ValueError(f"Invalid PI start date: {pi_start_iso!r}") from exc

    wd_list = working_days or list(DEFAULT_WORKING_DAYS)
    # Validate working day values (must be ISO weekday 1-7)
    invalid_days = [d for d in wd_list if d < 1 or d > 7]
    if invalid_days:
        raise ValueError(
            f"Invalid working day values: {invalid_days}. "
            "Must be ISO weekday numbers 1 (Monday) through 7 (Sunday)."
        )

    boundaries = compute_sprint_boundaries(pi_start, sprint_length, num_sprints, wd_list)
    if not boundaries:
        return PISnapshot(name=name, start_date=pi_start, end_date=pi_start, today=today)

    pi_end = boundaries[-1][1]

    slots: list[PISprintSlot] = []
    current_idx: int | None = None

    for i, (s_start, s_end) in enumerate(boundaries, 1):
        total_wd = count_working_days(s_start, s_end, wd_list)
        is_current = s_start <= today <= s_end
        if is_current:
            current_idx = i
            elapsed = count_working_days(s_start, today, wd_list)
            remaining = max(0, total_wd - elapsed)
        else:
            elapsed = total_wd if today > s_end else 0
            remaining = 0 if today > s_end else total_wd

        slots.append(PISprintSlot(
            index=i,
            name=f"{sprint_name_prefix} {i}",
            start_date=s_start,
            end_date=s_end,
            is_current=is_current,
            working_days_total=total_wd,
            working_days_elapsed=elapsed,
            working_days_remaining=remaining,
        ))

    total_wd = count_working_days(pi_start, pi_end, wd_list)
    elapsed_wd = count_working_days(pi_start, min(today, pi_end), wd_list) if today >= pi_start else 0
    remaining_wd = max(0, total_wd - elapsed_wd)
    progress = (elapsed_wd / total_wd * 100) if total_wd > 0 else 0.0

    return PISnapshot(
        name=name,
        start_date=pi_start,
        end_date=pi_end,
        sprints=slots,
        current_sprint_index=current_idx,
        total_working_days=total_wd,
        elapsed_working_days=elapsed_wd,
        remaining_working_days=remaining_wd,
        progress_pct=progress,
        today=today,
    )
