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
def status() -> None:
    """Report whether the panalyzer web app is running."""

    runtime = WebAppRuntime(Path.cwd())
    current = runtime.status()
    if current.running:
        typer.echo(f"running pid={current.pid} host={current.host} port={current.port}")
        return
    typer.echo(f"stopped host={current.host} port={current.port}")


def analyze_path(path: str = ".") -> None:
    """Analyze a Python project and print canonical architecture JSON."""

    root = Path(path).resolve()
    if not root.exists():
        typer.echo(f"Error: path does not exist: {root}", err=True)
        raise typer.Exit(1)
    if not root.is_dir():
        typer.echo(f"Error: not a directory: {root}", err=True)
        raise typer.Exit(1)

    artifacts = ProjectAnalysisService().analyze_project(root)
    typer.echo(artifacts.architecture.model_dump_json(indent=2))


def run() -> None:
    """Console entrypoint for the installed command."""

    args = sys.argv[1:]
    if not args:
        analyze_path(".")
        return

    first = args[0]
    if first in {"start", "stop", "status"}:
        app()
        return

    if first in {"--help", "-h", "help"}:
        typer.echo(_help_text())
        return

    if len(args) > 1:
        typer.echo("Error: expected either a single path or a subcommand.", err=True)
        raise typer.Exit(2)
    analyze_path(first)


def _help_text() -> str:
    return """Usage:
  panalyzer
  panalyzer <path>
  panalyzer start
  panalyzer stop
  panalyzer status
  panalyzer-web --config ./app.yaml

Commands:
  start   Start the panalyzer web app.
  stop    Stop the panalyzer web app.
  status  Report whether the panalyzer web app is running.
"""


if __name__ == "__main__":
    run()
