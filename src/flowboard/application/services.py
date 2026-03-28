"""Thin service helpers used by the CLI and orchestrator."""

from __future__ import annotations

from flowboard.i18n.translator import Translator, get_translator
from flowboard.infrastructure.config.loader import FlowBoardConfig
from flowboard.infrastructure.jira.client import JiraClient
from flowboard.shared.utils import mask_secret


def verify_jira_connection(config: FlowBoardConfig) -> dict[str, str]:
    """Verify connectivity to Jira and return basic server info.

    Returns a dict with ``baseUrl``, ``version``, and ``serverTitle`` on success.
    Raises on failure with a user-friendly message.
    """
    with JiraClient(config.jira) as client:
        info = client.verify_connection()
    return {
        "baseUrl": info.get("baseUrl", config.jira.base_url),
        "version": info.get("version", "unknown"),
        "serverTitle": info.get("serverTitle", "Jira"),
    }


def describe_config(config: FlowBoardConfig, t: Translator | None = None) -> dict[str, str]:
    """Return a safe, human-readable summary of the loaded config.

    Keys are stable internal identifiers; values are translated display text.
    """
    if t is None:
        t = get_translator(config.locale)
    return {
        "jira_url": config.jira.base_url or t("config.not_set"),
        "auth_email": config.jira.auth_email or t("config.not_set"),
        "auth_token": mask_secret(config.jira.auth_token) if config.jira.auth_token else t("config.not_set"),
        "projects": ", ".join(config.jira.projects) or t("config.all"),
        "boards": ", ".join(str(b) for b in config.jira.boards) or t("config.auto_detect"),
        "teams": str(len(config.teams)),
        "output": config.output.path,
    }


# Mapping of internal config keys to translation keys for display.
CONFIG_DISPLAY_KEYS = {
    "jira_url": "config.jira_url",
    "auth_email": "config.auth_email",
    "auth_token": "config.auth_token",
    "projects": "config.projects",
    "boards": "config.boards",
    "teams": "config.teams",
    "output": "config.output",
}
