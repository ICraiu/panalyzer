from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

import libcst as cst
from libcst import metadata

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


@dataclass
class _ResolvedValue:
    path: str
    kind: str
    confidence: str


@dataclass
class _AssignmentRecord:
    target_attr: str
    source_name: str


@dataclass
class _ClassInfo:
    qualname: str
    attr_types: dict[str, str] = field(default_factory=dict)
    methods: set[str] = field(default_factory=set)
    assignments: list[_AssignmentRecord] = field(default_factory=list)


@dataclass
class _ModuleInfo:
    import_path: str
    file_path: Path
    source_root: Path
    imports: dict[str, str]
    symbols: list[_DiscoveredSymbol]
    calls: list[_DiscoveredCall]
    classes: dict[str, _ClassInfo]


class _QualifiedResolver:
    def __init__(self, modules: dict[str, _ModuleInfo]):
        self.modules = modules
        self.class_infos: dict[str, _ClassInfo] = {}
        self.symbols: set[str] = set()
        self.method_symbols: set[str] = set()

        for module in modules.values():
            self.symbols.add(module.import_path)
            for symbol in module.symbols:
                self.symbols.add(symbol.qualname)
                if symbol.signature.startswith("class "):
                    self.class_infos[symbol.qualname] = module.classes.get(symbol.qualname, _ClassInfo(symbol.qualname))
                else:
                    self.method_symbols.add(symbol.qualname)

    def canonicalize(self, path: str) -> str:
        current = path
        seen: set[str] = set()
        while current not in seen:
            seen.add(current)
            if current in self.symbols:
                return current
            module_path, sep, attr = current.rpartition(".")
            if not sep:
                return current
            module = self.modules.get(module_path)
            if module is None:
                return current
            replacement = module.imports.get(attr)
            if replacement is None:
                return current
            current = replacement
        return current

    def resolve_annotation(self, module: _ModuleInfo, annotation: cst.Annotation | None) -> str | None:
        if annotation is None:
            return None
        return self._resolve_name_like(module, annotation.annotation)

    def _resolve_name_like(self, module: _ModuleInfo, node: cst.CSTNode) -> str | None:
        raw = _expression_name(node)
        if raw is None:
            return None
        parts = raw.split(".")
        first = parts[0]
        if first in module.imports:
            imported = module.imports[first]
            candidate = ".".join([imported, *parts[1:]]) if len(parts) > 1 else imported
            return self.canonicalize(candidate)
        if len(parts) == 1:
            return self.canonicalize(f"{module.import_path}.{raw}")
        return self.canonicalize(raw)


