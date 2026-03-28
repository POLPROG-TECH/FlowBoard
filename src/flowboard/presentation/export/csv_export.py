"""CSV export for selected FlowBoard data tables."""

from __future__ import annotations

import csv
import io

from flowboard.domain.models import BoardSnapshot
from flowboard.i18n.translator import Translator, get_translator

_CSV_INJECTION_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _safe_csv_value(value: object) -> str:
    """Neutralise CSV formula injection for values opened in spreadsheets.

    Numeric strings starting with '-' or '+' are left unchanged since they
    represent legitimate negative/positive numbers. Only non-numeric strings
    with injection-risk prefixes are escaped.
    """
    s = str(value) if value is not None else ""
    if not s:
        return s
    if s[0] in _CSV_INJECTION_PREFIXES:
        # Allow plain numeric values (e.g. "-3", "-3.14", "+5")
        try:
            float(s)
            return s
        except ValueError:
            return "'" + s
    return s


def export_workload_csv(snapshot: BoardSnapshot, t: Translator | None = None) -> str:
    """Export workload records as CSV."""
    if t is None:
        t = get_translator()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        t("csv.person"), t("csv.team"), t("csv.issues"),
        t("csv.story_points"), t("csv.in_progress"), t("csv.blocked"),
    ])
    for wr in snapshot.workload_records:
        writer.writerow([
            _safe_csv_value(wr.person.display_name),
            _safe_csv_value(wr.team or ""),
            wr.issue_count,
            wr.story_points,
            wr.in_progress_count,
            wr.blocked_count,
        ])
    return buf.getvalue()


def export_issues_csv(snapshot: BoardSnapshot, t: Translator | None = None) -> str:
    """Export all issues as CSV."""
    if t is None:
        t = get_translator()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        t("csv.key"), t("csv.summary"), t("csv.type"), t("csv.status"),
        t("csv.assignee"), t("csv.story_points"), t("csv.priority"),
        t("csv.epic"), t("csv.sprint"), t("csv.created"), t("csv.due_date"),
    ])
    for issue in snapshot.issues:
        writer.writerow([
            _safe_csv_value(issue.key),
            _safe_csv_value(issue.summary),
            _safe_csv_value(issue.issue_type),
            _safe_csv_value(issue.status),
            _safe_csv_value(issue.assignee.display_name) if issue.assignee else "",
            issue.story_points,
            _safe_csv_value(issue.priority),
            _safe_csv_value(issue.epic_key),
            _safe_csv_value(issue.sprint.name) if issue.sprint else "",
            issue.created.date().isoformat() if issue.created else "",
            issue.due_date.isoformat() if issue.due_date else "",
        ])
    return buf.getvalue()


def export_risks_csv(snapshot: BoardSnapshot, t: Translator | None = None) -> str:
    """Export risk signals as CSV."""
    if t is None:
        t = get_translator()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        t("csv.severity"), t("csv.category"), t("csv.title"),
        t("csv.description"), t("csv.recommendation"),
    ])
    for rs in snapshot.risk_signals:
        writer.writerow([
            _safe_csv_value(rs.severity),
            _safe_csv_value(rs.category),
            _safe_csv_value(rs.title),
            _safe_csv_value(rs.description),
            _safe_csv_value(rs.recommendation),
        ])
    return buf.getvalue()
