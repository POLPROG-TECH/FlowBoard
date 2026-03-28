"""Reusable HTML component builders for the dashboard.

Each function returns an HTML string fragment that can be embedded inside
the Jinja2 template context or called directly.
"""

from __future__ import annotations

from markupsafe import escape

from flowboard.domain.models import (
    BoardSnapshot,
)
from flowboard.i18n.translator import Translator, get_translator
from flowboard.infrastructure.config.loader import SummaryCardsConfig
from flowboard.shared.types import IssueType, LinkType, RiskSeverity, StatusCategory


def _esc(value: object) -> str:
    """HTML-escape a value for safe embedding in HTML output."""
    return str(escape(str(value)))


def _t(t: Translator, key: str, **kwargs: object) -> str:
    """Translate and HTML-escape for safe embedding."""
    return _esc(t(key, **kwargs))


_SENTINEL_KEYS = {"__unassigned__": "common.unassigned", "__no_team__": "common.no_team"}


def _loc(value: str, t: Translator) -> str:
    """Translate sentinel domain values like __unassigned__, __no_team__."""
    key = _SENTINEL_KEYS.get(value)
    return _esc(t(key)) if key else _esc(value)


# ---------------------------------------------------------------------------
# Severity / status styling
# ---------------------------------------------------------------------------

SEVERITY_BADGE: dict[RiskSeverity, tuple[str, str]] = {
    RiskSeverity.CRITICAL: ("bg-red-600 text-white", "🔴"),
    RiskSeverity.HIGH: ("bg-amber-500 text-white", "🟠"),
    RiskSeverity.MEDIUM: ("bg-blue-500 text-white", "🔵"),
    RiskSeverity.LOW: ("bg-emerald-500 text-white", "🟢"),
    RiskSeverity.INFO: ("bg-slate-400 text-white", "ℹ️"),
}

STATUS_CHIP: dict[StatusCategory, str] = {
    StatusCategory.TODO: "chip-todo",
    StatusCategory.IN_PROGRESS: "chip-inprogress",
    StatusCategory.DONE: "chip-done",
}

_STATUS_CAT_KEYS = {
    StatusCategory.TODO: "todo",
    StatusCategory.IN_PROGRESS: "in_progress",
    StatusCategory.DONE: "done",
}


def _status_cat_key(cat: StatusCategory) -> str:
    return _STATUS_CAT_KEYS.get(cat, "todo")


_ISSUE_TYPE_KEYS = {
    IssueType.EPIC: "epic",
    IssueType.STORY: "story",
    IssueType.TASK: "task",
    IssueType.BUG: "bug",
    IssueType.SUB_TASK: "sub_task",
    IssueType.OTHER: "other",
}


def _issue_type_key(it: IssueType) -> str:
    return _ISSUE_TYPE_KEYS.get(it, "other")


_LINK_TYPE_KEYS = {
    LinkType.BLOCKS: "blocks",
    LinkType.IS_BLOCKED_BY: "is_blocked_by",
    LinkType.DEPENDS_ON: "depends_on",
    LinkType.IS_DEPENDED_ON_BY: "is_depended_on_by",
    LinkType.RELATES_TO: "relates_to",
    LinkType.CLONES: "clones",
    LinkType.IS_CLONED_BY: "is_cloned_by",
    LinkType.PARENT: "parent",
    LinkType.CHILD: "child",
}


def _link_type_key(lt: LinkType) -> str:
    return _LINK_TYPE_KEYS.get(lt, "relates_to")


def severity_badge(sev: RiskSeverity, t: Translator | None = None) -> str:
    if t is None:
        t = get_translator()
    cls, icon = SEVERITY_BADGE.get(sev, ("bg-slate-400 text-white", "?"))
    label = _esc(t(f"enum.risk_severity.{sev.value}"))
    return f'<span class="badge {cls}">{icon} {label}</span>'


def status_chip(cat: StatusCategory, t: Translator | None = None) -> str:
    if t is None:
        t = get_translator()
    cls = STATUS_CHIP.get(cat, "chip-todo")
    label = _esc(t(f"enum.status_category.{_status_cat_key(cat)}"))
    return f'<span class="chip {cls}">{label}</span>'


# ---------------------------------------------------------------------------
# Summary cards (config-aware)
# ---------------------------------------------------------------------------

_CARD_DEFS: dict[str, tuple[str, str, str]] = {
    "total_issues": ("card.total_issues", "📋", "card-default"),
    "open_issues": ("card.open_issues", "📂", "card-blue"),
    "blocked": ("card.blocked", "🚫", ""),
    "story_points": ("card.story_points", "📊", "card-default"),
    "completed_sp": ("card.completed_sp", "✅", "card-green"),
    "critical_risks": ("card.critical_risks", "🔴", ""),
    "high_risks": ("card.high_risks", "🟠", ""),
    "overloaded": ("card.overloaded", "⚠️", ""),
    "conflicts": ("card.conflicts", "⚡", ""),
    # Kanban-specific
    "avg_cycle_time": ("card.avg_cycle_time", "⏱️", "card-default"),
    "throughput": ("card.throughput", "📈", "card-default"),
    "wip_violations": ("card.wip_violations", "🚧", ""),
    # Waterfall-specific
    "milestones_on_track": ("card.milestones_on_track", "🏁", "card-green"),
    "phase_progress": ("card.phase_progress", "📐", "card-default"),
}


