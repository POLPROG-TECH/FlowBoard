"""Tests for PI (Program Increment) domain logic — sprint boundaries,
business-day arithmetic, and PI snapshot computation.
"""

from __future__ import annotations

from datetime import date

from flowboard.domain.pi import (
    PISnapshot,
    add_business_days,
    compute_pi_snapshot,
    compute_sprint_boundaries,
    count_working_days,
    is_working_day,
)

# ---------------------------------------------------------------------------
# is_working_day
# ---------------------------------------------------------------------------


class TestIsWorkingDay:
    def test_monday_is_working(self) -> None:
        assert is_working_day(date(2026, 3, 2)) is True  # Monday

    def test_friday_is_working(self) -> None:
        assert is_working_day(date(2026, 3, 6)) is True  # Friday

    def test_saturday_is_not_working(self) -> None:
        assert is_working_day(date(2026, 3, 7)) is False  # Saturday

    def test_sunday_is_not_working(self) -> None:
        assert is_working_day(date(2026, 3, 8)) is False  # Sunday

    def test_custom_working_days(self) -> None:
        # Only Mon-Thu
        wd = frozenset({1, 2, 3, 4})
        assert is_working_day(date(2026, 3, 6), wd) is False  # Friday
        assert is_working_day(date(2026, 3, 5), wd) is True  # Thursday


# ---------------------------------------------------------------------------
# add_business_days
# ---------------------------------------------------------------------------


class TestAddBusinessDays:
    def test_one_business_day_from_monday(self) -> None:
        # Monday → still Monday (day 1 counts as working day)
        assert add_business_days(date(2026, 3, 2), 1) == date(2026, 3, 2)

    def test_five_business_days_from_monday(self) -> None:
        # Mon through Fri = 5 working days
        assert add_business_days(date(2026, 3, 2), 5) == date(2026, 3, 6)

    def test_ten_business_days_from_monday(self) -> None:
        # Mon Mar 2 through Fri Mar 13 = 10 working days (skipping weekend)
        assert add_business_days(date(2026, 3, 2), 10) == date(2026, 3, 13)

    def test_skips_weekends(self) -> None:
        # 6 working days from Mon: Mon-Fri + Mon of next week
        assert add_business_days(date(2026, 3, 2), 6) == date(2026, 3, 9)

    def test_zero_days_returns_start(self) -> None:
        assert add_business_days(date(2026, 3, 2), 0) == date(2026, 3, 2)

    def test_negative_days_returns_start(self) -> None:
        assert add_business_days(date(2026, 3, 2), -1) == date(2026, 3, 2)

    def test_start_on_weekend_counts_next_monday(self) -> None:
        # Saturday: first working day is Monday
        result = add_business_days(date(2026, 3, 7), 1)
        assert result == date(2026, 3, 9)  # Monday

    def test_custom_working_days(self) -> None:
        # Mon-Thu only
        wd = [1, 2, 3, 4]
        # From Mon, 5 working days: Mon-Thu + Mon next week
        result = add_business_days(date(2026, 3, 2), 5, wd)
        assert result == date(2026, 3, 9)  # Monday next week


# ---------------------------------------------------------------------------
# count_working_days
# ---------------------------------------------------------------------------


class TestCountWorkingDays:
    def test_single_working_day(self) -> None:
        assert count_working_days(date(2026, 3, 2), date(2026, 3, 2)) == 1

    def test_full_week(self) -> None:
        # Mon-Fri = 5 working days
        assert count_working_days(date(2026, 3, 2), date(2026, 3, 6)) == 5

    def test_two_weeks(self) -> None:
        # Mon-Fri of 2 weeks = 10 working days
        assert count_working_days(date(2026, 3, 2), date(2026, 3, 13)) == 10

    def test_across_weekend(self) -> None:
        # Mon-Mon = 5 working days of first week + Mon = 6
        assert count_working_days(date(2026, 3, 2), date(2026, 3, 9)) == 6

    def test_start_after_end_returns_zero(self) -> None:
        assert count_working_days(date(2026, 3, 10), date(2026, 3, 2)) == 0

    def test_weekend_days_excluded(self) -> None:
        # Saturday to Sunday = 0 working days
        assert count_working_days(date(2026, 3, 7), date(2026, 3, 8)) == 0

    def test_saturday_to_monday(self) -> None:
        # Sat, Sun, Mon = 1 working day
        assert count_working_days(date(2026, 3, 7), date(2026, 3, 9)) == 1


# ---------------------------------------------------------------------------
# compute_sprint_boundaries
# ---------------------------------------------------------------------------


