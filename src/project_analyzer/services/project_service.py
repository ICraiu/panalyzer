from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .project_analysis import AnalysisArtifacts, ProjectAnalysisService
from .project_registry import ProjectRegistry, RegisteredProject


@dataclass(frozen=True)
class ProjectContext:
    registration: RegisteredProject
    analysis: AnalysisArtifacts


class ProjectService:
    """Application service for project-facing operations used by controllers."""

    def __init__(
        self,
        registry: ProjectRegistry,
        analysis_service: ProjectAnalysisService | None = None,
    ):
        self.registry = registry
        self.analysis_service = analysis_service or ProjectAnalysisService()

    def list_projects(self) -> list[RegisteredProject]:
        return self.registry.list_projects()

    def get_project(self, project_id: str) -> RegisteredProject | None:
        return self.registry.get_project(project_id)

    def add_project(self, path: str, name: str | None = None) -> RegisteredProject:
        return self.registry.add_project(path, name=name)

    def delete_project(self, project_id: str) -> bool:
        return self.registry.delete_project(project_id)

    def get_project_context(self, project_id: str) -> ProjectContext | None:
        project = self.registry.get_project(project_id)
        if project is None:
            return None
        analysis = self.analysis_service.analyze_project(Path(project.path))
        return ProjectContext(registration=project, analysis=analysis)
