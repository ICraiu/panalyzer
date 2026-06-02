from __future__ import annotations

from pathlib import Path
import sys

import pytest
import typer

from project_analyzer import cli
from project_analyzer.models import (
    ArchitectureDocument,
    ArchitectureSummary,
    DiagramDocument,
    DiagramSummary,
    GraphDocument,
    GraphSummary,
    Project,
)
from project_analyzer.services.project_analysis import AnalysisArtifacts


def _sample_artifacts(root: Path) -> AnalysisArtifacts:
    return AnalysisArtifacts(
        project=Project(root=str(root), packages=[], references=[]),
        diagram=DiagramDocument(
            root=str(root),
            summary=DiagramSummary(package_count=0, file_count=0, transition_count=0),
            packages=[],
            files=[],
            transitions=[],
        ),
        architecture=ArchitectureDocument(
            root=str(root),
            summary=ArchitectureSummary(
                package_count=0,
                file_count=0,
                method_count=0,
                internal_call_count=0,
            ),
            sections=[],
            nodes=[],
            edges=[],
        ),
        graph=GraphDocument(
            root=str(root),
            summary=GraphSummary(package_count=0, file_count=0, method_count=0, edge_count=0),
            nodes=[],
            edges=[],
        ),
    )


def test_analyze_path_prints_diagram_json(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    outputs: list[str] = []

    monkeypatch.setattr(cli.typer, "echo", lambda value, err=False: outputs.append(value))
    monkeypatch.setattr(
        "project_analyzer.cli.ProjectAnalysisService.analyze_project",
        lambda self, root: _sample_artifacts(root),
    )

    cli.analyze_path(str(project_root))

    assert '"root"' in outputs[0]
    assert str(project_root.resolve()) in outputs[0]
    assert '"packages"' in outputs[0]
    assert '"files"' in outputs[0]
    assert '"transitions"' in outputs[0]
    assert '"references"' not in outputs[0]
    assert '"nodes"' not in outputs[0]


def test_analyze_path_rejects_missing_path(tmp_path: Path, monkeypatch) -> None:
    outputs: list[tuple[str, bool]] = []
    monkeypatch.setattr(cli.typer, "echo", lambda value, err=False: outputs.append((value, err)))

    with pytest.raises(typer.Exit) as exc_info:
        cli.analyze_path(str(tmp_path / "missing"))

    assert exc_info.value.exit_code == 1
    assert outputs[0][1] is True


def test_run_dispatches_to_subcommand_app(monkeypatch) -> None:
    called: list[str] = []
    monkeypatch.setattr(cli, "app", lambda: called.append("app"))
    monkeypatch.setattr(sys, "argv", ["panalyzer", "start"])

    cli.run()

    assert called == ["app"]


def test_run_prints_help(monkeypatch) -> None:
    outputs: list[str] = []
    monkeypatch.setattr(cli.typer, "echo", lambda value, err=False: outputs.append(value))
    monkeypatch.setattr(sys, "argv", ["panalyzer", "--help"])

    cli.run()

    assert outputs[0].startswith("Usage:")
    assert "panalyzer-web" not in outputs[0]


def test_run_rejects_extra_args(monkeypatch) -> None:
    outputs: list[tuple[str, bool]] = []
    monkeypatch.setattr(cli.typer, "echo", lambda value, err=False: outputs.append((value, err)))
    monkeypatch.setattr(sys, "argv", ["panalyzer", "a", "b"])

    with pytest.raises(typer.Exit) as exc_info:
        cli.run()

    assert exc_info.value.exit_code == 2
    assert outputs[0][1] is True


def test_run_defaults_to_current_directory(monkeypatch) -> None:
    called: list[str] = []
    monkeypatch.setattr(cli, "analyze_path", lambda path=".": called.append(path))
    monkeypatch.setattr(sys, "argv", ["panalyzer"])

    cli.run()

    assert called == ["."]
