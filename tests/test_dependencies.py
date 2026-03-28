"""Tests for dependency and blocker analysis."""

from __future__ import annotations

from flowboard.domain.dependencies import (
    build_dependency_chains,
    find_blocked_issues,
    find_blocking_issues,
)
from flowboard.domain.models import Dependency, IssueLink
from flowboard.shared.types import LinkType, StatusCategory


class TestFindBlockedIssues:
    def test_blocked_issue_found(self, make_issue) -> None:
        blocker_link = IssueLink("X-2", LinkType.IS_BLOCKED_BY, is_resolved=False)
        blocked = make_issue("X-1", links=[blocker_link], status_category=StatusCategory.TODO)
        not_blocked = make_issue("X-2", status_category=StatusCategory.IN_PROGRESS)
        done_blocked = make_issue("X-3", links=[blocker_link], status_category=StatusCategory.DONE)

        result = find_blocked_issues([blocked, not_blocked, done_blocked])

        assert len(result) == 1
        assert result[0].key == "X-1"


class TestFindBlockingIssues:
    def test_identifies_blocker(self, make_issue) -> None:
        link = IssueLink("X-2", LinkType.IS_BLOCKED_BY, is_resolved=False)
        blocked = make_issue("X-1", links=[link], status_category=StatusCategory.TODO)
        blocker = make_issue("X-2", status_category=StatusCategory.IN_PROGRESS)

        result = find_blocking_issues([blocked, blocker])

        assert len(result) == 1
        assert result[0].key == "X-2"


class TestDependencyChains:
    def test_chain_detected(self) -> None:
        deps = [
            Dependency("A", "B", LinkType.BLOCKS, target_status=StatusCategory.TODO),
            Dependency("B", "C", LinkType.BLOCKS, target_status=StatusCategory.TODO),
        ]
        chains = build_dependency_chains(deps)
        assert len(chains) >= 1
        longest = max(chains, key=len)
        assert len(longest) >= 2

    def test_resolved_deps_excluded(self) -> None:
        deps = [
            Dependency("A", "B", LinkType.BLOCKS, target_status=StatusCategory.DONE),
        ]
        chains = build_dependency_chains(deps)
        assert chains == []
