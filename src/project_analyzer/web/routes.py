from __future__ import annotations

from html import escape
from pathlib import Path
from urllib.parse import parse_qs
import json

from .app import WebAppContext
from ..app_config import DEFAULT_PORT
from ..services import ProposalApplicationError


class WebRoutes:
    def __init__(self, context: WebAppContext):
        self.context = context
        static_dir = Path(__file__).resolve().parent / "static"
        self._asset_versions = {
            asset_path.name: str(int(asset_path.stat().st_mtime_ns))
            for asset_path in static_dir.iterdir()
            if asset_path.is_file()
        }

    def homepage(
        self,
        error: str | None = None,
        message: str | None = None,
    ) -> tuple[int, str, bytes]:
        projects = self.context.project_service.list_projects()
        cards = "\n".join(
            f"""
            <article class="project-card" data-project-id="{project.id}" data-project-href="/projects/{project.id}" tabindex="0" role="link">
              <a class="project-card__link" href="/projects/{project.id}">
                <div class="project-card__title">{escape(project.name)}</div>
                <div class="project-card__path">{escape(project.path)}</div>
              </a>
              <form method="post" action="/projects/{project.id}/delete" class="project-card__actions">
                <button type="submit" class="button button--danger">Delete</button>
              </form>
            </article>
            """
            for project in projects
        ) or '<div class="empty-state">No projects saved yet.</div>'

        error_block = (
            f'<div class="flash flash--error">{escape(error)}</div>' if error else ""
        )
        message_block = (
            f'<div class="flash flash--success">{escape(message)}</div>' if message else ""
        )
        html = self._page(
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
              <section class="panel">
                <h2>Add Project</h2>
                <form method="post" action="/projects" class="project-form">
                  <label for="project-path">Python project root path</label>
                  <input id="project-path" name="path" type="text" placeholder="/absolute/path/to/project" required />
                  <div class="form-hint">Panalyzer accepts local Python project roots and rejects filesystem root paths like <code>/</code>.</div>
                  <button type="submit">Save Project</button>
                </form>
              </section>
              <section class="panel">
                {message_block}
                {error_block}
                <div class="panel__header">
                  <h2>Projects</h2>
                  <span>{len(projects)} saved</span>
                </div>
                <div class="project-grid">
                  {cards}
                </div>
              </section>
            </main>
            <script>
              const createdProjectKey = "panalyzer-created-project";
              const createdProjectReloadKey = "panalyzer-created-project-reloaded";

              function syncCreatedProjectCard() {{
                const createdProjectId = window.sessionStorage.getItem(createdProjectKey);
                if (!createdProjectId) {{
                  return;
                }}

                const existingCard = document.querySelector(`[data-project-id="${{createdProjectId}}"]`);
                if (existingCard) {{
                  window.sessionStorage.removeItem(createdProjectKey);
                  window.sessionStorage.removeItem(createdProjectReloadKey);
                  return;
                }}

                const reloadedProjectId = window.sessionStorage.getItem(createdProjectReloadKey);
                if (reloadedProjectId === createdProjectId) {{
                  window.sessionStorage.removeItem(createdProjectReloadKey);
                  return;
                }}

                window.sessionStorage.setItem(createdProjectReloadKey, createdProjectId);
                window.location.reload();
              }}

              function enableProjectCardNavigation() {{
                const cards = document.querySelectorAll("[data-project-href]");
                for (const card of cards) {{
                  const href = card.getAttribute("data-project-href");
                  if (!href) {{
                    continue;
                  }}
                  card.addEventListener("click", (event) => {{
                    if (event.target instanceof Element && event.target.closest("button, a, form")) {{
                      return;
                    }}
                    window.location.href = href;
                  }});
                  card.addEventListener("keydown", (event) => {{
                    if (event.key !== "Enter" && event.key !== " ") {{
                      return;
                    }}
                    event.preventDefault();
                    window.location.href = href;
                  }});
                }}
              }}

              window.addEventListener("pageshow", syncCreatedProjectCard);
              window.addEventListener("DOMContentLoaded", enableProjectCardNavigation);
            </script>
            """,
        )
        return 200, "text/html; charset=utf-8", html.encode("utf-8")

    def add_project(self, body: bytes) -> tuple[int, str, bytes, dict[str, str]]:
        form = parse_qs(body.decode("utf-8"))
        path = form.get("path", [""])[0]
        try:
            project = self.context.project_service.add_project(path)
        except ValueError as exc:
            status, content_type, payload = self.homepage(str(exc))
            return status, content_type, payload, {}
        return 303, "text/plain; charset=utf-8", b"", {"Location": f"/projects/{project.id}?created=1"}

    def delete_project(self, project_id: str) -> tuple[int, str, bytes, dict[str, str]]:
        deleted = self.context.project_service.delete_project(project_id)
        if not deleted:
            status, content_type, payload = self.not_found()
            return status, content_type, payload, {}
        return 303, "text/plain; charset=utf-8", b"", {"Location": "/?message=Project+deleted"}

    def project_detail(self, project_id: str, created: bool = False) -> tuple[int, str, bytes]:
        project_context = self.context.project_service.get_project_context(project_id)
        if project_context is None:
            return self.not_found()
        project = project_context.registration

        created_script = ""
        if created:
            created_script = f"""
            <script>
              window.sessionStorage.setItem("panalyzer-created-project", "{project.id}");
              window.sessionStorage.removeItem("panalyzer-created-project-reloaded");
            </script>
            """

        html = self._page(
            project.name,
            f"""
            <main class="shell shell--detail">
              <section class="graph-panel">
                <div class="graph-stage">
                  <div class="graph-nav">
                    <a class="action-link" href="/">Back to projects</a>
                    <form method="post" action="/projects/{project.id}/delete">
                      <button type="submit" class="button button--danger">Delete project</button>
                    </form>
                  </div>
                  <div class="graph-toolbar">
                    <label class="view-toggle" for="graph-view-mode">
                      <select id="graph-view-mode">
                        <option value="file" selected>Files</option>
                        <option value="method">Methods</option>
                      </select>
                    </label>
                  </div>
                  <div class="graph-project-meta">
                    <div class="graph-project-meta__name">{escape(project.name)}</div>
                    <div class="graph-project-meta__path">{escape(project.path)}</div>
                  </div>
                  <div class="graph-proposal-status" id="graph-proposal-status" hidden></div>
                  <div class="graph-hovercard" id="graph-hovercard" hidden></div>
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
            {created_script}
            <script type="module" src="{self._static_url('graph.js')}"></script>
            """,
        )
        return 200, "text/html; charset=utf-8", html.encode("utf-8")

    def project_graph(self, project_id: str) -> tuple[int, str, bytes]:
        project_context = self.context.project_service.get_project_context(project_id)
        if project_context is None:
            return self.not_found()
        try:
            graph, diagram = self.context.proposal_service.analyze_with_latest(
                project_id=project_id,
                project_root=Path(project_context.registration.path),
                project=project_context.analysis.project,
            )
        except ProposalApplicationError as exc:
            payload = json.dumps(
                {
                    "error": {
                        "code": exc.code,
                        "message": exc.message,
                        "errors": [issue.model_dump(mode="json") for issue in exc.errors],
                    }
                },
                indent=2,
            ).encode("utf-8")
            return 409, "application/json; charset=utf-8", payload
        payload = json.dumps(
            {
                "graph": graph.model_dump(mode="json"),
            },
            indent=2,
        ).encode("utf-8")
        return 200, "application/json; charset=utf-8", payload

    def add_proposal(self, project_id: str, body: bytes) -> tuple[int, str, bytes, dict[str, str]]:
        project_context = self.context.project_service.get_project_context(project_id)
        if project_context is None:
            status, content_type, payload = self.not_found()
            return status, content_type, payload, {}

        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            response = json.dumps(
                {
                    "valid": False,
                    "warnings": [],
                    "errors": [
                        {
                            "code": "invalid_json",
                            "path": "$",
                            "message": f"Request body is not valid JSON: {exc.msg}",
                        }
                    ],
                },
                indent=2,
            ).encode("utf-8")
            return 400, "application/json; charset=utf-8", response, {}

        result = self.context.proposal_service.save(
            project_id=project_id,
            project_root=Path(project_context.registration.path),
            project=project_context.analysis.project,
            payload=payload,
        )
        status = 201 if result.validation.valid else 202
        response = json.dumps(
            {
                "proposal": result.proposal.model_dump(mode="json"),
                "validation": result.validation.model_dump(mode="json"),
            },
            indent=2,
        ).encode("utf-8")
        return status, "application/json; charset=utf-8", response, {}

    def static_asset(self, asset_name: str) -> tuple[int, str, bytes, dict[str, str]]:
        base_dir = Path(__file__).resolve().parent / "static"
        asset_path = (base_dir / asset_name).resolve()
        if not asset_path.is_file() or asset_path.parent != base_dir.resolve():
            return self.not_found()
        content_type = "text/plain; charset=utf-8"
        if asset_path.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        elif asset_path.suffix == ".js":
            content_type = "text/javascript; charset=utf-8"
        headers = {
            "Cache-Control": "no-store, max-age=0",
        }
        return 200, content_type, asset_path.read_bytes(), headers

    def not_found(self) -> tuple[int, str, bytes]:
        html = self._page(
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

    def _static_url(self, asset_name: str) -> str:
        version = self._asset_versions.get(asset_name)
        if version is None:
            return f"/static/{asset_name}"
        return f"/static/{asset_name}?v={version}"

    def _page(self, title: str, body: str) -> str:
        return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escape(title)} · Panalyzer</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;700&display=swap" rel="stylesheet" />
    <link rel="stylesheet" href="{self._static_url('app.css')}" />
  </head>
  <body>
    {body}
  </body>
</html>
"""