def summary_cards(
    snapshot: BoardSnapshot,
    cards_cfg: SummaryCardsConfig | None = None,
    t: Translator | None = None,
    *,
    overload_points: float = 20.0,
    overload_issues: int = 8,
) -> str:
    """Render the executive summary cards row, filtered by config."""
    if t is None:
        t = get_translator()
    total_issues = len(snapshot.issues)
    open_issues = sum(1 for i in snapshot.issues if not i.is_done)
    blocked = sum(1 for i in snapshot.issues if i.is_blocked and not i.is_done)
    total_sp = sum(i.story_points for i in snapshot.issues)
    done_sp = sum(i.story_points for i in snapshot.issues if i.is_done)
    risks_critical = sum(1 for r in snapshot.risk_signals if r.severity == RiskSeverity.CRITICAL)
    risks_high = sum(1 for r in snapshot.risk_signals if r.severity == RiskSeverity.HIGH)
    overloaded = sum(
        1
        for wr in snapshot.workload_records
        if wr.story_points > overload_points or wr.issue_count > overload_issues
    )
    conflicts = len(snapshot.overlap_conflicts)

    values: dict[str, tuple[str, str]] = {
        "total_issues": (str(total_issues), "card-default"),
        "open_issues": (str(open_issues), "card-blue"),
        "blocked": (str(blocked), "card-red" if blocked > 0 else "card-default"),
        "story_points": (f"{total_sp:.0f}", "card-default"),
        "completed_sp": (f"{done_sp:.0f}", "card-green"),
        "critical_risks": (str(risks_critical), "card-red" if risks_critical else "card-default"),
        "high_risks": (str(risks_high), "card-amber" if risks_high else "card-default"),
        "overloaded": (str(overloaded), "card-amber" if overloaded else "card-default"),
        "conflicts": (str(conflicts), "card-red" if conflicts else "card-default"),
    }

    # Kanban metrics
    ki = snapshot.kanban_insights
    if ki and ki.flow_metrics:
        fm = ki.flow_metrics
        ct = f"{fm.avg_cycle_time:.1f}d" if fm.avg_cycle_time else "—"
        tp = f"{fm.throughput_per_week:.1f}/wk" if fm.throughput_per_week else "—"
        wv = fm.wip_violations
        values["avg_cycle_time"] = (ct, "card-default")
        values["throughput"] = (tp, "card-default")
        values["wip_violations"] = (str(wv), "card-red" if wv > 0 else "card-default")
    else:
        values["avg_cycle_time"] = ("—", "card-default")
        values["throughput"] = ("—", "card-default")
        values["wip_violations"] = ("0", "card-default")

    # Waterfall metrics
    wi = snapshot.waterfall_insights
    if wi:
        on_track = sum(1 for m in wi.milestones if m.status == "on_track")
        total_ms = len(wi.milestones)
        pp = wi.phase_progress
        overall_pct = f"{pp.overall_progress_pct:.0f}%" if pp else "—"
        values["milestones_on_track"] = (
            f"{on_track}/{total_ms}" if total_ms else "—",
            "card-green" if on_track == total_ms and total_ms > 0 else "card-amber",
        )
        values["phase_progress"] = (overall_pct, "card-default")
    else:
        values["milestones_on_track"] = ("—", "card-default")
        values["phase_progress"] = ("—", "card-default")

    visible = cards_cfg.visible if cards_cfg else list(_CARD_DEFS.keys())

    html_parts = ['<div class="summary-grid">']
    for card_id in visible:
        if card_id not in _CARD_DEFS:
            continue
        label_key, icon, _ = _CARD_DEFS[card_id]
        label = _esc(t(label_key))
        val, cls = values.get(card_id, ("0", "card-default"))
        html_parts.append(
            f'<div class="summary-card {cls}">'
            f'<div class="card-icon">{icon}</div>'
            f'<div class="card-value">{val}</div>'
            f'<div class="card-label">{label}</div>'
            f"</div>"
        )
    html_parts.append("</div>")
    return "\n".join(html_parts)


# ---------------------------------------------------------------------------
# Re-export all public names from submodules for backward compatibility.
# Existing code using ``from flowboard.presentation.html.components import X``
# or ``components.X`` continues to work unchanged.
# ---------------------------------------------------------------------------

from flowboard.presentation.html.components_scrum import *  # noqa: E402, F403
from flowboard.presentation.html.components_simulation import *  # noqa: E402, F403
from flowboard.presentation.html.components_tables import *  # noqa: E402, F403
from flowboard.presentation.html.components_timeline import *  # noqa: E402, F403
