from __future__ import annotations

from pathlib import Path
import sys

import typer

from .runtime import WebAppRuntime
from .services import ProjectAnalysisService


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


def analyze_path(path: str = ".", *, include_all: bool = False) -> None:
    """Analyze a Python project and print the selected JSON view."""

    root = Path(path).resolve()
    if not root.exists():
        typer.echo(f"Error: path does not exist: {root}", err=True)
        raise typer.Exit(1)
    if not root.is_dir():
        typer.echo(f"Error: not a directory: {root}", err=True)
        raise typer.Exit(1)

    artifacts = ProjectAnalysisService().analyze_project(root)
    document = artifacts.project if include_all else artifacts.diagram
    typer.echo(document.model_dump_json(indent=2))


def run() -> None:
    """Console entrypoint for the installed command."""

    args = sys.argv[1:]
    if not args:
        analyze_path(".")
        return

    first = args[0]
    if first in {"start", "stop", "restart", "status"}:
        app()
        return

    if first in {"--help", "-h", "help"}:
        typer.echo(_help_text())
        return

    include_all = False
    path: str | None = None
    for arg in args:
        if arg in {"-a", "--all"}:
            include_all = True
            continue
        if path is not None:
            typer.echo("Error: expected at most one path plus optional flags.", err=True)
            raise typer.Exit(2)
        path = arg

    analyze_path(path or ".", include_all=include_all)


def _help_text() -> str:
    return """Usage:
  panalyzer
  panalyzer <path>
  panalyzer -a
  panalyzer -a <path>
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
  -a, --all   Print the full scan model including methods and references.
"""


if __name__ == "__main__":
    run()
