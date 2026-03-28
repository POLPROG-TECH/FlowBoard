"""FlowBoard CLI — powered by Typer.

Commands:
  generate        Fetch Jira data and produce the HTML dashboard.
  validate-config Validate a configuration file.
  verify          Test Jira connectivity.
  demo            Generate a dashboard from built-in mock data.
"""

from __future__ import annotations

import importlib.resources
import json
import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from flowboard import __version__
from flowboard.i18n import get_translator, set_locale

app = typer.Typer(
    name="flowboard",
    help="FlowBoard — Jira-based delivery & workload intelligence.",
    add_completion=False,
)
console = Console()


class _JsonFormatter(logging.Formatter):
    """Produce valid JSON log lines by escaping the message."""

    def __init__(self) -> None:
        super().__init__(datefmt="%Y-%m-%dT%H:%M:%S")

    def format(self, record: logging.LogRecord) -> str:
        import json as _json

        record.message = record.getMessage()
        return _json.dumps(
            {
                "time": self.formatTime(record, self.datefmt),
                "level": record.levelname,
                "logger": record.name,
                "message": record.message,
            }
        )


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    root_logger = logging.getLogger("flowboard")
    root_logger.setLevel(level)
    if root_logger.handlers:
        for h in root_logger.handlers:
            h.setLevel(level)
        return
    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(_JsonFormatter())
    root_logger.addHandler(handler)


# ------------------------------------------------------------------
# generate
# ------------------------------------------------------------------


