"""Shared enumerations and type aliases used across FlowBoard."""

from __future__ import annotations

from enum import StrEnum


class IssueType(StrEnum):
    EPIC = "Epic"
    STORY = "Story"
    TASK = "Task"
    BUG = "Bug"
    SUB_TASK = "Sub-task"
    OTHER = "Other"


class IssueStatus(StrEnum):
    TODO = "To Do"
    IN_PROGRESS = "In Progress"
    IN_REVIEW = "In Review"
    DONE = "Done"
    BLOCKED = "Blocked"
    OTHER = "Other"


class StatusCategory(StrEnum):
    TODO = "To Do"
    IN_PROGRESS = "In Progress"
    DONE = "Done"


class Priority(StrEnum):
    HIGHEST = "Highest"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    LOWEST = "Lowest"
    UNSET = "__unset__"


class SprintState(StrEnum):
    FUTURE = "future"
    ACTIVE = "active"
    CLOSED = "closed"


class RiskSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class RiskCategory(StrEnum):
    OVERLOAD = "overload"
    BLOCKED = "blocked"
    AGING = "aging"
    SCOPE_CREEP = "scope_creep"
    DEPENDENCY_CHAIN = "dependency_chain"
    TIMELINE_CONFLICT = "timeline_conflict"
    CAPACITY = "capacity"
    CARRY_OVER = "carry_over"
    WIP_LIMIT = "wip_limit"


class LinkType(StrEnum):
    BLOCKS = "blocks"
    IS_BLOCKED_BY = "is blocked by"
    DEPENDS_ON = "depends on"
    IS_DEPENDED_ON_BY = "is depended on by"
    RELATES_TO = "relates to"
    CLONES = "clones"
    IS_CLONED_BY = "is cloned by"
    PARENT = "parent"
    CHILD = "child"


# Status category mapping: maps raw Jira status names to our categories.
DEFAULT_STATUS_CATEGORY_MAP: dict[str, StatusCategory] = {
    "To Do": StatusCategory.TODO,
    "Open": StatusCategory.TODO,
    "Backlog": StatusCategory.TODO,
    "New": StatusCategory.TODO,
    "Reopened": StatusCategory.TODO,
    "In Progress": StatusCategory.IN_PROGRESS,
    "In Development": StatusCategory.IN_PROGRESS,
    "In Review": StatusCategory.IN_PROGRESS,
    "In QA": StatusCategory.IN_PROGRESS,
    "Code Review": StatusCategory.IN_PROGRESS,
    "Testing": StatusCategory.IN_PROGRESS,
    "Blocked": StatusCategory.IN_PROGRESS,
    "Done": StatusCategory.DONE,
    "Closed": StatusCategory.DONE,
    "Resolved": StatusCategory.DONE,
    "Released": StatusCategory.DONE,
}
