"""Tests for PI (Program Increment) domain logic - sprint boundaries,
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
    """GIVEN is working day and the scenario: monday is working"""
    def test_monday_is_working(self) -> None:
        """THEN the expected behaviour holds: monday is working"""
        assert is_working_day(date(2026, 3, 2)) is True  # Monday

    """GIVEN is working day and the scenario: friday is working"""
    def test_friday_is_working(self) -> None:
        """THEN the expected behaviour holds: friday is working"""
        assert is_working_day(date(2026, 3, 6)) is True  # Friday

    """GIVEN is working day and the scenario: saturday is not working"""
    def test_saturday_is_not_working(self) -> None:
        """THEN the expected behaviour holds: saturday is not working"""
        assert is_working_day(date(2026, 3, 7)) is False  # Saturday

    """GIVEN is working day and the scenario: sunday is not working"""
    def test_sunday_is_not_working(self) -> None:
        """THEN the expected behaviour holds: sunday is not working"""
        assert is_working_day(date(2026, 3, 8)) is False  # Sunday

    """GIVEN is working day and the scenario: custom working days"""
    def test_custom_working_days(self) -> None:
        # Only Mon-Thu

        """WHEN the code under test is exercised for: custom working days"""
        wd = frozenset({1, 2, 3, 4})

        """THEN the expected behaviour holds: custom working days"""
        assert is_working_day(date(2026, 3, 6), wd) is False  # Friday
        assert is_working_day(date(2026, 3, 5), wd) is True  # Thursday


# ---------------------------------------------------------------------------
# add_business_days
# ---------------------------------------------------------------------------


class TestAddBusinessDays:
    """GIVEN add business days and the scenario: one business day from monday"""
    def test_one_business_day_from_monday(self) -> None:
        # Monday → still Monday (day 1 counts as working day)

        """THEN the expected behaviour holds: one business day from monday"""
        assert add_business_days(date(2026, 3, 2), 1) == date(2026, 3, 2)

    """GIVEN add business days and the scenario: five business days from monday"""
    def test_five_business_days_from_monday(self) -> None:
        # Mon through Fri = 5 working days

        """THEN the expected behaviour holds: five business days from monday"""
        assert add_business_days(date(2026, 3, 2), 5) == date(2026, 3, 6)

    """GIVEN add business days and the scenario: ten business days from monday"""
    def test_ten_business_days_from_monday(self) -> None:
        # Mon Mar 2 through Fri Mar 13 = 10 working days (skipping weekend)

        """THEN the expected behaviour holds: ten business days from monday"""
        assert add_business_days(date(2026, 3, 2), 10) == date(2026, 3, 13)

    """GIVEN add business days and the scenario: skips weekends"""
    def test_skips_weekends(self) -> None:
        # 6 working days from Mon: Mon-Fri + Mon of next week

        """THEN the expected behaviour holds: skips weekends"""
        assert add_business_days(date(2026, 3, 2), 6) == date(2026, 3, 9)

    """GIVEN add business days and the scenario: zero days returns start"""
    def test_zero_days_returns_start(self) -> None:
        """THEN the expected behaviour holds: zero days returns start"""
        assert add_business_days(date(2026, 3, 2), 0) == date(2026, 3, 2)

    """GIVEN add business days and the scenario: negative days returns start"""
    def test_negative_days_returns_start(self) -> None:
        """THEN the expected behaviour holds: negative days returns start"""
        assert add_business_days(date(2026, 3, 2), -1) == date(2026, 3, 2)

    """GIVEN add business days and the scenario: start on weekend counts next monday"""
    def test_start_on_weekend_counts_next_monday(self) -> None:
        # Saturday: first working day is Monday

        """WHEN the code under test is exercised for: start on weekend counts next monday"""
        result = add_business_days(date(2026, 3, 7), 1)

        """THEN the expected behaviour holds: start on weekend counts next monday"""
        assert result == date(2026, 3, 9)  # Monday

    """GIVEN add business days and the scenario: custom working days"""
    def test_custom_working_days(self) -> None:
        # Mon-Thu only

        """WHEN the code under test is exercised for: custom working days"""
        wd = [1, 2, 3, 4]
        # From Mon, 5 working days: Mon-Thu + Mon next week
        result = add_business_days(date(2026, 3, 2), 5, wd)

        """THEN the expected behaviour holds: custom working days"""
        assert result == date(2026, 3, 9)  # Monday next week


# ---------------------------------------------------------------------------
# count_working_days
# ---------------------------------------------------------------------------


class TestCountWorkingDays:
    """GIVEN count working days and the scenario: single working day"""
    def test_single_working_day(self) -> None:
        """THEN the expected behaviour holds: single working day"""
        assert count_working_days(date(2026, 3, 2), date(2026, 3, 2)) == 1

    """GIVEN count working days and the scenario: full week"""
    def test_full_week(self) -> None:
        # Mon-Fri = 5 working days

        """THEN the expected behaviour holds: full week"""
        assert count_working_days(date(2026, 3, 2), date(2026, 3, 6)) == 5

    """GIVEN count working days and the scenario: two weeks"""
    def test_two_weeks(self) -> None:
        # Mon-Fri of 2 weeks = 10 working days

        """THEN the expected behaviour holds: two weeks"""
        assert count_working_days(date(2026, 3, 2), date(2026, 3, 13)) == 10

    """GIVEN count working days and the scenario: across weekend"""
    def test_across_weekend(self) -> None:
        # Mon-Mon = 5 working days of first week + Mon = 6

        """THEN the expected behaviour holds: across weekend"""
        assert count_working_days(date(2026, 3, 2), date(2026, 3, 9)) == 6

    """GIVEN count working days and the scenario: start after end returns zero"""
    def test_start_after_end_returns_zero(self) -> None:
        """THEN the expected behaviour holds: start after end returns zero"""
        assert count_working_days(date(2026, 3, 10), date(2026, 3, 2)) == 0

    """GIVEN count working days and the scenario: weekend days excluded"""
    def test_weekend_days_excluded(self) -> None:
        # Saturday to Sunday = 0 working days

        """THEN the expected behaviour holds: weekend days excluded"""
        assert count_working_days(date(2026, 3, 7), date(2026, 3, 8)) == 0

    """GIVEN count working days and the scenario: saturday to monday"""
    def test_saturday_to_monday(self) -> None:
        # Sat, Sun, Mon = 1 working day

        """THEN the expected behaviour holds: saturday to monday"""
        assert count_working_days(date(2026, 3, 7), date(2026, 3, 9)) == 1


# ---------------------------------------------------------------------------
# compute_sprint_boundaries
# ---------------------------------------------------------------------------


class TestComputeSprintBoundaries:
    """GIVEN compute sprint boundaries and the scenario: default five sprints"""
    def test_default_five_sprints(self) -> None:
        """WHEN the code under test is exercised for: default five sprints"""
        boundaries = compute_sprint_boundaries(date(2026, 3, 2))

        """THEN the expected behaviour holds: default five sprints"""
        assert len(boundaries) == 5

    """GIVEN compute sprint boundaries and the scenario: first sprint starts on pi start"""
    def test_first_sprint_starts_on_pi_start(self) -> None:
        """WHEN the code under test is exercised for: first sprint starts on pi start"""
        boundaries = compute_sprint_boundaries(date(2026, 3, 2))

        """THEN the expected behaviour holds: first sprint starts on pi start"""
        assert boundaries[0][0] == date(2026, 3, 2)  # Monday

    """GIVEN compute sprint boundaries and the scenario: sprint length is 10 working days"""
    def test_sprint_length_is_10_working_days(self) -> None:
        """WHEN the code under test is exercised for: sprint length is 10 working days"""
        boundaries = compute_sprint_boundaries(date(2026, 3, 2))
        s1_start, s1_end = boundaries[0]
        wd = count_working_days(s1_start, s1_end)

        """THEN the expected behaviour holds: sprint length is 10 working days"""
        assert wd == 10

    """GIVEN compute sprint boundaries and the scenario: sprints are contiguous"""
    def test_sprints_are_contiguous(self) -> None:
        """WHEN the code under test is exercised for: sprints are contiguous"""
        boundaries = compute_sprint_boundaries(date(2026, 3, 2))

        """THEN the expected behaviour holds: sprints are contiguous"""
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

    """GIVEN compute sprint boundaries and the scenario: pi start on weekend advances to monday"""
    def test_pi_start_on_weekend_advances_to_monday(self) -> None:
        """WHEN the code under test is exercised for: pi start on weekend advances to monday"""
        boundaries = compute_sprint_boundaries(date(2026, 3, 7))  # Saturday

        """THEN the expected behaviour holds: pi start on weekend advances to monday"""
        assert boundaries[0][0] == date(2026, 3, 9)  # Monday

    """GIVEN compute sprint boundaries and the scenario: custom sprint length"""
    def test_custom_sprint_length(self) -> None:
        """WHEN the code under test is exercised for: custom sprint length"""
        boundaries = compute_sprint_boundaries(date(2026, 3, 2), sprint_length=5, num_sprints=2)

        """THEN the expected behaviour holds: custom sprint length"""
        assert len(boundaries) == 2
        wd = count_working_days(boundaries[0][0], boundaries[0][1])
        assert wd == 5

    """GIVEN compute sprint boundaries and the scenario: specific dates for first two sprints"""
    def test_specific_dates_for_first_two_sprints(self) -> None:
        # PI starts Mon March 2, 2026

        """WHEN the code under test is exercised for: specific dates for first two sprints"""
        boundaries = compute_sprint_boundaries(date(2026, 3, 2))
        # Sprint 1: Mon Mar 2 - Fri Mar 13 (10 working days)

        """THEN the expected behaviour holds: specific dates for first two sprints"""
        assert boundaries[0] == (date(2026, 3, 2), date(2026, 3, 13))
        # Sprint 2: Mon Mar 16 - Fri Mar 27 (10 working days)
        assert boundaries[1] == (date(2026, 3, 16), date(2026, 3, 27))


# ---------------------------------------------------------------------------
# compute_pi_snapshot
# ---------------------------------------------------------------------------


class TestComputePISnapshot:
    """GIVEN compute p i snapshot and the scenario: basic snapshot structure"""
    def test_basic_snapshot_structure(self) -> None:
        """WHEN the code under test is exercised for: basic snapshot structure"""
        snap = compute_pi_snapshot("PI 2026.1", "2026-03-02", today=date(2026, 3, 5))

        """THEN the expected behaviour holds: basic snapshot structure"""
        assert isinstance(snap, PISnapshot)
        assert snap.name == "PI 2026.1"
        assert len(snap.sprints) == 5
        assert snap.start_date == date(2026, 3, 2)

    """GIVEN compute p i snapshot and the scenario: current sprint detected"""
    def test_current_sprint_detected(self) -> None:
        # March 5 is Thu of first sprint (Mar 2-13)

        """WHEN the code under test is exercised for: current sprint detected"""
        snap = compute_pi_snapshot("PI", "2026-03-02", today=date(2026, 3, 5))

        """THEN the expected behaviour holds: current sprint detected"""
        assert snap.current_sprint_index == 1

    """GIVEN compute p i snapshot and the scenario: current sprint second"""
    def test_current_sprint_second(self) -> None:
        # March 20 falls in Sprint 2 (Mar 16-27)

        """WHEN the code under test is exercised for: current sprint second"""
        snap = compute_pi_snapshot("PI", "2026-03-02", today=date(2026, 3, 20))

        """THEN the expected behaviour holds: current sprint second"""
        assert snap.current_sprint_index == 2

    """GIVEN compute p i snapshot and the scenario: today before pi start"""
    def test_today_before_pi_start(self) -> None:
        """WHEN the code under test is exercised for: today before pi start"""
        snap = compute_pi_snapshot("PI", "2026-03-02", today=date(2026, 2, 1))

        """THEN the expected behaviour holds: today before pi start"""
        assert snap.current_sprint_index is None
        assert snap.elapsed_working_days == 0
        assert snap.progress_pct == 0.0

    """GIVEN compute p i snapshot and the scenario: today after pi end"""
    def test_today_after_pi_end(self) -> None:
        """WHEN the code under test is exercised for: today after pi end"""
        snap = compute_pi_snapshot("PI", "2026-03-02", today=date(2026, 12, 31))

        """THEN the expected behaviour holds: today after pi end"""
        assert snap.current_sprint_index is None
        assert snap.progress_pct == 100.0

    """GIVEN compute p i snapshot and the scenario: total working days"""
    def test_total_working_days(self) -> None:
        """WHEN the code under test is exercised for: total working days"""
        snap = compute_pi_snapshot("PI", "2026-03-02", today=date(2026, 3, 2))
        # 5 sprints x 10 working days = 50 total

        """THEN the expected behaviour holds: total working days"""
        assert snap.total_working_days == 50

    """GIVEN compute p i snapshot and the scenario: remaining days in sprint"""
    def test_remaining_days_in_sprint(self) -> None:
        # Day 4 of sprint 1 (Thu Mar 5), so 4 days elapsed (Mon-Thu), 6 remaining

        """WHEN the code under test is exercised for: remaining days in sprint"""
        snap = compute_pi_snapshot("PI", "2026-03-02", today=date(2026, 3, 5))
        sprint_1 = snap.sprints[0]

        """THEN the expected behaviour holds: remaining days in sprint"""
        assert sprint_1.is_current is True
        assert sprint_1.working_days_elapsed == 4
        assert sprint_1.working_days_remaining == 6

    """GIVEN compute p i snapshot and the scenario: sprint names"""
    def test_sprint_names(self) -> None:
        """WHEN the code under test is exercised for: sprint names"""
        snap = compute_pi_snapshot("PI", "2026-03-02", today=date(2026, 3, 2))
        names = [s.name for s in snap.sprints]

        """THEN the expected behaviour holds: sprint names"""
        assert names == ["Sprint 1", "Sprint 2", "Sprint 3", "Sprint 4", "Sprint 5"]

    """GIVEN compute p i snapshot and the scenario: custom sprint name prefix"""
    def test_custom_sprint_name_prefix(self) -> None:
        """WHEN the code under test is exercised for: custom sprint name prefix"""
        snap = compute_pi_snapshot(
            "PI", "2026-03-02", today=date(2026, 3, 2), sprint_name_prefix="Iteration"
        )

        """THEN the expected behaviour holds: custom sprint name prefix"""
        assert snap.sprints[0].name == "Iteration 1"

    """GIVEN compute p i snapshot and the scenario: progress midway"""
    def test_progress_midway(self) -> None:
        # Mid-PI: use a date roughly in the middle

        """WHEN the code under test is exercised for: progress midway"""
        snap = compute_pi_snapshot("PI", "2026-03-02", today=date(2026, 4, 13))
        # Sprint 3 is approx mid-PI

        """THEN the expected behaviour holds: progress midway"""
        assert 30 < snap.progress_pct < 70

    """GIVEN compute p i snapshot and the scenario: pi end date"""
    def test_pi_end_date(self) -> None:
        """WHEN the code under test is exercised for: pi end date"""
        snap = compute_pi_snapshot("PI", "2026-03-02", today=date(2026, 3, 2))
        # 5 x 10 = 50 working days from March 2 = ends on May 8

        """THEN the expected behaviour holds: pi end date"""
        assert snap.end_date == date(2026, 5, 8)

    """GIVEN compute p i snapshot and the scenario: custom working days"""
    def test_custom_working_days(self) -> None:
        # Mon-Thu only (4-day work week)

        """WHEN the code under test is exercised for: custom working days"""
        snap = compute_pi_snapshot(
            "PI",
            "2026-03-02",
            sprint_length=8,
            num_sprints=2,
            working_days=[1, 2, 3, 4],
            today=date(2026, 3, 2),
        )

        """THEN the expected behaviour holds: custom working days"""
        assert len(snap.sprints) == 2
        assert snap.sprints[0].working_days_total == 8
