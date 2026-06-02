from __future__ import annotations

import ast
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from .config import AnalyzerConfig
from .models import Method, MethodReference, Package, Project, SourceFile


@dataclass
class _DiscoveredSymbol:
    name: str
    qualname: str
    signature: str
    file: str
    line: int


@dataclass
class _DiscoveredCall:
    source: str
    target: str
    raw_target: str
    file: str
    line: int
    confidence: str


class _PythonFileAnalyzer(ast.NodeVisitor):
    """Walk a Python AST and collect symbols plus call edges."""

    def __init__(self, file_path: Path, import_path: str):
        self.file_path = file_path
        self.import_path = import_path
        self.symbols: list[_DiscoveredSymbol] = []
        self.edges: list[_DiscoveredCall] = []
        self.imports: dict[str, str] = {}
        self.scope_stack: list[str] = [import_path]

    @property
    def current_scope(self) -> str:
        return ".".join(self.scope_stack)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            local = alias.asname or alias.name.split(".")[0]
            self.imports[local] = alias.name
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module is None:
            return
        module = self._resolve_import_from_module(node.module, node.level)
        for alias in node.names:
            local = alias.asname or alias.name
            self.imports[local] = f"{module}.{alias.name}"
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        qualname = f"{self.current_scope}.{node.name}"
        self.symbols.append(
            _DiscoveredSymbol(
                name=node.name,
                qualname=qualname,
                signature=_render_class_signature(node),
                file=str(self.file_path),
                line=node.lineno,
            )
        )
        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def _visit_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> None:
        qualname = f"{self.current_scope}.{node.name}"
        self.symbols.append(
            _DiscoveredSymbol(
                name=node.name,
                qualname=qualname,
                signature=_render_function_signature(node),
                file=str(self.file_path),
                line=node.lineno,
            )
        )
        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_Call(self, node: ast.Call) -> None:
        raw_target = self._call_name(node.func)
        if raw_target:
            resolved_target, confidence = self._resolve_target(raw_target)
            self.edges.append(
                _DiscoveredCall(
                    source=self.current_scope,
                    target=resolved_target,
                    raw_target=raw_target,
                    file=str(self.file_path),
                    line=node.lineno,
                    confidence=confidence,
                )
            )
        self.generic_visit(node)

    def _call_name(self, node: ast.AST) -> str | None:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Call):
            return self._call_name(node.func)
        if isinstance(node, ast.Attribute):
            base = self._call_name(node.value)
            if base:
                return f"{base}.{node.attr}"
            return node.attr
        return None

    def _resolve_target(self, target: str) -> tuple[str, str]:
        parts = target.split(".")
        first = parts[0]

        if first in self.imports:
            imported = self.imports[first]
            rest = parts[1:]
            if rest:
                return ".".join([imported, *rest]), "resolved_import"
            return imported, "resolved_import"

        if first == "self" and len(parts) > 1:
            if len(self.scope_stack) >= 3:
                class_scope = ".".join(self.scope_stack[:-1])
                return f"{class_scope}.{parts[1]}", "resolved_self_method"
            return target, "unresolved_self"

        if len(parts) == 1:
            return f"{self.import_path}.{target}", "local_import_path_guess"

        return target, "unresolved"

    def _resolve_import_from_module(self, module: str, level: int) -> str:
        if level <= 0:
            return module

        package_parts = self.import_path.split(".")
        if package_parts:
            package_parts = package_parts[:-1]

        if level > 1:
            package_parts = package_parts[: max(len(package_parts) - (level - 1), 0)]

        resolved_parts = [*package_parts]
        if module:
            resolved_parts.extend(module.split("."))
        return ".".join(resolved_parts)


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
    bases = ", ".join(ast.unparse(base) for base in node.bases)
    return f"class {node.name}({bases})"


