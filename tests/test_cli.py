from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest
import typer

from project_analyzer import cli

def test_run_dispatches_to_subcommand_app(monkeypatch) -> None:
    called: list[str] = []
    monkeypatch.setattr(cli, "app", lambda: called.append("app"))
    monkeypatch.setattr(sys, "argv", ["panalyzer", "start"])

    cli.run()

    assert called == ["app"]


def test_restart_command_uses_runtime_restart(monkeypatch) -> None:
    outputs: list[str] = []
    monkeypatch.setattr(cli.typer, "echo", lambda value, err=False: outputs.append(value))
    monkeypatch.setattr(
        "project_analyzer.cli.WebAppRuntime.restart",
        lambda self: SimpleNamespace(running=True, host="127.0.0.1", port=7000),
    )

    cli.restart()

    assert outputs == ["Web app running on 127.0.0.1:7000"]


def test_run_prints_help(monkeypatch) -> None:
    outputs: list[str] = []
    monkeypatch.setattr(cli.typer, "echo", lambda value, err=False: outputs.append(value))
    monkeypatch.setattr(sys, "argv", ["panalyzer", "--help"])

    cli.run()

    assert outputs[0].startswith("Usage:")
    assert "panalyzer-web" not in outputs[0]
    assert "project endpoints" in outputs[0]
    assert "panalyzer restart" in outputs[0]
    assert "panalyzer <path>" not in outputs[0]
    assert "panalyzer -a" not in outputs[0]


def test_run_rejects_removed_path_analysis_args(monkeypatch) -> None:
    outputs: list[tuple[str, bool]] = []
    monkeypatch.setattr(cli.typer, "echo", lambda value, err=False: outputs.append((value, err)))
    monkeypatch.setattr(sys, "argv", ["panalyzer", "/tmp/demo"])

    with pytest.raises(typer.Exit) as exc_info:
        cli.run()

    assert exc_info.value.exit_code == 2
    assert outputs[0][1] is True
    assert "path-based analysis commands were removed" in outputs[0][0]


def test_run_without_args_prints_help_and_exits(monkeypatch) -> None:
    outputs: list[str] = []
    monkeypatch.setattr(cli.typer, "echo", lambda value, err=False: outputs.append(value))
    monkeypatch.setattr(sys, "argv", ["panalyzer"])

    with pytest.raises(typer.Exit) as exc_info:
        cli.run()

    assert exc_info.value.exit_code == 0
    assert outputs[0].startswith("Usage:")
