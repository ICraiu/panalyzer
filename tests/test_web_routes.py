from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
import json

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
from project_analyzer.services.project_registry import RegisteredProject
from project_analyzer.web.app import WebAppContext
from project_analyzer.web.routes import WebRoutes
from project_analyzer.web.server import _build_handler


@dataclass
class FakeRegistry:
    projects: list[RegisteredProject]

    def list_projects(self) -> list[RegisteredProject]:
        return list(self.projects)

    def get_project(self, project_id: str) -> RegisteredProject | None:
        for project in self.projects:
            if project.id == project_id:
                return project
        return None

    def add_project(self, path: str) -> RegisteredProject:
        if not path.strip():
            raise ValueError("path is required")
        project = RegisteredProject(id="new123", name="new", path=path)
        self.projects.append(project)
        return project

    def delete_project(self, project_id: str) -> bool:
        before = len(self.projects)
        self.projects = [project for project in self.projects if project.id != project_id]
        return len(self.projects) != before


@dataclass
class FakeAnalysisService:
    graph_root: str

    def analyze_project(self, project_root: Path) -> AnalysisArtifacts:
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
            architecture=ArchitectureDocument(
                root=root,
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
                root=root,
                summary=GraphSummary(package_count=0, file_count=0, method_count=0, edge_count=0),
                nodes=[],
                edges=[],
            ),
        )


def _routes(projects: list[RegisteredProject]) -> WebRoutes:
    context = WebAppContext(
        base_dir=Path.cwd(),
        registry=FakeRegistry(projects),
        analysis_service=FakeAnalysisService(graph_root=str(Path.cwd())),
    )
    return WebRoutes(context)


def test_homepage_renders_empty_and_populated_states() -> None:
    status, _, payload = _routes([]).homepage()
    assert status == 200
    assert "No projects saved yet." in payload.decode("utf-8")

    routes = _routes([RegisteredProject(id="abc123", name="demo", path="/tmp/demo")])
    status, _, payload = routes.homepage(message="saved")
    html = payload.decode("utf-8")

    assert status == 200
    assert "demo" in html
    assert "saved" in html


def test_add_project_returns_redirect_or_error_page() -> None:
    routes = _routes([])

    status, _, _, headers = routes.add_project(b"path=%2Ftmp%2Fproject")
    assert status == 303
    assert headers["Location"] == "/projects/new123?created=1"

    status, _, payload, headers = routes.add_project(b"path=")
    assert status == 200
    assert headers == {}
    assert "path is required" in payload.decode("utf-8")


def test_delete_project_returns_redirect_or_not_found() -> None:
    routes = _routes([RegisteredProject(id="abc123", name="demo", path="/tmp/demo")])

    status, _, _, headers = routes.delete_project("abc123")
    assert status == 303
    assert headers["Location"] == "/?message=Project+deleted"

    status, _, payload, _ = routes.delete_project("missing")
    assert status == 404
    assert "Not Found" in payload.decode("utf-8")


def test_project_detail_and_graph_render_known_project() -> None:
    routes = _routes([RegisteredProject(id="abc123", name="demo", path="/tmp/demo")])

    status, _, payload = routes.project_detail("abc123", created=True)
    html = payload.decode("utf-8")
    assert status == 200
    assert 'data-graph-url="/projects/abc123/graph"' in html
    assert "panalyzer-created-project" in html
    assert 'id="graph-hovercard"' in html
    assert 'id="selection-panel"' not in html

    status, content_type, payload = routes.project_graph("abc123")
    parsed = json.loads(payload.decode("utf-8"))
    assert status == 200
    assert content_type.startswith("application/json")
    assert parsed["graph"]["root"] == "/tmp/demo"
    assert parsed["diagram"]["root"] == "/tmp/demo"


def test_static_asset_serving_blocks_path_escape() -> None:
    routes = _routes([])

    status, content_type, payload, headers = routes.static_asset("graph.js")
    assert status == 200
    assert content_type.startswith("text/javascript")
    assert headers["Cache-Control"] == "no-store, max-age=0"
    graph_js = payload.decode("utf-8")
    assert 'selector: "node:selected, node.is-hovered"' in graph_js
    assert 'selector: "edge:selected, edge.is-hovered"' in graph_js
    assert 'cy.on("mouseover", "node, edge"' in graph_js
    assert 'cy.on("mouseout", "node, edge"' in graph_js
    assert 'cy.on("mousemove", "edge"' in graph_js
    assert "Referenced Methods" in graph_js
    assert "referenced_methods" in graph_js
    assert 'const hovercard = document.getElementById("graph-hovercard");' in graph_js
    assert "showHovercard(event.renderedPosition || event.position, describeEdge(event.target.data()))" in graph_js
    assert "hideHovercard();" in graph_js
    assert "file: buildFileGraphState(payload.diagram)" in graph_js
    assert "method: methodState" in graph_js
    assert "collectDescendantNodeIds(" in graph_js
    assert "!subtreeNodeIds.has(edge.data.source) || !subtreeNodeIds.has(edge.data.target)" in graph_js
    assert '(focusType === "file" && state.summary.mode === "method")' in graph_js
    assert "const aggregatedEdges = diagram.transitions.map((transition) => {" in graph_js
    assert "const sourceFileId = methodToFile.get(edge.source_id);" not in graph_js
    assert '"text-max-width": 220' in graph_js
    assert "width: 240" in graph_js
    assert "height: 52" in graph_js

    status, _, payload = routes.not_found()
    assert status == 404
    assert "The requested page does not exist." in payload.decode("utf-8")

    not_found = routes.static_asset("../README.md")
    assert not_found[0] == 404


def test_http_handler_dispatches_get_and_post_routes() -> None:
    routes = SimpleNamespace(
        homepage=lambda message=None: (200, "text/html; charset=utf-8", b"home"),
        project_graph=lambda project_id: (200, "application/json; charset=utf-8", b"graph"),
        project_detail=lambda project_id, created=False: (200, "text/html; charset=utf-8", b"detail"),
        static_asset=lambda asset_name: (200, "text/javascript; charset=utf-8", b"js", {}),
        not_found=lambda: (404, "text/html; charset=utf-8", b"missing"),
        add_project=lambda body: (303, "text/plain; charset=utf-8", b"", {"Location": "/projects/demo"}),
        delete_project=lambda project_id: (303, "text/plain; charset=utf-8", b"", {"Location": "/"}),
    )
    handler_class = _build_handler(routes)

    sent: list[tuple] = []
    fake_get = SimpleNamespace(path="/projects/demo/graph", _send=lambda *args, **kwargs: sent.append(args))
    handler_class.do_GET(fake_get)
    assert sent[0][0] == 200

    fake_post = SimpleNamespace(
        path="/projects",
        headers={"Content-Length": "9"},
        rfile=SimpleNamespace(read=lambda length: b"path=/tmp"),
        _send=lambda *args, **kwargs: sent.append(args),
    )
    handler_class.do_POST(fake_post)
    assert sent[1][0] == 303
