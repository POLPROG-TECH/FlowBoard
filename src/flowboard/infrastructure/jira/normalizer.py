"""Normalize raw Jira JSON into FlowBoard domain objects.

This module is the single translation boundary between the Jira API shape
and our internal domain model.  No other module should parse Jira JSON.
"""

from __future__ import annotations

import logging
from typing import Any

from flowboard.domain.models import (
    Dependency,
    Issue,
    IssueLink,
    Person,
    RoadmapItem,
    Sprint,
    Team,
)
from flowboard.infrastructure.config.loader import FlowBoardConfig
from flowboard.shared.types import (
    DEFAULT_STATUS_CATEGORY_MAP,
    IssueStatus,
    IssueType,
    LinkType,
    Priority,
    SprintState,
    StatusCategory,
)
from flowboard.shared.utils import parse_date, parse_datetime

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mapping helpers
# ---------------------------------------------------------------------------

_ISSUE_TYPE_MAP: dict[str, IssueType] = {
    "epic": IssueType.EPIC,
    "story": IssueType.STORY,
    "task": IssueType.TASK,
    "bug": IssueType.BUG,
    "sub-task": IssueType.SUB_TASK,
    "subtask": IssueType.SUB_TASK,
}

_PRIORITY_MAP: dict[str, Priority] = {
    "highest": Priority.HIGHEST,
    "high": Priority.HIGH,
    "medium": Priority.MEDIUM,
    "low": Priority.LOW,
    "lowest": Priority.LOWEST,
}

_LINK_TYPE_MAP: dict[str, LinkType] = {
    "blocks": LinkType.BLOCKS,
    "is blocked by": LinkType.IS_BLOCKED_BY,
    "depends on": LinkType.DEPENDS_ON,
    "is depended on by": LinkType.IS_DEPENDED_ON_BY,
    "relates to": LinkType.RELATES_TO,
    "clones": LinkType.CLONES,
    "is cloned by": LinkType.IS_CLONED_BY,
}


