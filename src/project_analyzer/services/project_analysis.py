from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..analyzer import PythonAnalyzer
from ..architecture_adapter import ArchitectureDocumentAdapter
from ..config import load_config
from ..graph_adapter import GraphDocumentAdapter
from ..models import ArchitectureDocument, GraphDocument, Project


@dataclass
class AnalysisArtifacts:
    project: Project
    architecture: ArchitectureDocument
    graph: GraphDocument


class ProjectAnalysisService:
    """Application use case for analyzing a project tree."""

    def analyze_project(self, project_root: Path) -> AnalysisArtifacts:
        root = project_root.resolve()
        config = load_config(root)
        project = PythonAnalyzer().analyze(root, config)
        architecture = ArchitectureDocumentAdapter().to_document(project)
        graph = GraphDocumentAdapter().to_document(project)
        return AnalysisArtifacts(project=project, architecture=architecture, graph=graph)
