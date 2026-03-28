"""Methodology presets — default configuration per project methodology.

Each preset defines which tabs, summary cards, charts, and thresholds
are most relevant for a given methodology. User configuration always
overrides preset defaults.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Preset definitions
# ---------------------------------------------------------------------------

_SCRUM_PRESET: dict[str, Any] = {
    "dashboard": {
        "tabs": {
            "visible": [
                "overview",
                "workload",
                "sprints",
                "timeline",
                "pi",
                "insights",
                "issues",
            ],
            "order": [
                "overview",
                "workload",
                "sprints",
                "timeline",
                "pi",
                "insights",
                "issues",
            ],
            "default_tab": "overview",
        },
        "summary_cards": {
            "visible": [
                "total_issues",
                "open_issues",
                "blocked",
                "story_points",
                "completed_sp",
                "critical_risks",
                "high_risks",
                "overloaded",
                "conflicts",
            ],
        },
        "charts": {
            "sprint_progress": True,
        },
    },
}

_KANBAN_PRESET: dict[str, Any] = {
    "dashboard": {
        "tabs": {
            "visible": [
                "overview",
                "workload",
                "flow",
                "timeline",
                "insights",
                "issues",
            ],
            "order": [
                "overview",
                "workload",
                "flow",
                "timeline",
                "insights",
                "issues",
            ],
            "default_tab": "overview",
        },
        "summary_cards": {
            "visible": [
                "total_issues",
                "open_issues",
                "blocked",
                "avg_cycle_time",
                "throughput",
                "wip_violations",
                "critical_risks",
                "high_risks",
                "overloaded",
            ],
        },
        "charts": {
            "sprint_progress": False,
        },
    },
    "thresholds": {
        "wip_limit": 5,
    },
}

_WATERFALL_PRESET: dict[str, Any] = {
    "dashboard": {
        "tabs": {
            "visible": [
                "overview",
                "workload",
                "phases",
                "timeline",
                "insights",
                "issues",
            ],
            "order": [
                "overview",
                "workload",
                "phases",
                "timeline",
                "insights",
                "issues",
            ],
            "default_tab": "overview",
        },
        "summary_cards": {
            "visible": [
                "total_issues",
                "open_issues",
                "blocked",
                "milestones_on_track",
                "phase_progress",
                "critical_risks",
                "high_risks",
                "overloaded",
            ],
        },
        "charts": {
            "sprint_progress": False,
        },
    },
}

_HYBRID_PRESET: dict[str, Any] = {
    "dashboard": {
        "tabs": {
            "visible": [
                "overview",
                "workload",
                "sprints",
                "flow",
                "timeline",
                "pi",
                "insights",
                "issues",
            ],
            "order": [
                "overview",
                "workload",
                "sprints",
                "flow",
                "timeline",
                "pi",
                "insights",
                "issues",
            ],
            "default_tab": "overview",
        },
        "summary_cards": {
            "visible": [
                "total_issues",
                "open_issues",
                "blocked",
                "story_points",
                "completed_sp",
                "avg_cycle_time",
                "throughput",
                "critical_risks",
                "high_risks",
                "overloaded",
                "conflicts",
            ],
        },
    },
}

_CUSTOM_PRESET: dict[str, Any] = {}

_PRESETS: dict[str, dict[str, Any]] = {
    "scrum": _SCRUM_PRESET,
    "kanban": _KANBAN_PRESET,
    "waterfall": _WATERFALL_PRESET,
    "hybrid": _HYBRID_PRESET,
    "custom": _CUSTOM_PRESET,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_preset(methodology: str) -> dict[str, Any]:
    """Return the preset dict for a methodology (empty dict if unknown)."""
    return _PRESETS.get(methodology, {})


def apply_preset(raw: dict[str, Any], methodology: str) -> dict[str, Any]:
    """Merge preset defaults into raw config. User values take precedence.

    The merge is shallow-recursive: for each nested dict in the preset,
    only keys NOT already present in ``raw`` are filled in.
    """
    preset = get_preset(methodology)
    if not preset:
        return raw
    return _deep_merge_defaults(raw, preset)


def _deep_merge_defaults(user: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge *defaults* into *user*, keeping user values."""
    for key, default_val in defaults.items():
        if key not in user:
            user[key] = default_val
        elif isinstance(default_val, dict) and isinstance(user[key], dict):
            _deep_merge_defaults(user[key], default_val)
    return user


def detect_methodology(
    has_sprints: bool = False,
    has_fix_versions: bool = False,
) -> str:
    """Heuristic: guess methodology from Jira data characteristics.

    - Has active sprints → Scrum
    - Has fix_versions but no sprints → Waterfall
    - Neither → Kanban (flow-based)
    - Both → Hybrid
    """
    if has_sprints and has_fix_versions:
        return "hybrid"
    if has_sprints:
        return "scrum"
    if has_fix_versions:
        return "waterfall"
    return "kanban"
