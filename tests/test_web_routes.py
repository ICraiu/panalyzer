from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
import json

from project_analyzer.models import (
    DiagramDocument,
    DiagramFile,
    DiagramPackage,
    DiagramSummary,
    DiagramTransition,
    GraphDocument,
    GraphEdge,
    GraphFileNode,
    GraphMethodNode,
    GraphPackageNode,
    GraphSummary,
    IterationState,
    Project,
    ValidationIssue,
)
from project_analyzer.services import ProposalApplicationError
from project_analyzer.services.project_analysis import AnalysisArtifacts
from project_analyzer.services.project_registry import RegisteredProject
from project_analyzer.services.project_service import ProjectContext
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
            graph=GraphDocument(
                root=root,
                summary=GraphSummary(package_count=0, file_count=0, method_count=0, edge_count=0),
                nodes=[],
                edges=[],
            ),
        )


@dataclass
class FakeProposalService:
    fail: bool = False

    def analyze_with_latest(self, *, project_id: str, project_root: Path, project: Project):
        if self.fail:
            raise ProposalApplicationError(
                "invalid_latest_proposal",
                "Latest proposal is invalid.",
                errors=[
                    ValidationIssue(
                        code="invalid_latest_proposal",
                        path="proposal",
                        message="Latest proposal is invalid.",
                    )
                ],
            )
        root = str(project_root)
        return (
            GraphDocument(
                root=root,
                summary=GraphSummary(package_count=1, file_count=1, method_count=1, edge_count=1),
                nodes=[
                    GraphPackageNode(
                        id="pkg_demo",
                        label="demo",
                        path=f"{root}/src/demo",
                        iteration_state=IterationState.CHANGE,
                    ),
                    GraphFileNode(
                        id="file_demo_main",
                        label="demo.main",
                        parent_id="pkg_demo",
                        path=f"{root}/src/demo/main.py",
                        import_path="demo.main",
                        iteration_state=IterationState.ADD,
                    ),
                    GraphMethodNode(
                        id="method_demo_main_run",
                        label="Run(...) | L1",
                        parent_id="file_demo_main",
                        path=f"{root}/src/demo/main.py",
                        import_path="demo.main",
                        qualname="demo.main.run",
                        signature="def run()",
                        line=1,
                        iteration_state=IterationState.CHANGE,
                    ),
                ],
                edges=[
                    GraphEdge(
                        id="method_demo_main_run:method_demo_main_run:proposal",
                        source_id="method_demo_main_run",
                        target_id="method_demo_main_run",
                        line=0,
                        iteration_state=IterationState.REMOVE,
                    )
                ],
                active_proposal=None,
                warnings=[],
            ),
            DiagramDocument(
                root=root,
                summary=DiagramSummary(package_count=1, file_count=1, transition_count=1),
                packages=[
                    DiagramPackage(
                        id="pkg_demo",
                        name="demo",
                        path=f"{root}/src/demo",
                        iteration_state=IterationState.CHANGE,
                    )
                ],
                files=[
                    DiagramFile(
                        id="file_demo_main",
                        package_id="pkg_demo",
                        import_path="demo.main",
                        path=f"{root}/src/demo/main.py",
                        iteration_state=IterationState.ADD,
                    )
                ],
                transitions=[
                    DiagramTransition(
                        id="transition_file_demo_main_file_demo_main",
                        source_file_id="file_demo_main",
                        target_file_id="file_demo_main",
                        source_import_path="demo.main",
                        target_import_path="demo.main",
                        referenced_methods=["demo.main.run"],
                        iteration_state=IterationState.REMOVE,
                    )
                ],
            ),
        )

    def save(self, *, project_id: str, project_root: Path, project: Project, payload: dict):
        return SimpleNamespace(
            proposal=SimpleNamespace(model_dump=lambda mode="json": payload),
            validation=SimpleNamespace(
                valid=False,
                model_dump=lambda mode="json": {
                    "valid": False,
                    "warnings": [],
                    "errors": [
                        {
                            "code": "project_sha_mismatch",
                            "path": "project_sha",
                            "message": "Proposal targets another SHA.",
                        }
                    ],
                },
            ),
        )


