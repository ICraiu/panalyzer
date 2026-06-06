from __future__ import annotations

from pathlib import Path
import sys

import typer

from .runtime import WebAppRuntime


app = typer.Typer(
    add_completion=False,
    help="Control the panalyzer web app.",
)


@app.command()
def start() -> None:
    """Start the panalyzer web app."""

    runtime = WebAppRuntime(Path.cwd())
    status = runtime.start()
    state = "running" if status.running else "stopped"
    typer.echo(f"Web app {state} on {status.host}:{status.port}")


@app.command()
def stop() -> None:
    """Stop the panalyzer web app."""

    runtime = WebAppRuntime(Path.cwd())
    status = runtime.stop()
    typer.echo(f"Web app stopped. Last known port: {status.port}")


@app.command()
def restart() -> None:
    """Restart the panalyzer web app, or start it if stopped."""

    runtime = WebAppRuntime(Path.cwd())
    status = runtime.restart()
    state = "running" if status.running else "stopped"
    typer.echo(f"Web app {state} on {status.host}:{status.port}")


@app.command()
def status() -> None:
    """Report whether the panalyzer web app is running."""

    runtime = WebAppRuntime(Path.cwd())
    current = runtime.status()
    if current.running:
        typer.echo(f"running pid={current.pid} host={current.host} port={current.port}")
        return
    typer.echo(f"stopped host={current.host} port={current.port}")


def run() -> None:
    """Console entrypoint for the installed command."""

    args = sys.argv[1:]
    if not args:
        typer.echo(_help_text())
        raise typer.Exit(0)

    first = args[0]
    if first in {"start", "stop", "restart", "status"}:
        app()
        return

    if first in {"--help", "-h", "help"}:
        typer.echo(_help_text())
        return

    typer.echo("Error: path-based analysis commands were removed. Start the web app and use its project endpoints instead.", err=True)
    raise typer.Exit(2)


def _help_text() -> str:
    return """Usage:
  panalyzer
  panalyzer start
  panalyzer stop
  panalyzer restart
  panalyzer status

Commands:
  start   Start the panalyzer web app.
  stop    Stop the panalyzer web app.
  restart Restart the panalyzer web app, or start it if stopped.
  status  Report whether the panalyzer web app is running.

Options:
  Use the web app project endpoints for scan and structure data.
"""


if __name__ == "__main__":
    run()
