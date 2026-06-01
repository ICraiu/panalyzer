from __future__ import annotations

from html import escape
from pathlib import Path
from urllib.parse import parse_qs
import json

from .app import WebAppContext
from ..app_config import DEFAULT_PORT


class WebRoutes:
    def __init__(self, context: WebAppContext):
        self.context = context

    def homepage(self, error: str | None = None) -> tuple[int, str, bytes]:
        projects = self.context.registry.list_projects()
        cards = "\n".join(
            f"""
            <a class="project-card" href="/projects/{project.id}">
              <div class="project-card__title">{escape(project.name)}</div>
              <div class="project-card__path">{escape(project.path)}</div>
              {f'<div class="project-card__source">{escape(project.source)}</div>' if project.source else ""}
            </a>
            """
            for project in projects
        ) or '<div class="empty-state">No projects saved yet.</div>'

        error_block = (
            f'<div class="flash flash--error">{escape(error)}</div>' if error else ""
        )
        html = _page(
            "Panalyzer",
            f"""
            <main class="shell shell--home">
              <section class="hero">
                <div>
                  <h1>Panalyzer</h1>
                  <p>Track package, file, method, and call structure across your projects.</p>
                </div>
                <div class="meta-chip">Default port {DEFAULT_PORT}</div>
              </section>
              {error_block}
              <section class="panel">
                <h2>Add Project</h2>
                <form method="post" action="/projects" class="project-form">
                  <label for="project-path">Project root path or Git repository URL</label>
                  <input id="project-path" name="path" type="text" placeholder="/absolute/path/to/project or https://github.com/org/repo.git" required />
                  <button type="submit">Save Project</button>
                </form>
              </section>
              <section class="panel">
                <div class="panel__header">
                  <h2>Projects</h2>
                  <span>{len(projects)} saved</span>
                </div>
                <div class="project-grid">
                  {cards}
                </div>
              </section>
            </main>
            """,
        )
        return 200, "text/html; charset=utf-8", html.encode("utf-8")

    def add_project(self, body: bytes) -> tuple[int, str, bytes, dict[str, str]]:
        form = parse_qs(body.decode("utf-8"))
        path = form.get("path", [""])[0]
        try:
            project = self.context.registry.add_project(path)
        except ValueError as exc:
            status, content_type, payload = self.homepage(str(exc))
            return status, content_type, payload, {}
        return 303, "text/plain; charset=utf-8", b"", {"Location": f"/projects/{project.id}"}

    def project_detail(self, project_id: str) -> tuple[int, str, bytes]:
        project = self.context.registry.get_project(project_id)
        if project is None:
            return self.not_found()

        html = _page(
            project.name,
            f"""
            <main class="shell shell--detail">
              <section class="graph-panel">
                <div class="graph-stage">
                  <div class="graph-toolbar">
                    <label class="view-toggle" for="graph-view-mode">
                      <select id="graph-view-mode">
                        <option value="file" selected>Files</option>
                        <option value="method">Methods</option>
                      </select>
                    </label>
                  </div>
                  <div class="graph-selection">
                    <div class="sidebar-card">
                      <h2>Selection</h2>
                      <div id="selection-panel">Select a node or edge.</div>
                    </div>
                  </div>
                  <div class="graph-project-meta">
                    <div class="graph-project-meta__name">{escape(project.name)}</div>
                    <div class="graph-project-meta__path">{escape(project.path)}</div>
                    {f'<div class="graph-project-meta__path">{escape(project.source)}</div>' if project.source else ""}
                  </div>
                  <div class="graph-loading" id="graph-loading" aria-live="polite">
                    <div class="graph-loading__spinner" aria-hidden="true"></div>
                    <div class="graph-loading__text">Loading graph…</div>
                  </div>
                  <div id="graph-root" data-graph-url="/projects/{project.id}/graph"></div>
                </div>
              </section>
            </main>
            <script src="https://unpkg.com/cytoscape@3.30.4/dist/cytoscape.min.js"></script>
            <script src="https://cdn.jsdelivr.net/npm/elkjs@0.9.3/lib/elk.bundled.js"></script>
            <script src="https://cdn.jsdelivr.net/npm/cytoscape-elk@2.3.0/dist/cytoscape-elk.min.js"></script>
            <script type="module" src="/static/graph.js"></script>
            """,
        )
        return 200, "text/html; charset=utf-8", html.encode("utf-8")

    def project_graph(self, project_id: str) -> tuple[int, str, bytes]:
        project = self.context.registry.get_project(project_id)
        if project is None:
            return self.not_found()
        artifacts = self.context.analysis_service.analyze_project(Path(project.path))
        payload = json.dumps(artifacts.graph.model_dump(mode="json"), indent=2).encode("utf-8")
        return 200, "application/json; charset=utf-8", payload

    def static_asset(self, asset_name: str) -> tuple[int, str, bytes]:
        base_dir = Path(__file__).resolve().parent / "static"
        asset_path = (base_dir / asset_name).resolve()
        if not asset_path.is_file() or asset_path.parent != base_dir.resolve():
            return self.not_found()
        content_type = "text/plain; charset=utf-8"
        if asset_path.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        elif asset_path.suffix == ".js":
            content_type = "text/javascript; charset=utf-8"
        return 200, content_type, asset_path.read_bytes()

    def not_found(self) -> tuple[int, str, bytes]:
        html = _page(
            "Not Found",
            """
            <main class="shell">
              <section class="panel">
                <h1>Not Found</h1>
                <p>The requested page does not exist.</p>
                <a class="action-link" href="/">Back to home</a>
              </section>
            </main>
            """,
        )
        return 404, "text/html; charset=utf-8", html.encode("utf-8")


def _page(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escape(title)} · Panalyzer</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;700&display=swap" rel="stylesheet" />
    <link rel="stylesheet" href="/static/app.css" />
  </head>
  <body>
    {body}
  </body>
</html>
"""
