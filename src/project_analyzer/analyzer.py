from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import ast
import json
import os
from pathlib import Path
import subprocess
from urllib.parse import unquote, urlparse

from .config import AnalyzerConfig
from .models import Method, MethodReference, Package, Project, SourceFile


@dataclass
class _DiscoveredSymbol:
    name: str
    qualname: str
    signature: str
    file: str
    line: int
    start_line: int
    start_col: int
    end_line: int
    end_col: int

    def contains(self, line: int, col: int) -> bool:
        if line < self.start_line or line > self.end_line:
            return False
        if line == self.start_line and col < self.start_col:
            return False
        if line == self.end_line and col > self.end_col:
            return False
        return True

    @property
    def span_size(self) -> tuple[int, int]:
        return (self.end_line - self.start_line, self.end_col - self.start_col)


@dataclass
class _DiscoveredCall:
    source_method: str | None
    raw_target: str
    file: str
    line: int
    position_line: int
    position_col: int


@dataclass
class _ModuleInfo:
    import_path: str
    file_path: Path
    source_root: Path
    symbols: list[_DiscoveredSymbol]
    calls: list[_DiscoveredCall]


class _ModuleCollector(ast.NodeVisitor):
    def __init__(self, source: str, file_path: Path, import_path: str):
        self.source = source
        self.file_path = file_path
        self.import_path = import_path
        self.symbols: list[_DiscoveredSymbol] = []
        self.calls: list[_DiscoveredCall] = []
        self.scope_stack: list[str] = []
        self.function_stack: list[str] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        qualname = self._qualname(node.name)
        self.symbols.append(
            _DiscoveredSymbol(
                name=node.name,
                qualname=qualname,
                signature=_render_class_signature(node),
                file=str(self.file_path),
                line=node.lineno,
                start_line=node.lineno,
                start_col=node.col_offset,
                end_line=node.end_lineno or node.lineno,
                end_col=node.end_col_offset or node.col_offset,
            )
        )
        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function_like(node, asynchronous=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function_like(node, asynchronous=True)

    def visit_Call(self, node: ast.Call) -> None:
        raw_target = _expression_name(node.func)
        position = _call_target_position(node.func)
        if raw_target is not None and position is not None:
            self.calls.append(
                _DiscoveredCall(
                    source_method=self.function_stack[-1] if self.function_stack else None,
                    raw_target=raw_target,
                    file=str(self.file_path),
                    line=node.lineno,
                    position_line=position[0],
                    position_col=position[1],
                )
            )
        self.generic_visit(node)

    def _visit_function_like(self, node: ast.FunctionDef | ast.AsyncFunctionDef, *, asynchronous: bool) -> None:
        qualname = self._qualname(node.name)
        self.symbols.append(
            _DiscoveredSymbol(
                name=node.name,
                qualname=qualname,
                signature=_render_function_signature(node, asynchronous=asynchronous),
                file=str(self.file_path),
                line=node.lineno,
                start_line=node.lineno,
                start_col=node.col_offset,
                end_line=node.end_lineno or node.lineno,
                end_col=node.end_col_offset or node.col_offset,
            )
        )
        self.scope_stack.append(node.name)
        self.function_stack.append(qualname)
        self.generic_visit(node)
        self.function_stack.pop()
        self.scope_stack.pop()

    def _qualname(self, name: str) -> str:
        parts = [self.import_path, *self.scope_stack, name]
        return ".".join(parts)


class _PyrightLanguageServer:
    def __init__(self, root: Path, source_roots: list[Path]):
        self.root = root
        self.source_roots = source_roots
        self.process: subprocess.Popen[bytes] | None = None
        self._next_id = 0

    def __enter__(self) -> _PyrightLanguageServer:
        try:
            self.process = subprocess.Popen(
                ["pyright-langserver", "--stdio"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "pyright-langserver is required for analysis but is not installed"
            ) from exc

        self._request(
            "initialize",
            {
                "processId": os.getpid(),
                "rootUri": self.root.as_uri(),
                "capabilities": {},
                "workspaceFolders": [{"uri": self.root.as_uri(), "name": self.root.name}],
            },
        )
        self._notify("initialized", {})
        self._notify(
            "workspace/didChangeConfiguration",
            {
                "settings": {
                    "python": {
                        "analysis": {
                            "autoSearchPaths": False,
                            "useLibraryCodeForTypes": True,
                            "diagnosticMode": "workspace",
                            "extraPaths": [str(path) for path in self.source_roots],
                        }
                    }
                }
            },
        )
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.process is None:
            return
        try:
            self._request("shutdown", None)
            self._notify("exit", {})
        finally:
            if self.process.poll() is None:
                self.process.kill()
            self.process.wait(timeout=5)

    def open_document(self, file_path: Path, source: str) -> None:
        self._notify(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": file_path.as_uri(),
                    "languageId": "python",
                    "version": 1,
                    "text": source,
                }
            },
        )

    def definition(self, file_path: Path, line: int, col: int) -> list[tuple[Path, int, int]]:
        result = self._request(
            "textDocument/definition",
            {
                "textDocument": {"uri": file_path.as_uri()},
                "position": {"line": line, "character": col},
            },
        )
        locations = result if isinstance(result, list) else ([result] if result else [])
        resolved: list[tuple[Path, int, int]] = []
        for location in locations:
            if not isinstance(location, dict):
                continue
            uri = location.get("uri")
            range_data = location.get("range", {})
            start = range_data.get("start", {})
            if not isinstance(uri, str):
                continue
            resolved.append(
                (
                    _uri_to_path(uri),
                    int(start.get("line", 0)),
                    int(start.get("character", 0)),
                )
            )
        return resolved

    def _notify(self, method: str, params: object) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def _request(self, method: str, params: object) -> object:
        request_id = self._next_id
        self._next_id += 1
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})

        while True:
            message = self._read()
            if message.get("id") == request_id:
                if "error" in message:
                    raise RuntimeError(f"pyright request failed: {message['error']}")
                return message.get("result")

    def _send(self, payload: dict[str, object]) -> None:
        if self.process is None or self.process.stdin is None:
            raise RuntimeError("pyright language server is not running")
        data = json.dumps(payload).encode("utf-8")
        header = f"Content-Length: {len(data)}\r\n\r\n".encode("ascii")
        self.process.stdin.write(header)
        self.process.stdin.write(data)
        self.process.stdin.flush()

    def _read(self) -> dict[str, object]:
        if self.process is None or self.process.stdout is None:
            raise RuntimeError("pyright language server is not running")

        headers: dict[str, str] = {}
        while True:
            line = self.process.stdout.readline()
            if not line:
                raise RuntimeError("pyright language server terminated unexpectedly")
            if line == b"\r\n":
                break
            decoded = line.decode("ascii").strip()
            name, _, value = decoded.partition(":")
            headers[name.lower()] = value.strip()

        content_length = int(headers["content-length"])
        body = self.process.stdout.read(content_length)
        return json.loads(body.decode("utf-8"))


