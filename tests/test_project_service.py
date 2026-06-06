from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from project_analyzer.models import DiagramDocument, DiagramSummary, GraphDocument, GraphSummary, Project
from project_analyzer.services.project_analysis import AnalysisArtifacts
from project_analyzer.services.project_registry import RegisteredProject
from project_analyzer.services.project_service import ProjectService


@dataclass
class FakeRegistry:
    project: RegisteredProject | None
    deleted: bool = False

    def list_projects(self) -> list[RegisteredProject]:
        return [self.project] if self.project is not None else []

    def get_project(self, project_id: str) -> RegisteredProject | None:
        if self.project is None or self.project.id != project_id:
            return None
        return self.project

    def add_project(self, path: str, name: str | None = None) -> RegisteredProject:
        self.project = RegisteredProject(id="demo123", name=name or "demo", path=path)
        return self.project

    def delete_project(self, project_id: str) -> bool:
        if self.project is None or self.project.id != project_id:
            return False
        self.project = None
        self.deleted = True
        return True


@dataclass
class FakeAnalysisService:
    calls: int = 0

    def analyze_project(self, project_root: Path, *, refresh: bool = False) -> AnalysisArtifacts:
        self.calls += 1
        root = str(project_root)
        return AnalysisArtifacts(
            project=Project(root=root, packages=[], references=[]),
            diagram=DiagramDocument(
                root=root,
                summary=DiagramSummary(package_count=0, file_count=0, transition_count=0),
                packages=[],
                files=[],
                transitions=[],
            ),
            graph=GraphDocument(
                root=root,
                summary=GraphSummary(package_count=0, file_count=0, method_count=0, edge_count=0),
                nodes=[],
                edges=[],
            ),
        )


def test_project_service_reanalyzes_on_each_request() -> None:
    registry = FakeRegistry(RegisteredProject(id="demo123", name="demo", path="/tmp/demo"))
    analysis_service = FakeAnalysisService()
    service = ProjectService(registry=registry, analysis_service=analysis_service)

    first = service.get_project_structure("demo123")
    second = service.get_project_context("demo123")
    refreshed = service.get_project_structure("demo123", refresh=True)

    assert first is not None
    assert second is not None
    assert refreshed is not None
    assert analysis_service.calls == 3
    assert first is not second
    assert refreshed is not first


def test_project_service_invalidates_cached_analysis_after_delete() -> None:
    registry = FakeRegistry(RegisteredProject(id="demo123", name="demo", path="/tmp/demo"))
    analysis_service = FakeAnalysisService()
    service = ProjectService(registry=registry, analysis_service=analysis_service)

    context = service.get_project_context("demo123")
    deleted = service.delete_project("demo123")
    missing = service.get_project_context("demo123")

    assert context is not None
    assert analysis_service.calls == 1
    assert deleted is True
    assert registry.deleted is True
    assert missing is None