class TestComputeSprintBoundaries:
    def test_default_five_sprints(self) -> None:
        boundaries = compute_sprint_boundaries(date(2026, 3, 2))
        assert len(boundaries) == 5

    def test_first_sprint_starts_on_pi_start(self) -> None:
        boundaries = compute_sprint_boundaries(date(2026, 3, 2))
        assert boundaries[0][0] == date(2026, 3, 2)  # Monday

    def test_sprint_length_is_10_working_days(self) -> None:
        boundaries = compute_sprint_boundaries(date(2026, 3, 2))
        s1_start, s1_end = boundaries[0]
        wd = count_working_days(s1_start, s1_end)
        assert wd == 10

    def test_sprints_are_contiguous(self) -> None:
        boundaries = compute_sprint_boundaries(date(2026, 3, 2))
        for i in range(len(boundaries) - 1):
            prev_end = boundaries[i][1]
            next_start = boundaries[i + 1][0]
            # Next start should be the next working day after prev end
            assert next_start > prev_end
            # No working day gap: the day after prev_end (possibly skipping weekend)
            # should be next_start
            working_between = count_working_days(prev_end, next_start)
            # prev_end is last working day of sprint, next_start is first of next
            assert working_between == 2  # end day + start day

    def test_pi_start_on_weekend_advances_to_monday(self) -> None:
        boundaries = compute_sprint_boundaries(date(2026, 3, 7))  # Saturday
        assert boundaries[0][0] == date(2026, 3, 9)  # Monday

    def test_custom_sprint_length(self) -> None:
        boundaries = compute_sprint_boundaries(date(2026, 3, 2), sprint_length=5, num_sprints=2)
        assert len(boundaries) == 2
        wd = count_working_days(boundaries[0][0], boundaries[0][1])
        assert wd == 5

    def test_specific_dates_for_first_two_sprints(self) -> None:
        # PI starts Mon March 2, 2026
        boundaries = compute_sprint_boundaries(date(2026, 3, 2))
        # Sprint 1: Mon Mar 2 - Fri Mar 13 (10 working days)
        assert boundaries[0] == (date(2026, 3, 2), date(2026, 3, 13))
        # Sprint 2: Mon Mar 16 - Fri Mar 27 (10 working days)
        assert boundaries[1] == (date(2026, 3, 16), date(2026, 3, 27))


# ---------------------------------------------------------------------------
# compute_pi_snapshot
# ---------------------------------------------------------------------------


class TestComputePISnapshot:
    def test_basic_snapshot_structure(self) -> None:
        snap = compute_pi_snapshot("PI 2026.1", "2026-03-02", today=date(2026, 3, 5))
        assert isinstance(snap, PISnapshot)
        assert snap.name == "PI 2026.1"
        assert len(snap.sprints) == 5
        assert snap.start_date == date(2026, 3, 2)

    def test_current_sprint_detected(self) -> None:
        # March 5 is Thu of first sprint (Mar 2-13)
        snap = compute_pi_snapshot("PI", "2026-03-02", today=date(2026, 3, 5))
        assert snap.current_sprint_index == 1

    def test_current_sprint_second(self) -> None:
        # March 20 falls in Sprint 2 (Mar 16-27)
        snap = compute_pi_snapshot("PI", "2026-03-02", today=date(2026, 3, 20))
        assert snap.current_sprint_index == 2

    def test_today_before_pi_start(self) -> None:
        snap = compute_pi_snapshot("PI", "2026-03-02", today=date(2026, 2, 1))
        assert snap.current_sprint_index is None
        assert snap.elapsed_working_days == 0
        assert snap.progress_pct == 0.0

    def test_today_after_pi_end(self) -> None:
        snap = compute_pi_snapshot("PI", "2026-03-02", today=date(2026, 12, 31))
        assert snap.current_sprint_index is None
        assert snap.progress_pct == 100.0

    def test_total_working_days(self) -> None:
        snap = compute_pi_snapshot("PI", "2026-03-02", today=date(2026, 3, 2))
        # 5 sprints x 10 working days = 50 total
        assert snap.total_working_days == 50

    def test_remaining_days_in_sprint(self) -> None:
        # Day 4 of sprint 1 (Thu Mar 5), so 4 days elapsed (Mon-Thu), 6 remaining
        snap = compute_pi_snapshot("PI", "2026-03-02", today=date(2026, 3, 5))
        sprint_1 = snap.sprints[0]
        assert sprint_1.is_current is True
        assert sprint_1.working_days_elapsed == 4
        assert sprint_1.working_days_remaining == 6

    def test_sprint_names(self) -> None:
        snap = compute_pi_snapshot("PI", "2026-03-02", today=date(2026, 3, 2))
        names = [s.name for s in snap.sprints]
        assert names == ["Sprint 1", "Sprint 2", "Sprint 3", "Sprint 4", "Sprint 5"]

    def test_custom_sprint_name_prefix(self) -> None:
        snap = compute_pi_snapshot(
            "PI", "2026-03-02", today=date(2026, 3, 2), sprint_name_prefix="Iteration"
        )
        assert snap.sprints[0].name == "Iteration 1"

    def test_progress_midway(self) -> None:
        # Mid-PI: use a date roughly in the middle
        snap = compute_pi_snapshot("PI", "2026-03-02", today=date(2026, 4, 13))
        # Sprint 3 is approx mid-PI
        assert 30 < snap.progress_pct < 70

    def test_pi_end_date(self) -> None:
        snap = compute_pi_snapshot("PI", "2026-03-02", today=date(2026, 3, 2))
        # 5 x 10 = 50 working days from March 2 = ends on May 8
        assert snap.end_date == date(2026, 5, 8)

    def test_custom_working_days(self) -> None:
        # Mon-Thu only (4-day work week)
        snap = compute_pi_snapshot(
            "PI",
            "2026-03-02",
            sprint_length=8,
            num_sprints=2,
            working_days=[1, 2, 3, 4],
            today=date(2026, 3, 2),
        )
        assert len(snap.sprints) == 2
        assert snap.sprints[0].working_days_total == 8