class _ModuleModelCollector(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (metadata.PositionProvider,)

    def __init__(self, module: cst.Module, file_path: Path, import_path: str):
        self.module = module
        self.file_path = file_path
        self.import_path = import_path
        self.imports: dict[str, str] = {}
        self.symbols: list[_DiscoveredSymbol] = []
        self.classes: dict[str, _ClassInfo] = {}
        self.class_stack: list[str] = []
        self.function_stack: list[str] = []
        self._current_init_params: dict[str, str | None] | None = None

    @property
    def current_scope(self) -> str:
        parts = [self.import_path, *self.class_stack, *self.function_stack]
        return ".".join(parts)

    def visit_Import(self, node: cst.Import) -> None:
        for alias in node.names:
            if not isinstance(alias, cst.ImportAlias):
                continue
            name = _expression_name(alias.name)
            if name is None:
                continue
            local = alias.asname.name.value if alias.asname is not None else name.split(".")[0]
            self.imports[local] = name

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        module_name = _resolve_import_from_module(self.import_path, node.module, node.relative)
        if module_name is None or isinstance(node.names, cst.ImportStar):
            return
        for alias in node.names:
            if not isinstance(alias, cst.ImportAlias):
                continue
            imported_name = _expression_name(alias.name)
            if imported_name is None:
                continue
            local = alias.asname.name.value if alias.asname is not None else imported_name
            self.imports[local] = f"{module_name}.{imported_name}"

    def visit_ClassDef(self, node: cst.ClassDef) -> None:
        qualname = f"{self.current_scope}.{node.name.value}"
        self.symbols.append(
            _DiscoveredSymbol(
                name=node.name.value,
                qualname=qualname,
                signature=_render_class_signature(self.module, node),
                file=str(self.file_path),
                line=self.get_metadata(metadata.PositionProvider, node).start.line,
            )
        )
        self.classes[qualname] = _ClassInfo(qualname=qualname)
        self.class_stack.append(node.name.value)

    def leave_ClassDef(self, original_node: cst.ClassDef) -> None:
        self.class_stack.pop()

    def visit_AnnAssign(self, node: cst.AnnAssign) -> None:
        if not self.class_stack:
            return
        class_info = self.classes.get(".".join([self.import_path, *self.class_stack]))
        if class_info is None:
            return
        if isinstance(node.target, cst.Name):
            annotation = _annotation_name(node.annotation.annotation)
            if annotation is not None:
                class_info.attr_types[node.target.value] = annotation

    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:
        qualname = f"{self.current_scope}.{node.name.value}"
        self.symbols.append(
            _DiscoveredSymbol(
                name=node.name.value,
                qualname=qualname,
                signature=_render_function_signature(self.module, node),
                file=str(self.file_path),
                line=self.get_metadata(metadata.PositionProvider, node).start.line,
            )
        )
        if self.class_stack:
            class_qualname = ".".join([self.import_path, *self.class_stack])
            class_info = self.classes.get(class_qualname)
            if class_info is not None:
                class_info.methods.add(node.name.value)

        self.function_stack.append(node.name.value)
        if node.name.value == "__init__" and self.class_stack:
            self._current_init_params = {
                param.name.value: _annotation_name(param.annotation.annotation) if param.annotation else None
                for param in node.params.params
            }
        else:
            self._current_init_params = None

    def leave_FunctionDef(self, original_node: cst.FunctionDef) -> None:
        self.function_stack.pop()
        self._current_init_params = None

    def visit_Assign(self, node: cst.Assign) -> None:
        if not self.class_stack or self._current_init_params is None:
            return
        if len(node.targets) != 1:
            return
        target = node.targets[0].target
        target_attr = _self_attribute_name(target)
        if target_attr is None:
            return
        source_name = _expression_name(node.value)
        if source_name is None:
            return
        class_qualname = ".".join([self.import_path, *self.class_stack])
        class_info = self.classes.get(class_qualname)
        if class_info is None:
            return
        class_info.assignments.append(
            _AssignmentRecord(target_attr=target_attr, source_name=source_name)
        )


class _CallCollector(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (metadata.PositionProvider,)

    def __init__(self, module_info: _ModuleInfo, resolver: _QualifiedResolver):
        self.module_info = module_info
        self.resolver = resolver
        self.calls: list[_DiscoveredCall] = []
        self.class_stack: list[str] = []
        self.function_stack: list[str] = []
        self.local_bindings: list[dict[str, _ResolvedValue]] = []

    @property
    def current_scope(self) -> str:
        parts = [self.module_info.import_path, *self.class_stack, *self.function_stack]
        return ".".join(parts)

    def visit_ClassDef(self, node: cst.ClassDef) -> None:
        self.class_stack.append(node.name.value)

    def leave_ClassDef(self, original_node: cst.ClassDef) -> None:
        self.class_stack.pop()

    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:
        self.function_stack.append(node.name.value)
        bindings: dict[str, _ResolvedValue] = {}
        if self.class_stack and node.params.params:
            first = node.params.params[0].name.value
            bindings[first] = _ResolvedValue(
                path=".".join([self.module_info.import_path, *self.class_stack]),
                kind="instance",
                confidence="self_binding",
            )
        for param in node.params.params:
            if param.annotation is None:
                continue
            annotation_path = self.resolver.resolve_annotation(self.module_info, param.annotation)
            if annotation_path is None:
                continue
            bindings[param.name.value] = _ResolvedValue(
                path=annotation_path,
                kind="instance",
                confidence="annotated_param",
            )
        self.local_bindings.append(bindings)

    def leave_FunctionDef(self, original_node: cst.FunctionDef) -> None:
        self.function_stack.pop()
        self.local_bindings.pop()

    def visit_Assign(self, node: cst.Assign) -> None:
        if not self.local_bindings or len(node.targets) != 1:
            return
        target = node.targets[0].target
        if not isinstance(target, cst.Name):
            return
        resolved_value = self._resolve_expression_value(node.value)
        if resolved_value is not None:
            self.local_bindings[-1][target.value] = resolved_value

    def visit_AnnAssign(self, node: cst.AnnAssign) -> None:
        if not self.local_bindings or not isinstance(node.target, cst.Name):
            return
        annotation_path = self.resolver.resolve_annotation(self.module_info, node.annotation)
        if annotation_path is None:
            return
        self.local_bindings[-1][node.target.value] = _ResolvedValue(
            path=annotation_path,
            kind="instance",
            confidence="annotated_local",
        )

    def visit_Call(self, node: cst.Call) -> None:
        if not self.function_stack:
            source = self.module_info.import_path
        else:
            source = self.current_scope
        raw_target = _expression_name(node.func)
        if raw_target is None:
            return
        resolved = self._resolve_callable(node.func)
        if resolved is None:
            target = self._fallback_target(raw_target)
            confidence = "unresolved"
        else:
            target = resolved.path
            confidence = resolved.confidence

        self.calls.append(
            _DiscoveredCall(
                source=source,
                target=target,
                raw_target=raw_target,
                file=str(self.module_info.file_path),
                line=self.get_metadata(metadata.PositionProvider, node).start.line,
                confidence=confidence,
            )
        )

    def _resolve_callable(self, node: cst.BaseExpression) -> _ResolvedValue | None:
        if isinstance(node, cst.Name):
            return self._resolve_name(node.value, allow_local_guess=True)
        if isinstance(node, cst.Attribute):
            base_value = self._resolve_expression_value(node.value)
            if base_value is None:
                return None
            return self._resolve_attribute(base_value, node.attr.value)
        if isinstance(node, cst.Call):
            return self._resolve_callable(node.func)
        return None

    def _resolve_expression_value(self, node: cst.BaseExpression) -> _ResolvedValue | None:
        if isinstance(node, cst.Name):
            return self._resolve_name(node.value, allow_local_guess=False)
        if isinstance(node, cst.Attribute):
            base = self._resolve_expression_value(node.value)
            if base is None:
                return None
            return self._resolve_attribute(base, node.attr.value)
        if isinstance(node, cst.Call):
            callee = self._resolve_callable(node.func)
            if callee is None:
                return None
            canonical = self.resolver.canonicalize(callee.path)
            if canonical in self.resolver.class_infos:
                return _ResolvedValue(path=canonical, kind="instance", confidence=callee.confidence)
            return None
        return None

    def _resolve_name(self, name: str, *, allow_local_guess: bool) -> _ResolvedValue | None:
        for scope in reversed(self.local_bindings):
            if name in scope:
                return scope[name]

        imported = self.module_info.imports.get(name)
        if imported is not None:
            canonical = self.resolver.canonicalize(imported)
            kind = "module"
            if canonical in self.resolver.class_infos:
                kind = "class"
            elif canonical in self.resolver.method_symbols:
                kind = "callable"
            return _ResolvedValue(path=canonical, kind=kind, confidence="resolved_import")

        if self.class_stack:
            class_qualname = ".".join([self.module_info.import_path, *self.class_stack])
            class_info = self.resolver.class_infos.get(class_qualname)
            if class_info and name in class_info.methods:
                return _ResolvedValue(
                    path=f"{class_qualname}.{name}",
                    kind="callable",
                    confidence="resolved_self_method",
                )

        if allow_local_guess and "." not in name:
            return _ResolvedValue(
                path=f"{self.module_info.import_path}.{name}",
                kind="callable",
                confidence="local_import_path_guess",
            )
        return None

    def _resolve_attribute(self, base: _ResolvedValue, attr: str) -> _ResolvedValue | None:
        canonical_base = self.resolver.canonicalize(base.path)
        class_info = self.resolver.class_infos.get(canonical_base)
        if class_info is not None:
            if attr in class_info.attr_types:
                attr_type = self.resolver.canonicalize(class_info.attr_types[attr])
                return _ResolvedValue(path=attr_type, kind="instance", confidence="resolved_attr_type")
            if attr in class_info.methods:
                return _ResolvedValue(
                    path=f"{canonical_base}.{attr}",
                    kind="callable",
                    confidence="resolved_attr_method",
                )

        candidate = self.resolver.canonicalize(f"{canonical_base}.{attr}")
        if candidate in self.resolver.class_infos:
            return _ResolvedValue(path=candidate, kind="class", confidence="resolved_import")
        if candidate in self.resolver.method_symbols:
            return _ResolvedValue(path=candidate, kind="callable", confidence="resolved_import")
        return _ResolvedValue(path=candidate, kind="unknown", confidence="unresolved")

    def _fallback_target(self, raw_target: str) -> str:
        if raw_target.startswith("self.") and self.class_stack:
            parts = raw_target.split(".")
            if len(parts) > 1:
                class_scope = ".".join([self.module_info.import_path, *self.class_stack])
                return f"{class_scope}.{parts[-1]}"
        parts = raw_target.split(".")
        if len(parts) == 1:
            return f"{self.module_info.import_path}.{raw_target}"
        return raw_target


def _build_module_info(file_path: Path, source_root: Path) -> _ModuleInfo | None:
    import_path = _path_to_import_path(source_root, file_path)
    try:
        source = file_path.read_text(encoding="utf-8")
        module = cst.parse_module(source)
    except (OSError, cst.ParserSyntaxError):
        return None

    wrapper = metadata.MetadataWrapper(module)
    collector = _ModuleModelCollector(module, file_path.resolve(), import_path)
    wrapper.visit(collector)
    return _ModuleInfo(
        import_path=import_path,
        file_path=file_path.resolve(),
        source_root=source_root,
        imports=collector.imports,
        symbols=collector.symbols,
        calls=[],
        classes=collector.classes,
    )


def _hydrate_class_assignments(modules: dict[str, _ModuleInfo], resolver: _QualifiedResolver) -> None:
    for module in modules.values():
        for class_info in module.classes.values():
            for assignment in class_info.assignments:
                source_type = class_info.attr_types.get(assignment.source_name)
                if source_type is not None:
                    class_info.attr_types[assignment.target_attr] = resolver.canonicalize(source_type)
                    continue
                imported = module.imports.get(assignment.source_name)
                if imported is not None:
                    class_info.attr_types[assignment.target_attr] = resolver.canonicalize(imported)


def _collect_calls(modules: dict[str, _ModuleInfo], resolver: _QualifiedResolver) -> None:
    for module in modules.values():
        source = module.file_path.read_text(encoding="utf-8")
        wrapper = metadata.MetadataWrapper(cst.parse_module(source))
        collector = _CallCollector(module, resolver)
        wrapper.visit(collector)
        module.calls = collector.calls


def _path_to_import_path(source_root: Path, file_path: Path) -> str:
    rel = file_path.relative_to(source_root).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    if not parts:
        return source_root.name
    return ".".join(parts)


def _render_class_signature(module: cst.Module, node: cst.ClassDef) -> str:
    if not node.bases:
        return f"class {node.name.value}"
    bases = ", ".join(module.code_for_node(base.value).strip() for base in node.bases)
    return f"class {node.name.value}({bases})"


def _render_function_signature(module: cst.Module, node: cst.FunctionDef) -> str:
    prefix = "async def" if node.asynchronous is not None else "def"
    args = module.code_for_node(node.params)
    returns = ""
    if node.returns is not None:
        returns = f" -> {module.code_for_node(node.returns.annotation).strip()}"
    return f"{prefix} {node.name.value}{args}{returns}"


def _expression_name(node: cst.CSTNode | None) -> str | None:
    if node is None:
        return None
    if isinstance(node, cst.Name):
        return node.value
    if isinstance(node, cst.Attribute):
        base = _expression_name(node.value)
        if base:
            return f"{base}.{node.attr.value}"
        return node.attr.value
    if isinstance(node, cst.Call):
        return _expression_name(node.func)
    if isinstance(node, cst.Annotation):
        return _expression_name(node.annotation)
    return None


def _annotation_name(node: cst.CSTNode | None) -> str | None:
    return _expression_name(node)


def _self_attribute_name(node: cst.CSTNode) -> str | None:
    if not isinstance(node, cst.Attribute):
        return None
    if not isinstance(node.value, cst.Name) or node.value.value != "self":
        return None
    return node.attr.value


def _resolve_import_from_module(
    import_path: str,
    module: cst.BaseExpression | None,
    relative: tuple[cst.Dot, ...] | None,
) -> str | None:
    module_name = _expression_name(module)
    level = len(relative or ())
    if level <= 0:
        return module_name

    package_parts = import_path.split(".")
    if package_parts:
        package_parts = package_parts[:-1]

    if level > 1:
        package_parts = package_parts[: max(len(package_parts) - (level - 1), 0)]

    resolved_parts = [*package_parts]
    if module_name:
        resolved_parts.extend(module_name.split("."))
    return ".".join(resolved_parts)


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
    """LibCST-based analyzer for Python projects."""

    def analyze(self, root: Path, config: AnalyzerConfig) -> Project:
        root = root.resolve()
        source_roots = config.resolved_source_roots(root)
        modules: dict[str, _ModuleInfo] = {}

        for file_path in _discover_python_files(root):
            if config.should_ignore_file(root, file_path):
                continue
            source_root = _source_root_for_file(file_path, source_roots)
            if source_root is None:
                continue
            module_info = _build_module_info(file_path, source_root)
            if module_info is None:
                continue
            modules[module_info.import_path] = module_info

        resolver = _QualifiedResolver(modules)
        _hydrate_class_assignments(modules, resolver)
        _collect_calls(modules, resolver)

        method_to_file: dict[str, str] = {}
        import_path_to_file: dict[str, str] = {}
        import_path_to_source_root: dict[str, Path] = {}
        file_symbols: dict[str, list[_DiscoveredSymbol]] = {}
        file_calls: dict[str, list[_DiscoveredCall]] = {}

        for import_path, module in modules.items():
            import_path_to_file[import_path] = str(module.file_path)
            import_path_to_source_root[import_path] = module.source_root
            file_symbols[import_path] = module.symbols
            file_calls[import_path] = module.calls
            for symbol in module.symbols:
                method_to_file[symbol.qualname] = str(module.file_path)

        internal_symbols = set(method_to_file)
        source_files: list[SourceFile] = []
        all_references: list[MethodReference] = []

        for import_path, symbols in file_symbols.items():
            source_root = import_path_to_source_root[import_path]
            file_path = import_path_to_file[import_path]
            methods = [
                Method(
                    name=symbol.name,
                    qualname=symbol.qualname,
                    signature=symbol.signature,
                    line=symbol.line,
                )
                for symbol in symbols
            ]

            for edge in file_calls.get(import_path, []):
                if edge.target not in internal_symbols and not config.include_external_references:
                    continue
                all_references.append(
                    MethodReference(
                        source_method=edge.source if edge.source != import_path else None,
                        target_method=edge.target,
                        file_path=edge.file,
                        line=edge.line,
                    )
                )

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
            references=all_references,
        )
