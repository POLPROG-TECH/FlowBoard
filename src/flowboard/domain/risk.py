"""Risk detection engine.

Scans normalized issues and workload data for delivery risk signals
including aging, overload, blocked chains, scope creep, and carry-over risk.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from flowboard.domain.models import (
    Issue,
    RiskSignal,
    RoadmapItem,
    SprintHealth,
    WorkloadRecord,
)
from flowboard.infrastructure.config.loader import Thresholds
from flowboard.shared.types import (
    LinkType,
    RiskCategory,
    RiskSeverity,
    SprintState,
    StatusCategory,
)

if TYPE_CHECKING:
    from flowboard.i18n.translator import Translator


def detect_all_risks(
    issues: list[Issue],
    workload_records: list[WorkloadRecord],
    sprint_healths: list[SprintHealth],
    roadmap_items: list[RoadmapItem],
    thresholds: Thresholds,
    *,
    today: date | None = None,
    t: Translator | None = None,
) -> list[RiskSignal]:
    """Run all risk detectors and return a combined, severity-sorted list."""
    today = today or date.today()
    if t is None:
        from flowboard.i18n.translator import get_translator
        t = get_translator()
    signals: list[RiskSignal] = []
    signals.extend(_detect_overload_risks(workload_records, thresholds, t=t))
    signals.extend(_detect_aging_risks(issues, thresholds, today, t=t))
    signals.extend(_detect_blocked_risks(issues, t=t))
    signals.extend(_detect_wip_risks(workload_records, thresholds, t=t))
    signals.extend(_detect_sprint_risks(sprint_healths, today=today, t=t))
    signals.extend(_detect_roadmap_risks(roadmap_items, today, t=t))
    # Sort by severity (critical first).
    severity_order = {
        RiskSeverity.CRITICAL: 0,
        RiskSeverity.HIGH: 1,
        RiskSeverity.MEDIUM: 2,
        RiskSeverity.LOW: 3,
        RiskSeverity.INFO: 4,
    }
    signals.sort(key=lambda s: severity_order.get(s.severity, 99))
    return signals


# ------------------------------------------------------------------
# Individual detectors
# ------------------------------------------------------------------

def _detect_overload_risks(
    records: list[WorkloadRecord],
    thresholds: Thresholds,
    *,
    t: Translator | None = None,
) -> list[RiskSignal]:
    signals: list[RiskSignal] = []
    for wr in records:
        if wr.story_points > thresholds.overload_points:
            signals.append(
                RiskSignal(
                    severity=RiskSeverity.HIGH,
                    category=RiskCategory.OVERLOAD,
                    title=t("risk.overloaded", name=wr.person.display_name),
                    description=t(
                        "risk.overloaded_desc",
                        name=wr.person.display_name,
                        points=f"{wr.story_points:.0f}",
                        issues=wr.issue_count,
                        threshold=thresholds.overload_points,
                    ),
                    recommendation=t("risk.overloaded_rec"),
                )
            )
        if wr.issue_count > thresholds.overload_issues:
            signals.append(
                RiskSignal(
                    severity=RiskSeverity.MEDIUM,
                    category=RiskCategory.OVERLOAD,
                    title=t("risk.too_many_issues", name=wr.person.display_name),
                    description=t(
                        "risk.too_many_issues_desc",
                        count=wr.issue_count,
                        threshold=thresholds.overload_issues,
                    ),
                    recommendation=t("risk.too_many_issues_rec"),
                )
            )
    return signals


def _detect_aging_risks(
    issues: list[Issue],
    thresholds: Thresholds,
    today: date,
    *,
    t: Translator | None = None,
) -> list[RiskSignal]:
    signals: list[RiskSignal] = []
    for issue in issues:
        if issue.is_done:
            continue
        if issue.created:
            # Compare at date level to avoid timezone mismatch issues
            created_date = issue.created.date() if isinstance(issue.created, datetime) else issue.created
            age = (today - created_date).days
            if age < 0:
                continue  # future-dated issue, skip
            if age > thresholds.aging_days:
                sev = RiskSeverity.HIGH if age > thresholds.aging_days * 2 else RiskSeverity.MEDIUM
                signals.append(
                    RiskSignal(
                        severity=sev,
                        category=RiskCategory.AGING,
                        title=t("risk.aging", key=issue.key, days=age),
                        description=t(
                            "risk.aging_desc",
                            key=issue.key,
                            summary=issue.summary,
                            days=age,
                            threshold=thresholds.aging_days,
                        ),
                        affected_keys=(issue.key,),
                        recommendation=t("risk.aging_rec"),
                    )
                )
    return signals


def _detect_blocked_risks(issues: list[Issue], *, t: Translator | None = None) -> list[RiskSignal]:
    signals: list[RiskSignal] = []
    blocked = [i for i in issues if i.is_blocked and not i.is_done]
    if len(blocked) > 5:
        signals.append(
            RiskSignal(
                severity=RiskSeverity.HIGH,
                category=RiskCategory.BLOCKED,
                title=t("risk.many_blocked", count=len(blocked)),
                description=t("risk.many_blocked_desc"),
                affected_keys=tuple(i.key for i in blocked[:10]),
                recommendation=t("risk.many_blocked_rec"),
            )
        )
    for issue in blocked:
        blockers = [
            lnk.target_key for lnk in issue.links
            if lnk.link_type in (LinkType.IS_BLOCKED_BY, LinkType.DEPENDS_ON)
            and not lnk.is_resolved
        ]
        signals.append(
            RiskSignal(
                severity=RiskSeverity.MEDIUM,
                category=RiskCategory.BLOCKED,
                title=t("risk.blocked", key=issue.key),
                description=t(
                    "risk.blocked_desc",
                    key=issue.key,
                    blockers=", ".join(blockers[:5]),
                ),
                affected_keys=(issue.key, *tuple(blockers[:5])),
                recommendation=t("risk.blocked_rec"),
            )
        )
    return signals


def _detect_wip_risks(
    records: list[WorkloadRecord],
    thresholds: Thresholds,
    *,
    t: Translator | None = None,
) -> list[RiskSignal]:
    signals: list[RiskSignal] = []
    for wr in records:
        if wr.in_progress_count > thresholds.wip_limit:
            signals.append(
                RiskSignal(
                    severity=RiskSeverity.MEDIUM,
                    category=RiskCategory.WIP_LIMIT,
                    title=t("risk.wip_exceeded", name=wr.person.display_name),
                    description=t(
                        "risk.wip_exceeded_desc",
                        count=wr.in_progress_count,
                        limit=thresholds.wip_limit,
                    ),
                    recommendation=t("risk.wip_exceeded_rec"),
                )
            )
    return signals


def _detect_sprint_risks(
    healths: list[SprintHealth],
    *,
    today: date | None = None,
    t: Translator | None = None,
) -> list[RiskSignal]:
    signals: list[RiskSignal] = []
    today = today or date.today()
    for sh in healths:
        if sh.sprint.state != SprintState.ACTIVE:
            continue
        if sh.completion_pct < 30 and sh.sprint.end_date:
            days_left = max(0, (sh.sprint.end_date - today).days)
            if days_left <= 3:
                signals.append(
                    RiskSignal(
                        severity=RiskSeverity.CRITICAL,
                        category=RiskCategory.CARRY_OVER,
                        title=t("risk.sprint_at_risk", name=sh.sprint.name),
                        description=t(
                            "risk.sprint_at_risk_desc",
                            pct=f"{sh.completion_pct:.0f}",
                            days=days_left,
                        ),
                        recommendation=t("risk.sprint_at_risk_rec"),
                    )
                )
        if sh.blocked_issues > 2:
            signals.append(
                RiskSignal(
                    severity=RiskSeverity.HIGH,
                    category=RiskCategory.BLOCKED,
                    title=t("risk.sprint_blocked", name=sh.sprint.name, count=sh.blocked_issues),
                    description=t("risk.sprint_blocked_desc"),
                    recommendation=t("risk.sprint_blocked_rec"),
                )
            )
    return signals


def _detect_roadmap_risks(
    items: list[RoadmapItem],
    today: date,
    *,
    t: Translator | None = None,
) -> list[RiskSignal]:
    signals: list[RiskSignal] = []
    for item in items:
        if item.status == StatusCategory.DONE:
            continue
        if item.target_date and item.target_date < today and item.progress_pct < 100:
            signals.append(
                RiskSignal(
                    severity=RiskSeverity.HIGH,
                    category=RiskCategory.SCOPE_CREEP,
                    title=t("risk.epic_overdue", key=item.key),
                    description=t(
                        "risk.epic_overdue_desc",
                        title=item.title,
                        date=item.target_date.isoformat(),
                        pct=f"{item.progress_pct:.0f}",
                    ),
                    affected_keys=(item.key,),
                    recommendation=t("risk.epic_overdue_rec"),
                )
            )
        if item.target_date:
            days_to_target = (item.target_date - today).days
            if 0 < days_to_target <= 14 and item.progress_pct < 50:
                signals.append(
                    RiskSignal(
                        severity=RiskSeverity.MEDIUM,
                        category=RiskCategory.SCOPE_CREEP,
                        title=t("risk.epic_may_miss", key=item.key),
                        description=t(
                            "risk.epic_may_miss_desc",
                            title=item.title,
                            pct=f"{item.progress_pct:.0f}",
                            days=days_to_target,
                        ),
                        affected_keys=(item.key,),
                        recommendation=t("risk.epic_may_miss_rec"),
                    )
                )
    return signals
