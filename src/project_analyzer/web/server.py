from __future__ import annotations

from argparse import ArgumentParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs
from urllib.parse import urlparse

from ..app_config import ensure_app_config, load_app_config, resolve_server_config
from ..services import ProjectAnalysisService, ProjectRegistry
from .app import WebAppContext
from .routes import WebRoutes


def serve(config_path: Path) -> None:
    ensure_app_config(config_path)
    config = load_app_config(config_path)
    server_config = resolve_server_config(config)
    context = WebAppContext(
        base_dir=config_path.parent.resolve(),
        registry=ProjectRegistry(config_path),
        analysis_service=ProjectAnalysisService(),
    )
    routes = WebRoutes(context)
    handler_class = _build_handler(routes)
    server = ThreadingHTTPServer((server_config.host, server_config.port), handler_class)
    try:
        server.serve_forever()
    finally:
        server.server_close()


def main() -> None:
    parser = ArgumentParser(description="Run the panalyzer web application.")
    parser.add_argument("--config", required=True, help="Path to app.yaml")
    args = parser.parse_args()
    serve(Path(args.config).resolve())


def _build_handler(routes: WebRoutes) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = parsed.path
            if path == "/":
                message = parse_qs(parsed.query).get("message", [""])[0] or None
                self._send(*routes.homepage(message=message))
                return
            if path.startswith("/projects/") and path.endswith("/graph"):
                project_id = path.removeprefix("/projects/").removesuffix("/graph").strip("/")
                self._send(*routes.project_graph(project_id))
                return
            if path.startswith("/projects/"):
                project_id = path.removeprefix("/projects/").strip("/")
                created = parse_qs(parsed.query).get("created", ["0"])[0] == "1"
                self._send(*routes.project_detail(project_id, created=created))
                return
            if path.startswith("/static/"):
                asset_name = path.removeprefix("/static/")
                self._send(*routes.static_asset(asset_name))
                return
            self._send(*routes.not_found())

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/projects":
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length)
                status, content_type, payload, headers = routes.add_project(body)
                self._send(status, content_type, payload, headers=headers)
                return
            if parsed.path.startswith("/projects/") and parsed.path.endswith("/delete"):
                project_id = parsed.path.removeprefix("/projects/").removesuffix("/delete").strip("/")
                status, content_type, payload, headers = routes.delete_project(project_id)
                self._send(status, content_type, payload, headers=headers)
                return
            else:
                self._send(*routes.not_found())
                return

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

        def _send(
            self,
            status: int,
            content_type: str,
            payload: bytes,
            headers: dict[str, str] | None = None,
        ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            if headers is None:
                headers = {}
            if content_type.startswith("text/html") and "Cache-Control" not in headers:
                headers["Cache-Control"] = "no-store, max-age=0"
            if content_type.startswith("application/json") and "Cache-Control" not in headers:
                headers["Cache-Control"] = "no-store, max-age=0"
            if headers:
                for key, value in headers.items():
                    self.send_header(key, value)
            self.end_headers()
            if payload:
                self.wfile.write(payload)

    return Handler


if __name__ == "__main__":
    main()
