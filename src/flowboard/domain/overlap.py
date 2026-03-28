"""Overlap and conflict detection.

Identifies situations where resource contention, timeline overlaps,
or excessive simultaneous work create delivery risk.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import TYPE_CHECKING

from flowboard.domain.models import Issue, OverlapConflict, RoadmapItem, WorkloadRecord
from flowboard.infrastructure.config.loader import Thresholds
from flowboard.shared.types import Priority, RiskSeverity, StatusCategory

if TYPE_CHECKING:
    from flowboard.i18n.translator import Translator


def detect_all_conflicts(
    issues: list[Issue],
    workload_records: list[WorkloadRecord],
    roadmap_items: list[RoadmapItem],
    thresholds: Thresholds,
    *,
    today: date | None = None,
    t: Translator | None = None,
) -> list[OverlapConflict]:
    """Run all conflict detectors and return severity-sorted results."""
    today = today or date.today()
    if t is None:
        from flowboard.i18n.translator import get_translator

        t = get_translator()
    conflicts: list[OverlapConflict] = []
    conflicts.extend(_detect_resource_contention(workload_records, thresholds, t=t))
    conflicts.extend(_detect_priority_pile_up(issues, thresholds, t=t))
    conflicts.extend(_detect_timeline_overlaps(roadmap_items, today, t=t))
    conflicts.extend(_detect_cross_team_dependencies(issues, t=t))
    severity_order = {
        RiskSeverity.CRITICAL: 0,
        RiskSeverity.HIGH: 1,
        RiskSeverity.MEDIUM: 2,
        RiskSeverity.LOW: 3,
        RiskSeverity.INFO: 4,
    }
    conflicts.sort(key=lambda c: severity_order.get(c.severity, 99))
    return conflicts


# ------------------------------------------------------------------
# Resource contention
# ------------------------------------------------------------------


def _detect_resource_contention(
    records: list[WorkloadRecord],
    thresholds: Thresholds,
    *,
    t: Translator | None = None,
) -> list[OverlapConflict]:
    conflicts: list[OverlapConflict] = []
    for wr in records:
        if wr.in_progress_count > thresholds.wip_limit:
            conflicts.append(
                OverlapConflict(
                    category="resource_contention",
                    severity=RiskSeverity.HIGH,
                    description=t(
                        "conflict.resource_wip",
                        name=wr.person.display_name,
                        count=wr.in_progress_count,
                        limit=thresholds.wip_limit,
                    ),
                    affected_people=(wr.person.display_name,),
                    recommendation=t("conflict.resource_wip_rec"),
                )
            )
        if wr.story_points > thresholds.overload_points * 1.5:
            conflicts.append(
                OverlapConflict(
                    category="resource_contention",
                    severity=RiskSeverity.CRITICAL,
                    description=t(
                        "conflict.resource_overload",
                        name=wr.person.display_name,
                        points=f"{wr.story_points:.0f}",
                        threshold=f"{thresholds.overload_points * 1.5:.0f}",
                    ),
                    affected_people=(wr.person.display_name,),
                    recommendation=t("conflict.resource_overload_rec"),
                )
            )
    return conflicts


# ------------------------------------------------------------------
# Priority pile-up: too many high-prio items for one person
# ------------------------------------------------------------------


def _detect_priority_pile_up(
    issues: list[Issue],
    thresholds: Thresholds,
    *,
    t: Translator | None = None,
) -> list[OverlapConflict]:
    conflicts: list[OverlapConflict] = []
    by_person: dict[str, list[Issue]] = defaultdict(list)
    for issue in issues:
        if (
            issue.assignee
            and not issue.is_done
            and issue.priority in (Priority.HIGHEST, Priority.HIGH)
        ):
            by_person[issue.assignee.display_name].append(issue)

    for name, high_prio in by_person.items():
        if len(high_prio) > 3:
            conflicts.append(
                OverlapConflict(
                    category="priority_pile_up",
                    severity=RiskSeverity.HIGH,
                    description=t(
                        "conflict.priority_desc",
                        name=name,
                        count=len(high_prio),
                    ),
                    affected_keys=tuple(i.key for i in high_prio),
                    affected_people=(name,),
                    recommendation=t("conflict.priority_rec"),
                )
            )
    return conflicts


# ------------------------------------------------------------------
# Timeline overlaps between roadmap items with the same owner/team
# ------------------------------------------------------------------


def _detect_timeline_overlaps(
    items: list[RoadmapItem],
    today: date,
    *,
    t: Translator | None = None,
) -> list[OverlapConflict]:
    conflicts: list[OverlapConflict] = []

    # Group by owner.
    by_owner: dict[str, list[RoadmapItem]] = defaultdict(list)
    for item in items:
        if (
            item.owner
            and item.start_date
            and item.target_date
            and item.status != StatusCategory.DONE
        ):
            by_owner[item.owner.display_name].append(item)

    for owner, owner_items in by_owner.items():
        owner_items.sort(key=lambda x: x.start_date or today)
        for i in range(len(owner_items)):
            for j in range(i + 1, len(owner_items)):
                a, b = owner_items[i], owner_items[j]
                if (
                    a.start_date
                    and a.target_date
                    and b.start_date
                    and b.target_date
                    and a.start_date <= b.target_date
                    and b.start_date <= a.target_date
                ):
                    conflicts.append(
                        OverlapConflict(
                            category="timeline_overlap",
                            severity=RiskSeverity.MEDIUM,
                            description=t(
                                "conflict.timeline_desc",
                                key_a=a.key,
                                key_b=b.key,
                                owner=owner,
                            ),
                            affected_keys=(a.key, b.key),
                            affected_people=(owner,),
                            recommendation=t("conflict.timeline_rec"),
                        )
                    )
    return conflicts


# ------------------------------------------------------------------
# Cross-team dependency friction
# ------------------------------------------------------------------


def _detect_cross_team_dependencies(
    issues: list[Issue], *, t: Translator | None = None
) -> list[OverlapConflict]:
    conflicts: list[OverlapConflict] = []
    issue_map = {i.key: i for i in issues}
    cross_team_pairs: set[tuple[str, str]] = set()

    for issue in issues:
        if not issue.assignee or issue.is_done:
            continue
        for lnk in issue.links:
            target = issue_map.get(lnk.target_key)
            if not (target and target.assignee):
                continue
            team_a = issue.assignee.team or "unknown"
            team_b = target.assignee.team or "unknown"
            if team_a != team_b and team_a != "unknown" and team_b != "unknown":
                pair = tuple(sorted([team_a, team_b]))
                cross_team_pairs.add((pair[0], pair[1]))

    for team_a, team_b in cross_team_pairs:
        conflicts.append(
            OverlapConflict(
                category="cross_team_dependency",
                severity=RiskSeverity.LOW,
                description=t("conflict.cross_team_desc", team_a=team_a, team_b=team_b),
                recommendation=t("conflict.cross_team_rec"),
            )
        )
    return conflicts
