from __future__ import annotations

from pathlib import Path

from project_analyzer.analyzer import PythonAnalyzer
from project_analyzer.architecture_adapter import ArchitectureDocumentAdapter
from project_analyzer.config import AnalyzerConfig
from project_analyzer.diagram_adapter import D2DiagramAdapter
from project_analyzer.diagram_document_adapter import DiagramDocumentAdapter
from project_analyzer.graph_adapter import GraphDocumentAdapter
from project_analyzer.presentation import display_name, node_id
from project_analyzer.services.project_analysis import ProjectAnalysisService


def test_python_analyzer_builds_project_model(sample_project: Path) -> None:
    project = PythonAnalyzer().analyze(sample_project, AnalyzerConfig())

    assert project.root == str(sample_project.resolve())
    assert [package.name for package in project.packages] == ["sample_pkg"]
    file_import_paths = [source_file.import_path for source_file in project.packages[0].files]
    assert "sample_pkg.module_a" in file_import_paths
    assert "sample_pkg.module_b" in file_import_paths
    assert "sample_pkg.broken" not in file_import_paths

    method_names = {
        method.qualname
        for package in project.packages
        for source_file in package.files
        for method in source_file.methods
    }
    assert "sample_pkg.module_a.Greeter.helper" in method_names
    assert "sample_pkg.module_b.use_imports" in method_names

    references = {(reference.source_method, reference.target_method) for reference in project.references}
    assert ("sample_pkg.module_a.Greeter.__init__", "sample_pkg.module_a.Greeter.helper") in references
    assert (None, "sample_pkg.module_a.format_name") in references


def test_python_analyzer_can_include_external_references(sample_project: Path) -> None:
    project = PythonAnalyzer().analyze(
        sample_project,
        AnalyzerConfig(include_external_references=True),
    )

    external_targets = {
        reference.target_method
        for reference in project.references
        if not any(method.qualname == reference.target_method for package in project.packages for source_file in package.files for method in source_file.methods)
    }
    assert "sample_pkg.module_a.print" in external_targets
    assert "value.strip" in external_targets


def test_architecture_graph_and_diagram_adapters_share_expected_structure(sample_project: Path) -> None:
    project = PythonAnalyzer().analyze(sample_project, AnalyzerConfig())

    diagram_document = DiagramDocumentAdapter().to_document(project)
    architecture = ArchitectureDocumentAdapter().to_document(project)
    graph = GraphDocumentAdapter().to_document(project)
    diagram = D2DiagramAdapter().to_diagram(project)

    assert diagram_document.summary.package_count == 1
    assert diagram_document.summary.file_count == 4
    assert diagram_document.summary.transition_count >= 1
    assert any(file.import_path == "sample_pkg.module_b" for file in diagram_document.files)
    assert any(
        transition.target_import_path == "sample_pkg.module_a"
        for transition in diagram_document.transitions
    )
    assert any(
        "sample_pkg.module_a.Greeter.helper" in transition.referenced_methods
        for transition in diagram_document.transitions
    )

    assert architecture.summary.package_count == 1
    assert architecture.summary.file_count == 4
    assert architecture.summary.method_count >= 5
    assert any(getattr(node, "qualname", None) == "sample_pkg.module_b.use_imports" for node in architecture.nodes)
    assert any(edge.target_id.endswith("Greeter_helper") for edge in architecture.edges)
    assert all("Greeter__init__" not in edge.id or "Greeter_helper" not in edge.id for edge in architecture.edges)

    assert graph.summary.package_count == architecture.summary.package_count
    assert graph.summary.file_count == architecture.summary.file_count
    assert graph.summary.method_count == architecture.summary.method_count
    assert graph.summary.edge_count == len(graph.edges)

    assert "pkg_sample_pkg" in diagram
    assert "sample_pkg.module_b" in diagram
    assert "->" in diagram


def test_project_analysis_service_returns_all_artifacts(sample_project: Path) -> None:
    artifacts = ProjectAnalysisService().analyze_project(sample_project)

    assert artifacts.project.root == str(sample_project.resolve())
    assert artifacts.diagram.root == artifacts.project.root
    assert artifacts.architecture.root == artifacts.project.root
    assert artifacts.graph.root == artifacts.project.root
    assert artifacts.diagram.summary.package_count == artifacts.graph.summary.package_count
    assert artifacts.graph.summary.package_count == artifacts.architecture.summary.package_count


def test_presentation_helpers_humanize_identifiers() -> None:
    assert node_id("pkg", "sample.pkg-name") == "pkg_sample_pkg_name"
    assert display_name("visit_ImportFrom") == "visit Import From"
    assert display_name("__AnalyzerConfig") == "Analyzer Config"