class ProjectAnalyzer(ABC):
    """Abstract adapter for analyzing a project tree."""

    @abstractmethod
    def analyze(self, root: Path, config: AnalyzerConfig) -> Project:
        """Analyze *root* and return the project domain model."""


class PythonAnalyzer(ProjectAnalyzer):
    """AST collector with Pyright-backed definition resolution."""

    def analyze(self, root: Path, config: AnalyzerConfig) -> Project:
        root = root.resolve()
        source_roots = config.resolved_source_roots(root)
        modules: dict[str, _ModuleInfo] = {}
        file_sources: dict[str, str] = {}

        for file_path in _discover_python_files(root):
            if config.should_ignore_file(root, file_path):
                continue
            source_root = _source_root_for_file(file_path, source_roots)
            if source_root is None:
                continue
            source = _read_source(file_path)
            if source is None:
                continue
            module = _build_module_info(file_path, source_root, source)
            if module is None:
                continue
            modules[module.import_path] = module
            file_sources[str(module.file_path)] = source

        symbol_index = _SymbolIndex.from_modules(modules)
        references = self._resolve_references(root, source_roots, modules, file_sources, symbol_index, config)

        source_files: list[SourceFile] = []
        import_path_to_source_root: dict[str, Path] = {}
        for import_path, module in sorted(modules.items()):
            import_path_to_source_root[import_path] = module.source_root
            source_files.append(
                SourceFile(
                    path=str(module.file_path),
                    import_path=import_path,
                    methods=[
                        Method(
                            name=symbol.name,
                            qualname=symbol.qualname,
                            signature=symbol.signature,
                            line=symbol.line,
                        )
                        for symbol in module.symbols
                    ],
                )
            )

        packages_by_name: dict[str, Package] = {}
        for source_file in sorted(source_files, key=lambda item: item.import_path):
            source_root = import_path_to_source_root[source_file.import_path]
            package_name = _package_name_for_file(source_root, source_file.path, source_file.import_path)
            package = packages_by_name.get(package_name)
            if package is None:
                package = Package(
                    name=package_name,
                    path=_package_path(source_root, source_file.path, package_name),
                    files=[],
                )
                packages_by_name[package_name] = package
            package.files.append(source_file)

        return Project(
            root=str(root),
            packages=sorted(packages_by_name.values(), key=lambda item: item.name),
            references=references,
        )

    def _resolve_references(
        self,
        root: Path,
        source_roots: list[Path],
        modules: dict[str, _ModuleInfo],
        file_sources: dict[str, str],
        symbol_index: _SymbolIndex,
        config: AnalyzerConfig,
    ) -> list[MethodReference]:
        references: list[MethodReference] = []
        with _PyrightLanguageServer(root, source_roots) as pyright:
            for module in modules.values():
                pyright.open_document(module.file_path, file_sources[str(module.file_path)])

            for module in sorted(modules.values(), key=lambda item: item.import_path):
                for call in module.calls:
                    target = None
                    for path, line, col in pyright.definition(
                        Path(call.file),
                        call.position_line,
                        call.position_col,
                    ):
                        symbol = symbol_index.resolve(path, line, col)
                        if symbol is not None:
                            target = symbol.qualname
                            break

                    if target is None:
                        if not config.include_external_references:
                            continue
                        target = _fallback_target(module.import_path, call.raw_target)

                    references.append(
                        MethodReference(
                            source_method=call.source_method,
                            target_method=target,
                            file_path=call.file,
                            line=call.line,
                        )
                    )
        return references