def _render_function_signature(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> str:
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    args = _render_arguments(node.args)
    if node.returns is not None:
        return_annotation = f" -> {ast.unparse(node.returns)}"
    else:
        return_annotation = ""
    return f"{prefix} {node.name}({args}){return_annotation}"


def _render_arguments(arguments: ast.arguments) -> str:
    rendered: list[str] = []

    positional = [*arguments.posonlyargs, *arguments.args]
    positional_defaults = [None] * (len(positional) - len(arguments.defaults)) + list(arguments.defaults)

    for index, arg in enumerate(positional):
        rendered.append(_render_argument(arg, positional_defaults[index]))
        if arguments.posonlyargs and index == len(arguments.posonlyargs) - 1:
            rendered.append("/")

    if arguments.vararg is not None:
        rendered.append(_render_argument(arguments.vararg, None, prefix="*"))
    elif arguments.kwonlyargs:
        rendered.append("*")

    for arg, default in zip(arguments.kwonlyargs, arguments.kw_defaults):
        rendered.append(_render_argument(arg, default))

    if arguments.kwarg is not None:
        rendered.append(_render_argument(arguments.kwarg, None, prefix="**"))

    return ", ".join(rendered)


def _render_argument(arg: ast.arg, default: ast.expr | None, prefix: str = "") -> str:
    rendered = f"{prefix}{arg.arg}"
    if arg.annotation is not None:
        rendered = f"{rendered}: {ast.unparse(arg.annotation)}"
    if default is not None:
        rendered = f"{rendered}={ast.unparse(default)}"
    return rendered


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


class ProjectAnalyzer(ABC):
    """Abstract adapter for analyzing a project tree."""

    @abstractmethod
    def analyze(self, root: Path, config: AnalyzerConfig) -> Project:
        """Analyze *root* and return the project domain model."""


class PythonAnalyzer(ProjectAnalyzer):
    """AST-based analyzer for Python projects."""

    def analyze(self, root: Path, config: AnalyzerConfig) -> Project:
        root = root.resolve()
        source_roots = config.resolved_source_roots(root)

        file_symbols: dict[str, list[_DiscoveredSymbol]] = {}
        file_edges: dict[str, list[_DiscoveredCall]] = {}
        import_path_to_file: dict[str, str] = {}
        import_path_to_source_root: dict[str, Path] = {}
        method_to_file: dict[str, str] = {}

        for file_path in _discover_python_files(root):
            if config.should_ignore_file(root, file_path):
                continue
            source_root = _source_root_for_file(file_path, source_roots)
            if source_root is None:
                continue
            import_path = _path_to_import_path(source_root, file_path)
            import_path_to_file[import_path] = str(file_path.resolve())
            import_path_to_source_root[import_path] = source_root

            try:
                source = file_path.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(file_path))
            except (OSError, SyntaxError):
                continue

            file_analyzer = _PythonFileAnalyzer(file_path.resolve(), import_path)
            file_analyzer.visit(tree)

            file_symbols[import_path] = file_analyzer.symbols
            file_edges[import_path] = file_analyzer.edges

            for symbol in file_analyzer.symbols:
                method_to_file[symbol.qualname] = str(file_path.resolve())

        internal_methods = set(method_to_file)
        source_files: list[SourceFile] = []
        all_references: list[MethodReference] = []

        for import_path, symbols in file_symbols.items():
            source_root = import_path_to_source_root[import_path]
            file_path = import_path_to_file[import_path]
            package_name = _package_name_for_file(source_root, file_path, import_path)
            methods = [
                Method(
                    name=symbol.name,
                    qualname=symbol.qualname,
                    signature=symbol.signature,
                    line=symbol.line,
                )
                for symbol in symbols
            ]

            for edge in file_edges.get(import_path, []):
                if edge.target not in internal_methods and not config.include_external_references:
                    continue

                reference = MethodReference(
                    source_method=edge.source if edge.source != import_path else None,
                    target_method=edge.target,
                    file_path=edge.file,
                    line=edge.line,
                )
                all_references.append(reference)

            source_files.append(
                SourceFile(
                    path=file_path,
                    import_path=import_path,
                    methods=methods,
                )
            )

        packages_by_name: dict[str, Package] = {}
        for source_file in sorted(source_files, key=lambda item: item.import_path):
            source_root = import_path_to_source_root[source_file.import_path]
            package_name = _package_name_for_file(
                source_root,
                source_file.path,
                source_file.import_path,
            )
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
            references=all_references,
        )