def _routes(projects: list[RegisteredProject], *, proposal_fail: bool = False) -> WebRoutes:
    registry = FakeRegistry(projects)
    analysis_service = FakeAnalysisService(graph_root=str(Path.cwd()))

    class FakeProjectService:
        def list_projects(self):
            return registry.list_projects()

        def get_project(self, project_id: str):
            return registry.get_project(project_id)

        def add_project(self, path: str, name: str | None = None):
            return registry.add_project(path)

        def delete_project(self, project_id: str):
            return registry.delete_project(project_id)

        def get_project_context(self, project_id: str):
            project = registry.get_project(project_id)
            if project is None:
                return None
            return ProjectContext(
                registration=project,
                analysis=analysis_service.analyze_project(Path(project.path)),
            )

    context = WebAppContext(
        base_dir=Path.cwd(),
        project_service=FakeProjectService(),
        proposal_service=FakeProposalService(fail=proposal_fail),
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
    assert 'class="project-card__link" href="/projects/abc123"' in html
    assert 'data-project-href="/projects/abc123"' in html
    assert "enableProjectCardNavigation" in html
    assert 'id="page-loading"' in html
    assert "Opening project…" in html


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
    assert 'id="graph-proposal-status"' in html
    assert 'id="selection-panel"' not in html

    status, content_type, payload = routes.project_graph("abc123")
    parsed = json.loads(payload.decode("utf-8"))
    assert status == 200
    assert content_type.startswith("application/json")
    assert parsed["graph"]["root"] == "/tmp/demo"
    assert parsed["graph"]["nodes"][0]["iteration_state"] == "change"


def test_project_graph_returns_explicit_error_when_latest_proposal_cannot_apply() -> None:
    routes = _routes([RegisteredProject(id="abc123", name="demo", path="/tmp/demo")], proposal_fail=True)

    status, content_type, payload = routes.project_graph("abc123")
    parsed = json.loads(payload.decode("utf-8"))

    assert status == 409
    assert content_type.startswith("application/json")
    assert parsed["error"]["code"] == "invalid_latest_proposal"


def test_add_proposal_returns_validation_payload() -> None:
    routes = _routes([RegisteredProject(id="abc123", name="demo", path="/tmp/demo")])

    status, content_type, payload, headers = routes.add_proposal(
        "abc123",
        b'{"id":"p1","name":"demo","created_at":"2026-06-04T10:15:00Z","author":"codex","source_model":"gpt-5","rationale":"test","project_sha":"abc","packages":[],"files":[],"methods":[],"references":[]}',
    )
    parsed = json.loads(payload.decode("utf-8"))

    assert status == 202
    assert content_type.startswith("application/json")
    assert headers == {}
    assert parsed["validation"]["valid"] is False
    assert parsed["validation"]["errors"][0]["code"] == "project_sha_mismatch"


def test_static_asset_serving_blocks_path_escape() -> None:
    routes = _routes([])

    status, content_type, payload, headers = routes.static_asset("app.css")
    assert status == 200
    assert content_type.startswith("text/css")
    app_css = payload.decode("utf-8")
    assert ".project-card__link" in app_css
    assert "cursor: pointer;" in app_css
    assert ".project-card::before" not in app_css
    assert ".project-card__actions" in app_css
    assert ".project-card__actions .button--danger" in app_css
    assert "background: transparent;" in app_css
    assert ".page-loading" in app_css
    assert ".page-loading__spinner" in app_css
    assert ".graph-proposal-status" in app_css
    assert ".graph-proposal-status--error" in app_css
    assert ".graph-proposal-status__warnings" in app_css

    status, content_type, payload, headers = routes.static_asset("graph.js")
    assert status == 200
    assert content_type.startswith("text/javascript")
    assert headers["Cache-Control"] == "no-store, max-age=0"
    graph_js = payload.decode("utf-8")
    assert 'selector: "node:selected, node.is-hovered"' in graph_js
    assert 'selector: "edge:selected, edge.is-hovered"' in graph_js
    assert 'cy.on("mouseover", "node, edge"' in graph_js
    assert 'cy.on("mousemove", "node"' in graph_js
    assert 'cy.on("mouseout", "node, edge"' in graph_js
    assert 'cy.on("mousemove", "edge"' in graph_js
    assert "Referenced Methods" in graph_js
    assert "referenced_methods" in graph_js
    assert 'const hovercard = document.getElementById("graph-hovercard");' in graph_js
    assert "collectNodeConnections(cy, event.target, currentMode)" in graph_js
    assert "function describeNodeHover(data, connections)" in graph_js
    assert "highlightEdgeEndpoints(event.target);" in graph_js
    assert "clearEdgeEndpointHighlights(cy);" in graph_js
    assert "showHovercard(event.renderedPosition || event.position, describeEdge(event.target.data()))" in graph_js
    assert "hideHovercard();" in graph_js
    assert "file: buildFileGraphState(payload.graph)" in graph_js
    assert "method: methodState" in graph_js
    assert "collectDescendantNodeIds(" in graph_js
    assert "!subtreeNodeIds.has(edge.data.source) || !subtreeNodeIds.has(edge.data.target)" in graph_js
    assert '(focusType === "file" && state.summary.mode === "method")' in graph_js
    assert "const transitionsById = new Map();" in graph_js
    assert "const sourceFileId = methodToFile.get(edge.source_id);" not in graph_js
    assert '"text-max-width": 220' in graph_js
    assert "width: 240" in graph_js
    assert "height: 52" in graph_js
    assert "renderProposalStatus(payload.graph?.active_proposal, payload.graph?.warnings || []);" in graph_js
    assert "showGraphError(payload?.error?.message || \"Failed to load graph data.\");" in graph_js
    assert 'showLoading("Scanning project…");' in graph_js
    assert 'showLoading("Rendering graph…");' in graph_js
    assert 'Rendering ${currentMode === "file" ? "file" : "method"} view…' in graph_js
    assert '"border-color": "#d7dde3"' in graph_js
    assert '"border-color": "#dce3e8"' in graph_js
    assert '"border-color": "#cdd5dc"' in graph_js
    assert '"border-width": 4.5' in graph_js
    assert 'node[node_type = "file"][iteration_state = "add"]' in graph_js
    assert 'node[node_type = "method"][iteration_state = "change"]' in graph_js
    assert 'node[node_type = "package"][iteration_state = "remove"]' in graph_js
    assert 'node[node_type = "file"][iteration_state = "change"]' in graph_js
    assert 'node[node_type = "file"][iteration_state = "remove"]' in graph_js
    assert 'color: "#f7f2e8"' in graph_js
    assert '"background-color": "#173324"' in graph_js
    assert '"background-color": "#2a2416"' in graph_js
    assert '"background-color": "#311819"' in graph_js
    assert '"line-color": "#d4dbe0"' in graph_js
    assert '"target-arrow-color": "#d4dbe0"' in graph_js
    assert "width: 4" in graph_js
    assert 'selector: \'node[iteration_state = "add"]\'' in graph_js
    assert 'selector: \'edge[iteration_state = "remove"]\'' in graph_js
    assert 'iteration_state: node.iteration_state || "present"' in graph_js
    assert 'iteration_state: edge.iteration_state || "present"' in graph_js
    assert "file: buildFileGraphState(payload.graph)" in graph_js
    assert "diagram.transitions" not in graph_js
    assert "graph-proposal-status__warnings" in graph_js

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
        add_proposal=lambda project_id, body: (201, "application/json; charset=utf-8", b"{}", {}),
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

    fake_proposal_post = SimpleNamespace(
        path="/projects/demo/proposals",
        headers={"Content-Length": "2"},
        rfile=SimpleNamespace(read=lambda length: b"{}"),
        _send=lambda *args, **kwargs: sent.append(args),
    )
    handler_class.do_POST(fake_proposal_post)
    assert sent[2][0] == 201