@dataclass
class _SymbolIndex:
    by_file: dict[str, list[_DiscoveredSymbol]]

    @classmethod
    def from_modules(cls, modules: dict[str, _ModuleInfo]) -> _SymbolIndex:
        by_file: dict[str, list[_DiscoveredSymbol]] = {}
        for module in modules.values():
            by_file[str(module.file_path)] = sorted(
                module.symbols,
                key=lambda symbol: (symbol.span_size[0], symbol.span_size[1]),
            )
        return cls(by_file=by_file)

    def resolve(self, file_path: Path, line: int, col: int) -> _DiscoveredSymbol | None:
        symbols = self.by_file.get(str(file_path.resolve()))
        if not symbols:
            return None
        candidates = [symbol for symbol in symbols if symbol.contains(line + 1, col)]
        if not candidates:
            candidates = [symbol for symbol in symbols if symbol.line == line + 1]
        if not candidates:
            return None
        return min(candidates, key=lambda symbol: symbol.span_size)


def _build_module_info(file_path: Path, source_root: Path, source: str) -> _ModuleInfo | None:
    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError:
        return None

    import_path = _path_to_import_path(source_root, file_path)
    collector = _ModuleCollector(source, file_path.resolve(), import_path)
    collector.visit(tree)
    return _ModuleInfo(
        import_path=import_path,
        file_path=file_path.resolve(),
        source_root=source_root,
        symbols=collector.symbols,
        calls=collector.calls,
    )


def _read_source(file_path: Path) -> str | None:
    try:
        return file_path.read_text(encoding="utf-8")
    except OSError:
        return None


def _path_to_import_path(source_root: Path, file_path: Path) -> str:
    rel = file_path.relative_to(source_root).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    if not parts:
        return source_root.name
    return ".".join(parts)


def _render_class_signature(node: ast.ClassDef) -> str:
    if not node.bases:
        return f"class {node.name}"
    bases = ", ".join(ast.unparse(base).strip() for base in node.bases)
    return f"class {node.name}({bases})"


def _render_function_signature(node: ast.FunctionDef | ast.AsyncFunctionDef, *, asynchronous: bool) -> str:
    prefix = "async def" if asynchronous else "def"
    args = ast.unparse(node.args).strip()
    returns = f" -> {ast.unparse(node.returns).strip()}" if node.returns is not None else ""
    return f"{prefix} {node.name}({args}){returns}"


def _expression_name(node: ast.AST | None) -> str | None:
    if node is None:
        return None
    try:
        return ast.unparse(node).strip()
    except Exception:
        return None


def _call_target_position(node: ast.AST) -> tuple[int, int] | None:
    if isinstance(node, ast.Attribute):
        return ((node.end_lineno or node.lineno) - 1, (node.end_col_offset or node.col_offset) - 1)
    if isinstance(node, ast.Name):
        return (node.lineno - 1, node.col_offset)
    if isinstance(node, ast.Call):
        return _call_target_position(node.func)
    return None


def _fallback_target(import_path: str, raw_target: str) -> str:
    parts = raw_target.split(".")
    if len(parts) == 1:
        return f"{import_path}.{raw_target}"
    return raw_target


def _discover_python_files(root: Path) -> list[Path]:
    ignored_dirs = {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        "site-packages",
        "dist",
        "build",
    }
    files: list[Path] = []
    for path in root.rglob("*.py"):
        if any(part in ignored_dirs for part in path.parts):
            continue
        files.append(path)
    return sorted(files)


def _source_root_for_file(file_path: Path, source_roots: list[Path]) -> Path | None:
    for source_root in sorted(source_roots, key=lambda path: len(path.parts), reverse=True):
        if file_path.is_relative_to(source_root):
            return source_root
    return None


def _package_name_for_file(source_root: Path, file_path: str, import_path: str) -> str:
    path = Path(file_path)
    if path.name == "__init__.py":
        return import_path
    relative_parent = path.parent.relative_to(source_root)
    if not relative_parent.parts:
        return source_root.name
    return ".".join(relative_parent.parts)


def _package_path(source_root: Path, file_path: str, package_name: str) -> str:
    path = Path(file_path)
    if package_name == source_root.name:
        return str(source_root)
    return str(path.parent)


def _uri_to_path(uri: str) -> Path:
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        return Path(uri)
    return Path(unquote(parsed.path)).resolve()
