from __future__ import annotations

from pathlib import Path

from project_analyzer.analyzer import PythonAnalyzer
from project_analyzer.config import AnalyzerConfig
from project_analyzer.diagram_adapter import D2DiagramAdapter
from project_analyzer.diagram_document_adapter import DiagramDocumentAdapter
from project_analyzer.graph_adapter import GraphDocumentAdapter
from project_analyzer.models import GraphFileNode, GraphMethodNode, GraphPackageNode
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


def test_python_analyzer_resolves_service_calls_via_pyright(service_wiring_project: Path) -> None:
    project = PythonAnalyzer().analyze(service_wiring_project, AnalyzerConfig())

    references = {(reference.source_method, reference.target_method) for reference in project.references}

    assert (
        "demo.routes.WebRoutes.project_graph",
        "demo.project_service.ProjectService.get_project_context",
    ) in references
    assert (
        "demo.routes.WebRoutes.project_graph",
        "demo.proposal_service.ProposalService.analyze_with_latest",
    ) in references
    assert (
        "demo.routes.WebRoutes.add_proposal",
        "demo.proposal_service.ProposalService.save",
    ) in references


def test_architecture_graph_and_diagram_adapters_share_expected_structure(sample_project: Path) -> None:
    project = PythonAnalyzer().analyze(sample_project, AnalyzerConfig())

    diagram_document = DiagramDocumentAdapter().to_document(project)
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

    assert graph.summary.package_count == 1
    assert graph.summary.file_count == 4
    assert graph.summary.method_count >= 5
    assert graph.summary.edge_count == len(graph.edges)
    assert any(getattr(node, "qualname", None) == "sample_pkg.module_b.use_imports" for node in graph.nodes)
    assert any(edge.target_id.endswith("Greeter_helper") for edge in graph.edges)
    assert all("Greeter__init__" not in edge.id or "Greeter_helper" not in edge.id for edge in graph.edges)

    assert "pkg_sample_pkg" in diagram
    assert "sample_pkg.module_b" in diagram
    assert "->" in diagram


def test_project_analysis_service_returns_all_artifacts(sample_project: Path) -> None:
    artifacts = ProjectAnalysisService().analyze_project(sample_project)

    assert artifacts.project.root == str(sample_project.resolve())
    assert artifacts.diagram.root == artifacts.project.root
    assert artifacts.graph.root == artifacts.project.root
    assert artifacts.diagram.summary.package_count == artifacts.graph.summary.package_count
def test_graph_document_adapter_preserves_exact_node_contract(sample_project: Path) -> None:
    project = PythonAnalyzer().analyze(sample_project, AnalyzerConfig())
    graph = GraphDocumentAdapter().to_document(project)

    actual_nodes = sorted(
        [
            (
                type(node).__name__,
                node.id,
                node.label,
                getattr(node, "parent_id", None),
                getattr(node, "qualname", None),
                getattr(node, "line", None),
            )
            for node in graph.nodes
        ],
        key=lambda item: item[1],
    )

    assert actual_nodes == [
        ("GraphFileNode", "file_sample_pkg", "sample_pkg", "pkg_sample_pkg", None, None),
        (
            "GraphFileNode",
            "file_sample_pkg_module_a",
            "sample_pkg.module_a",
            "pkg_sample_pkg",
            None,
            None,
        ),
        (
            "GraphFileNode",
            "file_sample_pkg_module_b",
            "sample_pkg.module_b",
            "pkg_sample_pkg",
            None,
            None,
        ),
        (
            "GraphFileNode",
            "file_sample_pkg_module_c",
            "sample_pkg.module_c",
            "pkg_sample_pkg",
            None,
            None,
        ),
        (
            "GraphMethodNode",
            "method_sample_pkg_module_a_Greeter",
            "class Greeter | L1",
            "file_sample_pkg_module_a",
            "sample_pkg.module_a.Greeter",
            1,
        ),
        (
            "GraphMethodNode",
            "method_sample_pkg_module_a_Greeter___init__",
            "Init(...) | L2",
            "file_sample_pkg_module_a",
            "sample_pkg.module_a.Greeter.__init__",
            2,
        ),
        (
            "GraphMethodNode",
            "method_sample_pkg_module_a_Greeter_helper",
            "Helper(...) | L5",
            "file_sample_pkg_module_a",
            "sample_pkg.module_a.Greeter.helper",
            5,
        ),
        (
            "GraphMethodNode",
            "method_sample_pkg_module_a_format_name",
            "Format Name(...) | L9",
            "file_sample_pkg_module_a",
            "sample_pkg.module_a.format_name",
            9,
        ),
        (
            "GraphMethodNode",
            "method_sample_pkg_module_a_module_entry",
            "Module Entry(...) | L13",
            "file_sample_pkg_module_a",
            "sample_pkg.module_a.module_entry",
            13,
        ),
        (
            "GraphMethodNode",
            "method_sample_pkg_module_b_use_imports",
            "Use Imports(...) | L4",
            "file_sample_pkg_module_b",
            "sample_pkg.module_b.use_imports",
            4,
        ),
        ("GraphPackageNode", "pkg_sample_pkg", "sample_pkg", None, None, None),
    ]

    assert sum(isinstance(node, GraphPackageNode) for node in graph.nodes) == 1
    assert sum(isinstance(node, GraphFileNode) for node in graph.nodes) == 4
    assert sum(isinstance(node, GraphMethodNode) for node in graph.nodes) == 6


def test_graph_document_adapter_preserves_exact_edge_contract(sample_project: Path) -> None:
    project = PythonAnalyzer().analyze(sample_project, AnalyzerConfig())
    graph = GraphDocumentAdapter().to_document(project)

    actual_edges = sorted(
        [(edge.id, edge.source_id, edge.target_id, edge.line) for edge in graph.edges],
        key=lambda item: item[0],
    )

    assert actual_edges == [
        (
            "method_sample_pkg_module_a_Greeter___init__:method_sample_pkg_module_a_Greeter_helper:3",
            "method_sample_pkg_module_a_Greeter___init__",
            "method_sample_pkg_module_a_Greeter_helper",
            3,
        ),
        (
            "method_sample_pkg_module_a_Greeter_helper:method_sample_pkg_module_a_format_name:6",
            "method_sample_pkg_module_a_Greeter_helper",
            "method_sample_pkg_module_a_format_name",
            6,
        ),
        (
            "method_sample_pkg_module_a_module_entry:method_sample_pkg_module_a_Greeter:14",
            "method_sample_pkg_module_a_module_entry",
            "method_sample_pkg_module_a_Greeter",
            14,
        ),
        (
            "method_sample_pkg_module_a_module_entry:method_sample_pkg_module_a_format_name:15",
            "method_sample_pkg_module_a_module_entry",
            "method_sample_pkg_module_a_format_name",
            15,
        ),
        (
            "method_sample_pkg_module_b_use_imports:method_sample_pkg_module_a_Greeter_helper:5",
            "method_sample_pkg_module_b_use_imports",
            "method_sample_pkg_module_a_Greeter_helper",
            5,
        ),
        (
            "method_sample_pkg_module_b_use_imports:method_sample_pkg_module_a_format_name:6",
            "method_sample_pkg_module_b_use_imports",
            "method_sample_pkg_module_a_format_name",
            6,
        ),
    ]


def test_presentation_helpers_humanize_identifiers() -> None:
    assert node_id("pkg", "sample.pkg-name") == "pkg_sample_pkg_name"
    assert display_name("visit_ImportFrom") == "visit Import From"
    assert display_name("__AnalyzerConfig") == "Analyzer Config"
