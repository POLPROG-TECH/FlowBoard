"""JSON export for FlowBoard snapshots."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, datetime
from typing import Any

from flowboard.domain.models import BoardSnapshot


class _Encoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        if hasattr(o, "__dataclass_fields__"):
            return asdict(o)
        return super().default(o)


def export_json(snapshot: BoardSnapshot, *, indent: int = 2) -> str:
    """Serialize a BoardSnapshot to a JSON string."""
    data = {
        "generated_at": snapshot.generated_at.isoformat(),
        "title": snapshot.title,
        "projects": snapshot.projects,
        "summary": {
            "total_issues": len(snapshot.issues),
            "total_people": len(snapshot.people),
            "total_teams": len(snapshot.teams),
            "total_sprints": len(snapshot.sprints),
            "total_roadmap_items": len(snapshot.roadmap_items),
            "risk_signal_count": len(snapshot.risk_signals),
            "overlap_conflict_count": len(snapshot.overlap_conflicts),
        },
        "risk_signals": [asdict(r) for r in snapshot.risk_signals],
        "overlap_conflicts": [asdict(c) for c in snapshot.overlap_conflicts],
        "workload_records": [
            {
                "person": wr.person.display_name,
                "team": wr.team,
                "issue_count": wr.issue_count,
                "story_points": wr.story_points,
                "in_progress": wr.in_progress_count,
                "blocked": wr.blocked_count,
            }
            for wr in snapshot.workload_records
        ],
        "sprint_health": [
            {
                "sprint": sh.sprint.name,
                "total_issues": sh.total_issues,
                "done": sh.done_issues,
                "completion_pct": round(sh.completion_pct, 1),
                "points_completion_pct": round(sh.points_completion_pct, 1),
                "blocked": sh.blocked_issues,
                "aging": sh.aging_issues,
            }
            for sh in snapshot.sprint_health
        ],
        "roadmap_items": [
            {
                "key": ri.key,
                "title": ri.title,
                "team": ri.team,
                "progress_pct": round(ri.progress_pct, 1),
                "child_count": ri.child_count,
                "done_count": ri.done_count,
            }
            for ri in snapshot.roadmap_items
        ],
    }
    return json.dumps(data, cls=_Encoder, indent=indent)