@app.command()
def generate(
    config: Path = typer.Option("config.json", "--config", "-c", help="Path to config file."),
    output: str | None = typer.Option(None, "--output", "-o", help="Override output path."),
    locale: str | None = typer.Option(None, "--locale", "-l", help="UI locale (en, pl)."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Fetch Jira data and generate the FlowBoard HTML dashboard."""
    _setup_logging(verbose)
    from flowboard.application.orchestrator import Orchestrator
    from flowboard.infrastructure.config.loader import load_config
    from flowboard.infrastructure.jira.client import JiraAuthError

    try:
        cfg = load_config(config)
    except FileNotFoundError:
        _t = get_translator(locale or "en")
        console.print(f"[red]{_t('error.config_not_found', path=config)}[/red]")
        raise typer.Exit(1) from None
    except Exception as exc:
        _t = get_translator(locale or "en")
        console.print(f"[red]{_t('cli.config_error', error=exc)}[/red]")
        raise typer.Exit(1) from None

    if locale:
        cfg.locale = locale
    set_locale(cfg.locale)
    t = get_translator(cfg.locale)

    if output:
        cfg.output.path = output

    try:
        orch = Orchestrator(cfg)
        path = orch.run()
        console.print(f"\n[green]✅ {t('cli.dashboard_generated', path=path)}[/green]")
    except JiraAuthError as exc:
        console.print(f"[red]❌ {t('error.auth_failed', code=exc.status_code)}[/red]")
        raise typer.Exit(1) from None
    except Exception as exc:
        console.print(f"[red]{t('cli.error', error=exc)}[/red]")
        raise typer.Exit(1) from None


# ------------------------------------------------------------------
# validate-config
# ------------------------------------------------------------------


@app.command("validate-config")
def validate_config(
    config: Path = typer.Option("config.json", "--config", "-c"),
    locale: str | None = typer.Option(None, "--locale", "-l", help="UI locale (en, pl)."),
) -> None:
    """Validate a FlowBoard config file against the schema."""
    from flowboard.infrastructure.config.loader import load_config

    try:
        cfg = load_config(config)
        if locale:
            cfg.locale = locale
        set_locale(cfg.locale)
        t = get_translator(cfg.locale)
        console.print(f"[green]✅ {t('cli.config_valid')}[/green]")
        from flowboard.application.services import CONFIG_DISPLAY_KEYS, describe_config

        info = describe_config(cfg, t)
        table = Table(title=t("cli.config_summary"))
        table.add_column(t("cli.column_key"), style="bold")
        table.add_column(t("cli.column_value"))
        for k, v in info.items():
            display_key = t(CONFIG_DISPLAY_KEYS.get(k, k))
            table.add_row(display_key, v)
        console.print(table)
    except FileNotFoundError:
        t = get_translator(locale or "en")
        console.print(f"[red]❌ {t('error.config_not_found', path=config)}[/red]")
        raise typer.Exit(1) from None
    except Exception as exc:
        t = get_translator(locale or "en")
        console.print(f"[red]❌ {t('cli.validation_failed', error=exc)}[/red]")
        raise typer.Exit(1) from None


# ------------------------------------------------------------------
# verify
# ------------------------------------------------------------------


@app.command()
def verify(
    config: Path = typer.Option("config.json", "--config", "-c"),
    locale: str | None = typer.Option(None, "--locale", "-l", help="UI locale (en, pl)."),
) -> None:
    """Verify Jira connectivity using the configured credentials."""
    from flowboard.application.services import verify_jira_connection
    from flowboard.infrastructure.config.loader import load_config
    from flowboard.infrastructure.jira.client import JiraApiError, JiraAuthError

    try:
        cfg = load_config(config)
        if locale:
            cfg.locale = locale
        set_locale(cfg.locale)
        t = get_translator(cfg.locale)
        info = verify_jira_connection(cfg)
        console.print(
            f"[green]✅ {t('cli.connected', title=info['serverTitle'], url=info['baseUrl'], version=info['version'])}[/green]"
        )
    except JiraAuthError as exc:
        t = get_translator(locale or "en")
        console.print(f"[red]❌ {t('error.auth_failed', code=exc.status_code)}[/red]")
        raise typer.Exit(1) from None
    except JiraApiError as exc:
        t = get_translator(locale or "en")
        console.print(
            f"[red]❌ {t('error.jira_api', code=exc.status_code, detail=exc.detail)}[/red]"
        )
        raise typer.Exit(1) from None
    except Exception as exc:
        t = get_translator(locale or "en")
        console.print(f"[red]❌ {t('cli.connection_failed', error=exc)}[/red]")
        raise typer.Exit(1) from None


# ------------------------------------------------------------------
# demo
# ------------------------------------------------------------------


def _locate_demo_fixture() -> Path:
    """Locate the bundled mock Jira fixture using importlib.resources first,
    then fall back to path traversal for editable installs."""
    # Try importlib.resources (works for installed packages)
    try:
        ref = (
            importlib.resources.files("flowboard")
            / ".."
            / ".."
            / ".."
            / "examples"
            / "fixtures"
            / "mock_jira_data.json"
        )
        candidate = Path(str(ref))
        if candidate.exists():
            return candidate
    except (ImportError, TypeError, OSError):
        pass
    # Fallback: traverse from source file (editable installs / dev)
    candidate = (
        Path(__file__).resolve().parents[3] / "examples" / "fixtures" / "mock_jira_data.json"
    )
    if candidate.exists():
        return candidate
    # Last resort: from CWD
    candidate = Path("examples/fixtures/mock_jira_data.json")
    if candidate.exists():
        return candidate
    _t = get_translator()
    raise FileNotFoundError(
        _t("cli.mock_data_not_found", path="examples/fixtures/mock_jira_data.json")
    )


@app.command()
def demo(
    output: str = typer.Option("output/demo_dashboard.html", "--output", "-o"),
    locale: str | None = typer.Option(None, "--locale", "-l", help="UI locale (en, pl)."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Generate a demo dashboard from built-in mock data (no Jira needed)."""
    _setup_logging(verbose)
    from flowboard.application.orchestrator import Orchestrator
    from flowboard.infrastructure.config.loader import load_config_from_dict

    effective_locale = locale or "en"
    set_locale(effective_locale)
    t = get_translator(effective_locale)

    # Load the bundled mock fixture.
    try:
        fixture_path = _locate_demo_fixture()
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from None

    with fixture_path.open(encoding="utf-8") as f:
        try:
            mock_payload = json.load(f)
        except json.JSONDecodeError as exc:
            console.print(f"[red]Corrupt demo fixture: {exc}[/red]")
            raise typer.Exit(1) from None

    demo_config = {
        "jira": {"base_url": "https://demo.atlassian.net"},
        "locale": effective_locale,
        "output": {
            "path": output,
            "title": "FlowBoard Demo Dashboard",
            "company_name": "Acme Corp",
        },
        "teams": [
            {"key": "platform", "name": "Platform", "members": ["user-1", "user-2", "user-3"]},
            {"key": "frontend", "name": "Frontend", "members": ["user-4", "user-5"]},
            {"key": "backend", "name": "Backend", "members": ["user-6", "user-7"]},
        ],
        "thresholds": {"overload_points": 15, "aging_days": 10},
        "dashboard": {
            "branding": {
                "title": "FlowBoard Demo Dashboard",
                "subtitle": "Delivery & Workload Intelligence — Demo Mode",
                "primary_color": "#fb6400",
                "company_name": "Acme Corp",
            },
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
            },
        },
        "pi": {
            "enabled": True,
            "name": "PI 2026.1",
            "start_date": "2026-03-02",
            "sprints_per_pi": 5,
            "sprint_length_days": 10,
            "working_days": [1, 2, 3, 4, 5],
        },
    }

    cfg = load_config_from_dict(demo_config)
    orch = Orchestrator(cfg)
    path = orch.run_from_payload(mock_payload)
    console.print(f"\n[green]✅ {t('cli.demo_generated', path=path)}[/green]")


# ------------------------------------------------------------------
# serve
# ------------------------------------------------------------------


@app.command()
def serve(
    config: Path = typer.Option("config.json", "--config", "-c", help="Configuration file."),
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8084, "--port", "-p"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Start the interactive web dashboard server."""
    import uvicorn

    from flowboard.web.logging import configure_root_logger
    from flowboard.web.server import create_app

    configure_root_logger(verbose)
    first_run = not config.exists()

    # Blocker #24: warn when binding to 127.0.0.1 in a container
    if host == "127.0.0.1" and Path("/.dockerenv").exists():
        console.print(
            "[yellow]⚠ Running inside a container with host=127.0.0.1. "
            "The server will not be accessible from outside. "
            "Use --host 0.0.0.0 to bind to all interfaces.[/yellow]"
        )

    console.print(f"\n[bold]FlowBoard[/bold] v{__version__} — Web Dashboard")
    if first_run:
        console.print("[yellow]No config file found — starting in demo mode.[/yellow]")
    else:
        console.print(f"Config: [cyan]{config}[/cyan]")
    console.print(f"Server: [link=http://{host}:{port}]http://{host}:{port}[/link]\n")

    web_app = create_app(config if not first_run else None, first_run=first_run)
    uvicorn.run(web_app, host=host, port=port, log_level="info" if verbose else "warning")


# ------------------------------------------------------------------
# version
# ------------------------------------------------------------------


@app.command("version")
def version() -> None:
    """Print FlowBoard version."""
    console.print(f"FlowBoard v{__version__}")


# ------------------------------------------------------------------
# health
# ------------------------------------------------------------------


@app.command()
def health(
    config: Path = typer.Option("config.json", "--config", "-c"),
    locale: str | None = typer.Option(None, "--locale", "-l", help="UI locale (en, pl)."),
) -> None:
    """Run a lightweight health check: validate config, verify schema, test connectivity."""
    from flowboard.infrastructure.config.loader import load_config
    from flowboard.infrastructure.config.validator import ConfigValidationError
    from flowboard.infrastructure.jira.client import JiraApiError, JiraAuthError

    checks: list[tuple[str, bool, str]] = []

    # Check 1: Config file exists
    if config.exists():
        checks.append(("Config file", True, str(config)))
    else:
        checks.append(("Config file", False, f"Not found: {config}"))
        _print_health(checks)
        raise typer.Exit(1) from None

    # Check 2: Config validates
    cfg = None
    try:
        cfg = load_config(config)
        checks.append(("Schema validation", True, "Passed"))
    except ConfigValidationError as exc:
        checks.append(("Schema validation", False, f"{len(exc.errors)} error(s)"))
    except Exception as exc:
        checks.append(("Schema validation", False, str(exc)))

    # Check 3: Jira connectivity
    if cfg:
        try:
            from flowboard.application.services import verify_jira_connection

            info = verify_jira_connection(cfg)
            checks.append(
                (
                    "Jira connectivity",
                    True,
                    f"{info.get('serverTitle', '?')} v{info.get('version', '?')}",
                )
            )
        except JiraAuthError as exc:
            checks.append(("Jira connectivity", False, f"Auth failed (HTTP {exc.status_code})"))
        except (JiraApiError, Exception) as exc:
            checks.append(("Jira connectivity", False, str(exc)))
    else:
        checks.append(("Jira connectivity", False, "Skipped (config invalid)"))

    # Check 4: Output directory writable
    if cfg:
        out_dir = Path(cfg.output.path).parent
        if out_dir.exists() and out_dir.is_dir():
            checks.append(("Output directory", True, str(out_dir)))
        else:
            checks.append(("Output directory", False, f"Missing: {out_dir}"))

    _print_health(checks)
    if not all(ok for _, ok, _ in checks):
        raise typer.Exit(1) from None


def _print_health(checks: list[tuple[str, bool, str]]) -> None:
    table = Table(title="FlowBoard Health Check")
    table.add_column("Check", style="bold")
    table.add_column("Status")
    table.add_column("Detail")
    for name, ok, detail in checks:
        icon = "[green]✅ Pass[/green]" if ok else "[red]❌ Fail[/red]"
        table.add_row(name, icon, detail)
    console.print(table)


# ------------------------------------------------------------------
# schedule (Improvement #2)
# ------------------------------------------------------------------


@app.command()
def schedule(
    config: Path = typer.Option("config.json", "--config", "-c", help="Path to config file."),
    interval: str = typer.Option(
        "daily", "--interval", "-i", help="Run interval: hourly, daily, or weekly."
    ),
    once: bool = typer.Option(False, "--once", help="Run once and exit (useful for cron)."),
    output: str | None = typer.Option(None, "--output", "-o", help="Override output path."),
    webhook: str | None = typer.Option(
        None, "--webhook", "-w", help="Webhook URL for notifications (Slack/Teams)."
    ),
    locale: str | None = typer.Option(None, "--locale", "-l", help="UI locale (en, pl)."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Schedule periodic dashboard generation.

    Examples:
      flowboard schedule --interval daily
      flowboard schedule --interval hourly --webhook https://hooks.slack.com/...
      flowboard schedule --once   # Run once (for external cron)
    """
    import signal
    import time as time_mod

    _setup_logging(verbose)

    if locale:
        set_locale(locale)

    intervals = {"hourly": 3600, "daily": 86400, "weekly": 604800}
    interval_secs = intervals.get(interval)
    if interval_secs is None:
        console.print(f"[yellow]⚠ Unknown interval '{interval}', defaulting to daily.[/yellow]")
        interval_secs = 86400

    def _run_once():
        from flowboard.application.orchestrator import Orchestrator
        from flowboard.infrastructure.config.loader import load_config

        cfg = load_config(config)
        if output:
            cfg.output.path = output
        orch = Orchestrator(cfg)
        path = orch.run()
        console.print(f"[green]✅ Dashboard generated:[/green] {path}")

        # Send webhook notification if configured
        if webhook:
            _send_webhook(webhook, f"FlowBoard dashboard generated: {path}")

        return path

    if once:
        _run_once()
        return

    console.print(f"[bold]FlowBoard Scheduler[/bold] — running every {interval} ({interval_secs}s)")
    console.print(f"Config: {config}")
    if webhook:
        console.print(f"Webhook: {webhook}")
    console.print("Press Ctrl+C to stop.\n")

    running = True

    def _handle_signal(signum, frame):
        nonlocal running
        running = False
        console.print("\n[yellow]Stopping scheduler...[/yellow]")

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    while running:
        try:
            _run_once()
        except Exception as exc:
            console.print(f"[red]❌ Generation failed:[/red] {exc}")
            if webhook:
                _send_webhook(webhook, f"FlowBoard generation failed: {exc}", error=True)

        next_run = time_mod.time() + interval_secs
        while running and time_mod.time() < next_run:
            time_mod.sleep(max(0, min(5, next_run - time_mod.time())))


def _send_webhook(url: str, message: str, *, error: bool = False) -> None:
    """Send a notification to a Slack/Teams webhook URL (Improvement #3)."""
    from urllib.parse import urlparse

    import requests as req_lib

    parsed = urlparse(url)
    if parsed.scheme not in ("https", "http"):
        console.print(f"[yellow]⚠ Webhook URL must use http(s), got: {parsed.scheme}[/yellow]")
        return
    # Block obviously private addresses (SSRF prevention — Blocker #3)
    hostname = parsed.hostname or ""
    if (
        hostname in ("localhost", "127.0.0.1", "0.0.0.0", "::1")
        or hostname.startswith("10.")
        or hostname.startswith("192.168.")
        or hostname.startswith("172.")
    ):
        console.print("[yellow]⚠ Webhook URL points to a private address — skipping.[/yellow]")
        return

    try:
        # Detect Slack vs Teams format
        if "hooks.slack.com" in url or "slack" in url.lower():
            payload = {
                "text": f"{'🔴' if error else '✅'} {message}",
            }
        elif "webhook.office.com" in url or "teams" in url.lower():
            payload = {
                "@type": "MessageCard",
                "summary": "FlowBoard Notification",
                "text": f"{'🔴' if error else '✅'} {message}",
            }
        else:
            payload = {"text": message, "error": error}

        resp = req_lib.post(url, json=payload, timeout=10)
        if resp.status_code < 300:
            logging.getLogger("flowboard.webhook").info("Webhook sent to %s", url[:50])
        else:
            logging.getLogger("flowboard.webhook").warning(
                "Webhook failed: HTTP %s", resp.status_code
            )
    except Exception as exc:
        logging.getLogger("flowboard.webhook").warning("Webhook error: %s", exc)


if __name__ == "__main__":
    app()
