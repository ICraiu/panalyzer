from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..analyzer import PythonAnalyzer
from ..architecture_adapter import ArchitectureDocumentAdapter
from ..config import load_config
from ..diagram_document_adapter import DiagramDocumentAdapter
from ..graph_adapter import GraphDocumentAdapter
from ..models import ArchitectureDocument, DiagramDocument, GraphDocument, Project


@dataclass
class AnalysisArtifacts:
    project: Project
    diagram: DiagramDocument
    architecture: ArchitectureDocument
    graph: GraphDocument


class ProjectAnalysisService:
    """Application use case for analyzing a project tree."""

    def analyze_project(self, project_root: Path) -> AnalysisArtifacts:
        root = project_root.resolve()
        config = load_config(root)
        project = PythonAnalyzer().analyze(root, config)
        diagram = DiagramDocumentAdapter().to_document(project)
        architecture = ArchitectureDocumentAdapter().to_document(project)
        graph = GraphDocumentAdapter().to_document(project)
        return AnalysisArtifacts(
            project=project,
            diagram=diagram,
            architecture=architecture,
            graph=graph,
        )