class JiraNormalizer:
    """Converts raw Jira API payloads into domain objects."""

    def __init__(self, config: FlowBoardConfig) -> None:
        self._cfg = config
        custom_statuses: dict[str, StatusCategory] = {}
        for k, v in config.status_mapping.items():
            try:
                custom_statuses[k] = StatusCategory(v)
            except ValueError:
                logger.warning(
                    "Invalid status_mapping value '%s' for '%s' — expected one of: %s. Skipping.",
                    v,
                    k,
                    ", ".join(sc.value for sc in StatusCategory),
                )
        self._status_map: dict[str, StatusCategory] = {
            **DEFAULT_STATUS_CATEGORY_MAP,
            **custom_statuses,
        }
        self._person_cache: dict[str, Person] = {}
        self._team_lookup = self._build_team_lookup()

    def _build_team_lookup(self) -> dict[str, str]:
        """Map member identifiers to team keys."""
        lookup: dict[str, str] = {}
        for td in self._cfg.teams:
            for m in td.members:
                lookup[m] = td.key
        return lookup

    # ------------------------------------------------------------------
    # People
    # ------------------------------------------------------------------

    def normalize_person(self, raw: dict[str, Any] | None) -> Person | None:
        if not raw:
            return None
        aid = raw.get("accountId", raw.get("key", ""))
        if aid and aid in self._person_cache:
            return self._person_cache[aid]
        name = raw.get("displayName", "Unknown")
        email = raw.get("emailAddress", "")
        avatar = (
            raw.get("avatarUrls", {}).get("48x48", "")
            if isinstance(raw.get("avatarUrls"), dict)
            else ""
        )
        team = self._team_lookup.get(aid, self._team_lookup.get(name, ""))
        person = Person(
            account_id=aid, display_name=name, email=email, team=team, avatar_url=avatar
        )
        if aid:
            self._person_cache[aid] = person
        return person

    # ------------------------------------------------------------------
    # Sprints
    # ------------------------------------------------------------------

    def normalize_sprint(self, raw: dict[str, Any]) -> Sprint:
        sprint_id = raw.get("id")
        if sprint_id is None:
            raise ValueError(f"Sprint data missing 'id' field: {raw!r:.200}")
        state_str = raw.get("state", "future").lower()
        try:
            state = SprintState(state_str)
        except ValueError:
            state = SprintState.FUTURE
        return Sprint(
            id=sprint_id,
            name=raw.get("name", ""),
            board_id=raw.get("originBoardId", 0),
            state=state,
            start_date=parse_date(raw.get("startDate")),
            end_date=parse_date(raw.get("endDate")),
            goal=raw.get("goal", ""),
        )

    def normalize_sprints(self, raw_sprints: list[dict[str, Any]]) -> list[Sprint]:
        result: list[Sprint] = []
        for s in raw_sprints:
            try:
                result.append(self.normalize_sprint(s))
            except (ValueError, TypeError, KeyError) as exc:
                logger.warning("Skipping malformed sprint data: %s", exc)
        return result

    # ------------------------------------------------------------------
    # Issues
    # ------------------------------------------------------------------

    def _resolve_issue_type(self, raw_type: str) -> IssueType:
        if not raw_type:
            return IssueType.OTHER
        return _ISSUE_TYPE_MAP.get(raw_type.lower(), IssueType.OTHER)

    def _resolve_status(self, raw_status: str) -> tuple[IssueStatus, StatusCategory]:
        cat = self._status_map.get(raw_status, StatusCategory.TODO)
        try:
            status = IssueStatus(raw_status)
        except ValueError:
            status = IssueStatus.OTHER
        return status, cat

    def _resolve_priority(self, raw: str | None) -> Priority:
        if not raw:
            return Priority.UNSET
        return _PRIORITY_MAP.get(raw.lower(), Priority.MEDIUM)

    def _extract_sprint(self, fields: dict[str, Any]) -> Sprint | None:
        sprint_field = self._cfg.field_mappings.sprint
        sprint_data = fields.get(sprint_field)
        if isinstance(sprint_data, list) and sprint_data:
            sprint_data = sprint_data[-1]  # most recent sprint
        if isinstance(sprint_data, dict) and "id" in sprint_data:
            return self.normalize_sprint(sprint_data)
        if sprint_data is not None and not isinstance(sprint_data, (dict, list)):
            logger.warning(
                "Unexpected sprint field format (type=%s) for field '%s'. "
                "Expected dict or list. Jira Server GreenHopper may return a string. "
                "Sprint data will be missing for this issue.",
                type(sprint_data).__name__,
                sprint_field,
            )
        return None

    def _extract_links(self, raw_links: list[dict[str, Any]]) -> list[IssueLink]:
        links: list[IssueLink] = []
        for rl in raw_links:
            lt_raw = rl.get("type", {})
            if "inwardIssue" in rl:
                direction_name = lt_raw.get("inward", "relates to")
                target = rl["inwardIssue"]
            elif "outwardIssue" in rl:
                direction_name = lt_raw.get("outward", "relates to")
                target = rl["outwardIssue"]
            else:
                continue
            link_type = _LINK_TYPE_MAP.get(direction_name.lower(), LinkType.RELATES_TO)
            target_status = target.get("fields", {}).get("status", {}).get("name", "")
            is_resolved = self._status_map.get(target_status) == StatusCategory.DONE
            links.append(
                IssueLink(
                    target_key=target.get("key", ""),
                    link_type=link_type,
                    is_resolved=is_resolved,
                    target_summary=target.get("fields", {}).get("summary", ""),
                    target_status=target_status,
                )
            )
        return links

    def normalize_issue(self, raw: dict[str, Any]) -> Issue:
        fields = raw.get("fields", {})
        raw_issuetype = fields.get("issuetype")
        raw_type = (
            raw_issuetype.get("name", "Other") if isinstance(raw_issuetype, dict) else "Other"
        )
        raw_status_obj = fields.get("status")
        raw_status = (
            raw_status_obj.get("name", "Other") if isinstance(raw_status_obj, dict) else "Other"
        )
        status, status_cat = self._resolve_status(raw_status)

        sp_field = self._cfg.field_mappings.story_points
        sp_raw = fields.get(sp_field) or fields.get("story_points") or 0.0
        try:
            story_points = float(sp_raw) if sp_raw else 0.0
            if sp_raw and not isinstance(sp_raw, (int, float)):
                logger.debug(
                    "Story points coerced from %s to %.1f",
                    type(sp_raw).__name__,
                    story_points,
                )
        except (ValueError, TypeError):
            logger.warning("Invalid story_points value %r, defaulting to 0", sp_raw)
            story_points = 0.0

        epic_field = self._cfg.field_mappings.epic_link
        epic_src = (
            fields.get(epic_field)
            or (
                fields.get("epic", {}).get("key", "")
                if isinstance(fields.get("epic"), dict)
                else ""
            )
            or ""
        )
        if isinstance(epic_src, dict):
            epic_key = epic_src.get("key", "")
            logger.debug("Epic resolved from dict field '%s'", epic_field)
        elif isinstance(epic_src, list):
            first = epic_src[0] if epic_src else ""
            epic_key = (
                first.get("key", "") if isinstance(first, dict) else str(first) if first else ""
            )
            logger.debug("Epic resolved from list field '%s' (len=%d)", epic_field, len(epic_src))
        elif isinstance(epic_src, str):
            epic_key = epic_src
        else:
            epic_key = str(epic_src) if epic_src else ""
            if epic_src:
                logger.debug("Epic coerced from %s via str() fallback", type(epic_src).__name__)

        project_obj = fields.get("project")
        project_key = project_obj.get("key", "") if isinstance(project_obj, dict) else ""

        return Issue(
            key=raw.get("key", ""),
            summary=fields.get("summary", ""),
            issue_type=self._resolve_issue_type(raw_type),
            status=status,
            status_category=status_cat,
            assignee=self.normalize_person(fields.get("assignee")),
            reporter=self.normalize_person(fields.get("reporter")),
            story_points=story_points,
            priority=self._resolve_priority(
                fields.get("priority", {}).get("name")
                if isinstance(fields.get("priority"), dict)
                else None
            ),
            epic_key=str(epic_key),
            sprint=self._extract_sprint(fields),
            labels=fields.get("labels") or [],
            components=[
                c.get("name", "") for c in (fields.get("components") or []) if isinstance(c, dict)
            ],
            fix_versions=[
                v.get("name", "") for v in (fields.get("fixVersions") or []) if isinstance(v, dict)
            ],
            created=parse_datetime(fields.get("created")),
            updated=parse_datetime(fields.get("updated")),
            resolved=parse_datetime(fields.get("resolutiondate")),
            due_date=parse_date(fields.get("duedate")),
            parent_key=(
                fields["parent"].get("key", "") if isinstance(fields.get("parent"), dict) else ""
            ),
            project_key=project_key,
            links=self._extract_links(fields.get("issuelinks") or []),
        )

    def normalize_issues(self, raw_issues: list[dict[str, Any]]) -> list[Issue]:
        results: list[Issue] = []
        for r in raw_issues:
            try:
                results.append(self.normalize_issue(r))
            except (KeyError, TypeError, ValueError, AttributeError) as exc:
                key = r.get("key", "<unknown>")
                logger.warning("Skipping malformed issue %s: %s", key, exc)
        return results

    # ------------------------------------------------------------------
    # Dependencies (extracted from issue links)
    # ------------------------------------------------------------------

    def extract_dependencies(self, issues: list[Issue]) -> list[Dependency]:
        deps: list[Dependency] = []
        issue_map = {i.key: i for i in issues}
        for issue in issues:
            for link in issue.links:
                if link.link_type in (
                    LinkType.BLOCKS,
                    LinkType.IS_BLOCKED_BY,
                    LinkType.DEPENDS_ON,
                    LinkType.IS_DEPENDED_ON_BY,
                ):
                    target = issue_map.get(link.target_key)
                    deps.append(
                        Dependency(
                            source_key=issue.key,
                            target_key=link.target_key,
                            link_type=link.link_type,
                            source_summary=issue.summary,
                            target_summary=link.target_summary,
                            source_status=issue.status_category,
                            target_status=target.status_category if target else StatusCategory.TODO,
                        )
                    )
        return deps

    # ------------------------------------------------------------------
    # Teams
    # ------------------------------------------------------------------

    def build_teams(self, issues: list[Issue]) -> list[Team]:
        configured = {
            td.key: Team(key=td.key, name=td.name, members=tuple(td.members))
            for td in self._cfg.teams
        }
        # Discover teams from issue assignees.
        discovered: dict[str, set[str]] = {}
        for issue in issues:
            if issue.assignee and issue.assignee.team:
                discovered.setdefault(issue.assignee.team, set()).add(issue.assignee.account_id)
        for key, members in discovered.items():
            if key not in configured:
                configured[key] = Team(key=key, name=key, members=tuple(members))
        return list(configured.values())

    # ------------------------------------------------------------------
    # Roadmap items (from epics)
    # ------------------------------------------------------------------

    def build_roadmap_items(self, issues: list[Issue]) -> list[RoadmapItem]:
        epics = [i for i in issues if i.issue_type == IssueType.EPIC]
        children_by_epic: dict[str, list[Issue]] = {}
        for i in issues:
            if i.epic_key:
                children_by_epic.setdefault(i.epic_key, []).append(i)
        items: list[RoadmapItem] = []
        for epic in epics:
            children = children_by_epic.get(epic.key, [])
            done = [c for c in children if c.is_done]
            total_sp = sum(c.story_points for c in children)
            done_sp = sum(c.story_points for c in done)
            progress = (len(done) / len(children) * 100) if children else 0.0
            dep_keys = [
                lnk.target_key
                for lnk in epic.links
                if lnk.link_type in (LinkType.BLOCKS, LinkType.DEPENDS_ON, LinkType.IS_BLOCKED_BY)
            ]
            items.append(
                RoadmapItem(
                    key=epic.key,
                    title=epic.summary,
                    team=epic.assignee.team if epic.assignee else "",
                    owner=epic.assignee,
                    start_date=epic.created.date() if epic.created else None,
                    target_date=epic.due_date,
                    status=epic.status_category,
                    progress_pct=progress,
                    child_count=len(children),
                    done_count=len(done),
                    total_points=total_sp,
                    completed_points=done_sp,
                    dependency_keys=dep_keys,
                )
            )
        return items

    # ------------------------------------------------------------------
    # Unique people list
    # ------------------------------------------------------------------

    def get_all_people(self) -> list[Person]:
        return list(self._person_cache.values())
