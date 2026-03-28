"""Scrum-oriented analytics for Scrum Masters and Product Owners.

Provides sprint goal health, scope change tracking, blocker aging,
backlog quality, readiness assessment, delivery risk forecast,
dependency heatmaps, capacity-vs-commitment, ceremony support,
and product progress views.

Split into sub-modules for maintainability:
- scrum_models: dataclasses
- scrum_compute: analytics functions

This module re-exports everything for backward compatibility.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from flowboard.domain.scrum_compute import (
    compute_backlog_quality,
    compute_blockers,
    compute_capacity,
    compute_ceremonies,
    compute_delivery_risks,
    compute_dependency_heatmap,
    compute_product_progress,
    compute_readiness,
    compute_scope_changes,
    compute_sprint_goals,
)
from flowboard.domain.scrum_models import (  # noqa: F401 - re-export
    BacklogQualityReport,
    BlockerItem,
    CapacityRow,
    CeremonySummary,
    DeliveryRiskItem,
    DependencyHeatCell,
    EpicProgress,
    GoalItem,
    ProductProgressReport,
    ReadinessItem,
    ReadinessReport,
    ScopeChangeReport,
    ScrumInsights,
    SprintGoalReport,
)

if TYPE_CHECKING:
    from flowboard.domain.models import (
        BoardSnapshot,
    )
    from flowboard.infrastructure.config.config_models import Thresholds


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------


def compute_scrum_insights(
    snapshot: BoardSnapshot,
    thresholds: Thresholds,
    today: date | None = None,
) -> ScrumInsights:
    """Compute all Scrum-oriented analytics from a board snapshot."""
    today = today or date.today()

    sprint_goals = compute_sprint_goals(snapshot.issues, snapshot.sprint_health)
    scope_changes = compute_scope_changes(snapshot.issues, snapshot.sprint_health)
    blockers = compute_blockers(snapshot.issues, today)
    backlog = compute_backlog_quality(snapshot.issues, thresholds.aging_days, today)
    readiness = compute_readiness(snapshot.issues, thresholds.capacity_per_person)
    delivery_risks = compute_delivery_risks(snapshot.issues, snapshot.sprint_health)
    dep_cells, dep_teams = compute_dependency_heatmap(snapshot)
    capacity = compute_capacity(snapshot, thresholds.capacity_per_person)
    ceremonies = compute_ceremonies(
        snapshot.issues,
        blockers,
        sprint_goals,
        scope_changes,
        readiness,
        capacity,
        snapshot.sprint_health,
        today,
    )
    product_progress = compute_product_progress(snapshot.issues, today)

    return ScrumInsights(
        sprint_goals=sprint_goals,
        scope_changes=scope_changes,
        blockers=blockers,
        backlog_quality=backlog,
        readiness=readiness,
        delivery_risks=delivery_risks,
        dependency_heat=dep_cells,
        dependency_teams=dep_teams,
        capacity=capacity,
        ceremonies=ceremonies,
        product_progress=product_progress,
    )
