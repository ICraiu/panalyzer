from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import subprocess
import time

from ..diagram_document_adapter import DiagramDocumentAdapter
from ..graph_adapter import GraphDocumentAdapter, _method_display_label
from ..models import (
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
    Method,
    MethodReference,
    Package,
    Project,
    ProposalDocument,
    ProposalFile,
    ProposalMethod,
    ProposalPackage,
    ProposalReference,
    ProposalSaveResult,
    ProposalState,
    ProposalSummary,
    ValidationIssue,
    ValidationResult,
)
from ..presentation import node_id


ReferenceKey = tuple[str, str, str]


class ProposalApplicationError(Exception):
    def __init__(self, code: str, message: str, errors: list[ValidationIssue] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.errors = errors or []


@dataclass(frozen=True)
class FileInfo:
    relative_path: str
    path: str
    import_path: str
    package_name: str
    methods: tuple[str, ...]


@dataclass(frozen=True)
class MethodInfo:
    qualname: str
    name: str
    signature: str
    line: int
    file_relative_path: str
    package_name: str


@dataclass(frozen=True)
class ProjectIndex:
    packages: dict[str, Package]
    package_paths: dict[str, str]
    files: dict[str, FileInfo]
    methods: dict[str, MethodInfo]
    references: set[ReferenceKey]
    outgoing: dict[str, set[ReferenceKey]]
    incoming: dict[str, set[ReferenceKey]]
    package_files: dict[str, set[str]]


class ProposalStore:
    def __init__(self, root: Path):
        self.root = root

    def save(self, project_id: str, proposal: ProposalDocument) -> Path:
        project_dir = self.root / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        path = project_dir / _proposal_filename(proposal, time.time_ns())
        path.write_text(proposal.model_dump_json(indent=2), encoding="utf-8")
        return path

    def latest(self, project_id: str) -> ProposalDocument | None:
        project_dir = self.root / project_id
        if not project_dir.exists():
            return None
        files = sorted(
            [path for path in project_dir.iterdir() if path.is_file() and path.suffix == ".json"],
            key=lambda path: path.name,
        )
        if not files:
            return None
        payload = json.loads(files[-1].read_text(encoding="utf-8"))
        return ProposalDocument.model_validate(payload)


class ProjectShaResolver:
    def current_sha(self, project_root: Path) -> str:
        result = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip() or "unable to resolve git SHA"
            raise ProposalApplicationError(
                "project_sha_unavailable",
                f"Could not determine git SHA for {project_root}: {stderr}",
                errors=[
                    ValidationIssue(
                        code="project_sha_unavailable",
                        path="project_sha",
                        message=f"Could not determine git SHA for {project_root}: {stderr}",
                    )
                ],
            )
        return result.stdout.strip()


class ProposalValidator:
    def validate(self, project: Project, proposal: ProposalDocument) -> ValidationResult:
        index = build_project_index(project)
        errors: list[ValidationIssue] = []
        warnings: list[ValidationIssue] = []

        package_states = {item.name: item.iteration_state for item in proposal.packages}
        file_states = {item.relative_path: item.iteration_state for item in proposal.files}
        method_states = {item.qualname: item.iteration_state for item in proposal.methods}
        reference_states = {
            (item.source_method, item.target_method, item.file_relative_path): item.iteration_state
            for item in proposal.references
        }
        proposal_files = {item.relative_path: item for item in proposal.files}
        proposal_methods = {item.qualname: item for item in proposal.methods}

        self._check_duplicates(proposal, errors)

        for idx, package in enumerate(proposal.packages):
            package_path = _validate_relative_project_path(package.relative_path, f"packages[{idx}]", errors)
            exists = package.name in index.packages
            self._check_existence(
                exists=exists,
                state=package.iteration_state,
                noun="package",
                identity=package.name,
                path=f"packages[{idx}]",
                errors=errors,
            )
            if exists and package_path is not None and package_path != index.package_paths[package.name]:
                errors.append(
                    ValidationIssue(
                        code="package_relative_path_mismatch",
                        path=f"packages[{idx}]",
                        message=f"Existing package '{package.name}' must use relative path '{index.package_paths[package.name]}'.",
                    )
                )

        for idx, source_file in enumerate(proposal.files):
            _validate_relative_project_path(source_file.relative_path, f"files[{idx}].relative_path", errors)
            exists = source_file.relative_path in index.files
            self._check_existence(
                exists=exists,
                state=source_file.iteration_state,
                noun="file",
                identity=source_file.relative_path,
                path=f"files[{idx}]",
                errors=errors,
            )
            if source_file.package_name not in package_states:
                errors.append(
                    ValidationIssue(
                        code="missing_parent_package_declaration",
                        path=f"files[{idx}]",
                        message=f"File '{source_file.relative_path}' requires an explicit package declaration for '{source_file.package_name}'.",
                    )
                )
            if exists:
                actual = index.files[source_file.relative_path]
                if source_file.package_name != actual.package_name:
                    errors.append(
                        ValidationIssue(
                            code="file_package_mismatch",
                            path=f"files[{idx}]",
                            message=f"Existing file '{source_file.relative_path}' belongs to package '{actual.package_name}', not '{source_file.package_name}'.",
                        )
                    )
                if source_file.import_path != actual.import_path:
                    errors.append(
                        ValidationIssue(
                            code="file_import_path_mismatch",
                            path=f"files[{idx}]",
                            message=f"Existing file '{source_file.relative_path}' must use import path '{actual.import_path}'.",
                        )
                    )

        for idx, method in enumerate(proposal.methods):
            _validate_relative_project_path(method.file_relative_path, f"methods[{idx}].file_relative_path", errors)
            exists = method.qualname in index.methods
            self._check_existence(
                exists=exists,
                state=method.iteration_state,
                noun="method",
                identity=method.qualname,
                path=f"methods[{idx}]",
                errors=errors,
            )
            if method.file_relative_path not in file_states:
                errors.append(
                    ValidationIssue(
                        code="missing_parent_file_declaration",
                        path=f"methods[{idx}]",
                        message=f"Method '{method.qualname}' requires an explicit file declaration for '{method.file_relative_path}'.",
                    )
                )
            if exists:
                actual = index.methods[method.qualname]
                if method.file_relative_path != actual.file_relative_path:
                    errors.append(
                        ValidationIssue(
                            code="method_file_mismatch",
                            path=f"methods[{idx}]",
                            message=f"Existing method '{method.qualname}' belongs to file '{actual.file_relative_path}', not '{method.file_relative_path}'.",
                        )
                    )

        for idx, reference in enumerate(proposal.references):
            _validate_relative_project_path(reference.file_relative_path, f"references[{idx}].file_relative_path", errors)
            ref_key = (reference.source_method, reference.target_method, reference.file_relative_path)
            exists = ref_key in index.references
            self._check_existence(
                exists=exists,
                state=reference.iteration_state,
                noun="reference",
                identity=" -> ".join(ref_key[:2]),
                path=f"references[{idx}]",
                errors=errors,
            )
            source_state = method_states.get(reference.source_method)
            target_state = method_states.get(reference.target_method)
            source_exists = reference.source_method in index.methods
            target_exists = reference.target_method in index.methods

            if source_state is None:
                errors.append(
                    ValidationIssue(
                        code="missing_source_method_declaration",
                        path=f"references[{idx}]",
                        message=f"Reference '{reference.source_method} -> {reference.target_method}' requires an explicit declaration for source method '{reference.source_method}'.",
                    )
                )
            if source_state == ProposalState.REMOVE and reference.iteration_state != ProposalState.REMOVE:
                errors.append(
                    ValidationIssue(
                        code="removed_source_requires_removed_reference",
                        path=f"references[{idx}]",
                        message=f"Reference '{reference.source_method} -> {reference.target_method}' must be 'remove' because the source method is removed.",
                    )
                )
            if source_state == ProposalState.ADD and reference.iteration_state != ProposalState.ADD:
                errors.append(
                    ValidationIssue(
                        code="new_source_requires_added_reference",
                        path=f"references[{idx}]",
                        message=f"Reference '{reference.source_method} -> {reference.target_method}' must be 'add' because the source method is new.",
                    )
                )

            if reference.iteration_state == ProposalState.ADD:
                if source_state not in {ProposalState.ADD, ProposalState.CHANGE}:
                    errors.append(
                        ValidationIssue(
                            code="invalid_source_state_for_added_reference",
                            path=f"references[{idx}]",
                            message=f"Added reference '{reference.source_method} -> {reference.target_method}' requires source method state 'add' or 'change'.",
                        )
                    )
                if target_state == ProposalState.REMOVE:
                    errors.append(
                        ValidationIssue(
                            code="invalid_target_state_for_added_reference",
                            path=f"references[{idx}]",
                            message=f"Added reference '{reference.source_method} -> {reference.target_method}' cannot target a removed method.",
                        )
                    )
                if not target_exists and target_state != ProposalState.ADD:
                    errors.append(
                        ValidationIssue(
                            code="missing_target_method_for_added_reference",
                            path=f"references[{idx}]",
                            message=f"Added reference '{reference.source_method} -> {reference.target_method}' requires the target method to exist or be declared 'add'.",
                        )
                    )
            elif reference.iteration_state == ProposalState.CHANGE:
                if source_state != ProposalState.CHANGE:
                    errors.append(
                        ValidationIssue(
                            code="changed_reference_requires_changed_source",
                            path=f"references[{idx}]",
                            message=f"Changed reference '{reference.source_method} -> {reference.target_method}' requires source method state 'change'.",
                        )
                    )
                if target_state != ProposalState.CHANGE:
                    errors.append(
                        ValidationIssue(
                            code="changed_reference_requires_changed_target",
                            path=f"references[{idx}]",
                            message=f"Changed reference '{reference.source_method} -> {reference.target_method}' requires target method state 'change'.",
                        )
                    )
                if source_exists and target_exists:
                    warnings.append(
                        ValidationIssue(
                            code="reference_change_requires_signature_adaptation_confirmation",
                            path=f"references[{idx}]",
                            message=f"Reference '{reference.source_method} -> {reference.target_method}' is marked 'change'. Confirm this means signature adaptation rather than a broader behavioral rewrite.",
                        )
                    )
            elif reference.iteration_state == ProposalState.REMOVE:
                if source_state not in {ProposalState.CHANGE, ProposalState.REMOVE}:
                    errors.append(
                        ValidationIssue(
                            code="invalid_source_state_for_removed_reference",
                            path=f"references[{idx}]",
                            message=f"Removed reference '{reference.source_method} -> {reference.target_method}' requires source method state 'change' or 'remove'.",
                        )
                    )
                if not exists:
                    errors.append(
                        ValidationIssue(
                            code="missing_existing_reference_for_remove",
                            path=f"references[{idx}]",
                            message=f"Reference '{reference.source_method} -> {reference.target_method}' cannot be removed because it does not exist.",
                        )
                    )

            if not source_exists and source_state != ProposalState.ADD:
                errors.append(
                    ValidationIssue(
                        code="missing_source_method_for_reference",
                        path=f"references[{idx}]",
                        message=f"Reference '{reference.source_method} -> {reference.target_method}' requires source method to exist or be declared 'add'.",
                    )
                )
            if not target_exists and target_state != ProposalState.ADD:
                errors.append(
                    ValidationIssue(
                        code="missing_target_method_for_reference",
                        path=f"references[{idx}]",
                        message=f"Reference '{reference.source_method} -> {reference.target_method}' requires target method to exist or be declared 'add'.",
                    )
                )

        for idx, source_file in enumerate(proposal.files):
            child_states = {
                method.iteration_state
                for method in proposal.methods
                if method.file_relative_path == source_file.relative_path
            }
            outgoing_reference_states = {
                reference.iteration_state
                for reference in proposal.references
                if _reference_source_file(reference, index, proposal_methods) == source_file.relative_path
            }
            if source_file.iteration_state == ProposalState.ADD:
                if child_states and child_states != {ProposalState.ADD}:
                    errors.append(
                        ValidationIssue(
                            code="invalid_child_state_for_added_file",
                            path=f"files[{idx}]",
                            message=f"Added file '{source_file.relative_path}' may contain only added methods.",
                        )
                    )
            elif source_file.iteration_state == ProposalState.REMOVE:
                existing_methods = set(index.files.get(source_file.relative_path, FileInfo("", "", "", "", tuple())).methods)
                removed_methods = {
                    method.qualname
                    for method in proposal.methods
                    if method.file_relative_path == source_file.relative_path
                    and method.iteration_state == ProposalState.REMOVE
                }
                missing_methods = existing_methods - removed_methods
                if missing_methods:
                    errors.append(
                        ValidationIssue(
                            code="missing_removed_method_for_removed_file",
                            path=f"files[{idx}]",
                            message=f"Removed file '{source_file.relative_path}' is missing explicit removed methods: {', '.join(sorted(missing_methods))}.",
                        )
                    )
            elif source_file.iteration_state == ProposalState.CHANGE:
                if not child_states and not outgoing_reference_states:
                    errors.append(
                        ValidationIssue(
                            code="empty_changed_file",
                            path=f"files[{idx}]",
                            message=f"Changed file '{source_file.relative_path}' must contain changed methods or outgoing reference changes.",
                        )
                    )
                elif child_states and child_states in ({ProposalState.ADD}, {ProposalState.REMOVE}):
                    errors.append(
                        ValidationIssue(
                            code="invalid_changed_file_state_family",
                            path=f"files[{idx}]",
                            message=f"Changed file '{source_file.relative_path}' cannot be a pure '{next(iter(child_states)).value}' child set.",
                        )
                    )

        for idx, package in enumerate(proposal.packages):
            child_file_states = {
                source_file.iteration_state
                for source_file in proposal.files
                if source_file.package_name == package.name
            }
            if package.iteration_state == ProposalState.ADD:
                if child_file_states and child_file_states != {ProposalState.ADD}:
                    errors.append(
                        ValidationIssue(
                            code="invalid_child_state_for_added_package",
                            path=f"packages[{idx}]",
                            message=f"Added package '{package.name}' may contain only added files.",
                        )
                    )
            elif package.iteration_state == ProposalState.REMOVE:
                existing_files = index.package_files.get(package.name, set())
                removed_files = {
                    source_file.relative_path
                    for source_file in proposal.files
                    if source_file.package_name == package.name
                    and source_file.iteration_state == ProposalState.REMOVE
                }
                missing_files = existing_files - removed_files
                if missing_files:
                    errors.append(
                        ValidationIssue(
                            code="missing_removed_file_for_removed_package",
                            path=f"packages[{idx}]",
                            message=f"Removed package '{package.name}' is missing explicit removed files: {', '.join(sorted(missing_files))}.",
                        )
                    )
            elif package.iteration_state == ProposalState.CHANGE:
                if not child_file_states:
                    errors.append(
                        ValidationIssue(
                            code="invalid_changed_package",
                            path=f"packages[{idx}]",
                            message=f"Changed package '{package.name}' must contain at least one changed or removed file.",
                        )
                    )
                elif ProposalState.CHANGE not in child_file_states:
                    errors.append(
                        ValidationIssue(
                            code="missing_changed_file_for_changed_package",
                            path=f"packages[{idx}]",
                            message=f"Changed package '{package.name}' must contain at least one file explicitly marked 'change'.",
                        )
                    )

        for method_name, state in method_states.items():
            if state != ProposalState.REMOVE:
                continue
            for ref_key in index.outgoing.get(method_name, set()) | index.incoming.get(method_name, set()):
                if reference_states.get(ref_key) != ProposalState.REMOVE:
                    errors.append(
                        ValidationIssue(
                            code="missing_removed_reference",
                            path=f"methods[{_proposal_method_index(proposal, method_name)}]",
                            message=f"Method '{method_name}' is marked 'remove' but reference '{ref_key[0]} -> {ref_key[1]}' was not explicitly declared 'remove'.",
                        )
                    )

        for target_method, target_state in method_states.items():
            if target_state != ProposalState.CHANGE:
                continue
            for ref_key in index.incoming.get(target_method, set()):
                if reference_states.get(ref_key) is None:
                    warnings.append(
                        ValidationIssue(
                            code="signature_change_may_require_reference_change",
                        path=f"methods[{_proposal_method_index(proposal, target_method)}]",
                        message=f"Target method '{target_method}' changes while incoming reference '{ref_key[0]} -> {ref_key[1]}' remains present. Confirm that no signature adaptation is required.",
                    )
                )

        return ValidationResult(valid=not errors, warnings=_dedupe_issues(warnings), errors=_dedupe_issues(errors))

    def _check_duplicates(self, proposal: ProposalDocument, errors: list[ValidationIssue]) -> None:
        self._find_duplicates([item.name for item in proposal.packages], "packages", "package", errors)
        self._find_duplicates([item.relative_path for item in proposal.files], "files", "file", errors)
        self._find_duplicates([item.qualname for item in proposal.methods], "methods", "method", errors)
        self._find_duplicates(
            [f"{item.source_method}|{item.target_method}|{item.file_relative_path}" for item in proposal.references],
            "references",
            "reference",
            errors,
        )

    def _find_duplicates(
        self,
        values: list[str],
        section: str,
        noun: str,
        errors: list[ValidationIssue],
    ) -> None:
        seen: set[str] = set()
        duplicates: set[str] = set()
        for value in values:
            if value in seen:
                duplicates.add(value)
            seen.add(value)
        for value in sorted(duplicates):
            errors.append(
                ValidationIssue(
                    code=f"duplicate_{noun}",
                    path=section,
                    message=f"Duplicate {noun} identity '{value}' in proposal.",
                )
            )

    def _check_existence(
        self,
        *,
        exists: bool,
        state: ProposalState,
        noun: str,
        identity: str,
        path: str,
        errors: list[ValidationIssue],
    ) -> None:
        if exists and state == ProposalState.ADD:
            errors.append(
                ValidationIssue(
                    code=f"invalid_state_for_existing_{noun}",
                    path=path,
                    message=f"Existing {noun} '{identity}' cannot be proposed with state 'add'.",
                )
            )
        if not exists and state in {ProposalState.CHANGE, ProposalState.REMOVE}:
            errors.append(
                ValidationIssue(
                    code=f"invalid_state_for_missing_{noun}",
                    path=path,
                    message=f"Missing {noun} '{identity}' cannot be proposed with state '{state.value}'.",
                )
            )


class ProposalGraphService:
    def to_graph(self, project: Project, proposal: ProposalDocument, validation: ValidationResult) -> GraphDocument:
        index = build_project_index(project)
        package_states = _build_package_states(index, proposal)
        file_states = _build_file_states(index, proposal)
        method_states = _build_method_states(index, proposal)
        reference_states = _build_reference_states(index, proposal)

        package_names = sorted(set(index.packages) | {item.name for item in proposal.packages})
        file_paths = sorted(set(index.files) | {item.relative_path for item in proposal.files})
        method_names = sorted(set(index.methods) | {item.qualname for item in proposal.methods})

        file_proposals = {item.relative_path: item for item in proposal.files}
        method_proposals = {item.qualname: item for item in proposal.methods}
        package_proposals = {item.name: item for item in proposal.packages}

        nodes: list[GraphPackageNode | GraphFileNode | GraphMethodNode] = []
        package_node_ids: dict[str, str] = {}
        file_node_ids: dict[str, str] = {}
        method_node_ids: dict[str, str] = {}

        for package_name in package_names:
            package = index.packages.get(package_name)
            package_proposal = package_proposals.get(package_name)
            package_path = package.path if package else str((Path(project.root) / package_proposal.relative_path).resolve())
            package_id = node_id("pkg", package_name)
            package_node_ids[package_name] = package_id
            nodes.append(
                GraphPackageNode(
                    id=package_id,
                    label=package_name,
                    path=package_path,
                    iteration_state=package_states[package_name],
                )
            )

        for file_relative_path in file_paths:
            info = index.files.get(file_relative_path)
            proposal_file = file_proposals.get(file_relative_path)
            import_path = info.import_path if info else proposal_file.import_path
            package_name = info.package_name if info else proposal_file.package_name
            file_path = info.path if info else str((Path(project.root) / file_relative_path).resolve())
            file_id = node_id("file", import_path)
            file_node_ids[file_relative_path] = file_id
            nodes.append(
                GraphFileNode(
                    id=file_id,
                    label=import_path,
                    parent_id=package_node_ids[package_name],
                    path=file_path,
                    import_path=import_path,
                    iteration_state=file_states[file_relative_path],
                )
            )

        for method_name in method_names:
            info = index.methods.get(method_name)
            proposal_method = method_proposals.get(method_name)
            if info:
                method = Method(
                    name=info.name,
                    qualname=info.qualname,
                    signature=proposal_method.signature or info.signature if proposal_method else info.signature,
                    line=proposal_method.line or info.line if proposal_method else info.line,
                )
                file_relative_path = info.file_relative_path
                import_path = index.files[file_relative_path].import_path
                file_path = index.files[file_relative_path].path
            else:
                method = Method(
                    name=proposal_method.name,
                    qualname=proposal_method.qualname,
                    signature=proposal_method.signature or f"def {proposal_method.name}(...)",
                    line=proposal_method.line or 0,
                )
                file_relative_path = proposal_method.file_relative_path
                import_path = file_proposals[file_relative_path].import_path
                file_path = str((Path(project.root) / file_relative_path).resolve())
            method_id = node_id("method", method.qualname)
            method_node_ids[method.qualname] = method_id
            nodes.append(
                GraphMethodNode(
                    id=method_id,
                    label=_method_display_label(method.name, method.signature, method.line),
                    parent_id=file_node_ids[file_relative_path],
                    path=file_path,
                    import_path=import_path,
                    qualname=method.qualname,
                    signature=method.signature,
                    line=method.line,
                    iteration_state=method_states[method.qualname],
                )
            )

        project_references_by_key: dict[ReferenceKey, list[MethodReference]] = {}
        for reference in project.references:
            if reference.source_method is None:
                continue
            source_method = index.methods.get(reference.source_method)
            if source_method is None:
                continue
            key = (reference.source_method, reference.target_method, source_method.file_relative_path)
            project_references_by_key.setdefault(key, []).append(reference)

        edges: list[GraphEdge] = []
        seen_ids: set[str] = set()
        for ref_key, refs in project_references_by_key.items():
            source_method, target_method, _ = ref_key
            if source_method not in method_node_ids or target_method not in method_node_ids:
                continue
            state = reference_states.get(ref_key, IterationState.PRESENT)
            for reference in refs:
                edge_id = f"{method_node_ids[source_method]}:{method_node_ids[target_method]}:{reference.line}"
                if edge_id in seen_ids:
                    continue
                seen_ids.add(edge_id)
                edges.append(
                    GraphEdge(
                        id=edge_id,
                        source_id=method_node_ids[source_method],
                        target_id=method_node_ids[target_method],
                        line=reference.line,
                        iteration_state=state,
                    )
                )

        for reference in proposal.references:
            ref_key = (reference.source_method, reference.target_method, reference.file_relative_path)
            if ref_key in project_references_by_key:
                continue
            if reference.source_method not in method_node_ids or reference.target_method not in method_node_ids:
                continue
            edge_id = f"{method_node_ids[reference.source_method]}:{method_node_ids[reference.target_method]}:proposal"
            if edge_id in seen_ids:
                continue
            seen_ids.add(edge_id)
            edges.append(
                GraphEdge(
                    id=edge_id,
                    source_id=method_node_ids[reference.source_method],
                    target_id=method_node_ids[reference.target_method],
                    line=0,
                    iteration_state=reference_states[ref_key],
                )
            )

        return GraphDocument(
            root=project.root,
            summary=GraphSummary(
                package_count=len(package_names),
                file_count=len(file_paths),
                method_count=len(method_names),
                edge_count=len(edges),
            ),
            nodes=sorted(nodes, key=lambda item: item.id),
            edges=sorted(edges, key=lambda item: item.id),
            active_proposal=ProposalSummary(
                id=proposal.id,
                name=proposal.name,
                created_at=proposal.created_at,
                author=proposal.author,
                source_model=proposal.source_model,
                rationale=proposal.rationale,
                project_sha=proposal.project_sha,
                validation=validation,
            ),
            warnings=validation.warnings,
        )

    def to_diagram(self, graph: GraphDocument) -> DiagramDocument:
        return DiagramDocumentAdapter().to_document_from_graph(graph)


class ProposalService:
    def __init__(self, store: ProposalStore, sha_resolver: ProjectShaResolver | None = None):
        self.store = store
        self.sha_resolver = sha_resolver or ProjectShaResolver()
        self.validator = ProposalValidator()
        self.graph_service = ProposalGraphService()

    def save(
        self,
        *,
        project_id: str,
        project_root: Path,
        project: Project,
        payload: dict,
    ) -> ProposalSaveResult:
        proposal = ProposalDocument.model_validate(payload)
        validation = self.validator.validate(project, proposal)
        validation = self._with_sha_validation(validation, proposal, project_root)
        self.store.save(project_id, proposal)
        return ProposalSaveResult(proposal=proposal, validation=validation)

    def load_latest(self, project_id: str) -> ProposalDocument | None:
        return self.store.latest(project_id)

    def analyze_with_latest(
        self,
        *,
        project_id: str,
        project_root: Path,
        project: Project,
    ) -> tuple[GraphDocument, DiagramDocument]:
        proposal = self.store.latest(project_id)
        if proposal is None:
            graph = GraphDocumentAdapter().to_document(project)
            diagram = DiagramDocumentAdapter().to_document_from_graph(graph)
            return graph, diagram

        current_sha = self.sha_resolver.current_sha(project_root)
        if proposal.project_sha != current_sha:
            issue = ValidationIssue(
                code="project_sha_mismatch",
                path="project_sha",
                message=f"Proposal '{proposal.id}' targets SHA '{proposal.project_sha}' but project is at '{current_sha}'.",
            )
            raise ProposalApplicationError(issue.code, issue.message, errors=[issue])

        validation = self.validator.validate(project, proposal)
        if not validation.valid:
            raise ProposalApplicationError(
                "invalid_latest_proposal",
                f"Latest proposal '{proposal.id}' is invalid and cannot be applied.",
                errors=validation.errors,
            )

        graph = self.graph_service.to_graph(project, proposal, validation)
        diagram = self.graph_service.to_diagram(graph)
        return graph, diagram

    def _with_sha_validation(
        self,
        validation: ValidationResult,
        proposal: ProposalDocument,
        project_root: Path,
    ) -> ValidationResult:
        errors = list(validation.errors)
        warnings = list(validation.warnings)
        try:
            current_sha = self.sha_resolver.current_sha(project_root)
        except ProposalApplicationError as exc:
            errors.extend(exc.errors)
            return ValidationResult(valid=False, warnings=warnings, errors=_dedupe_issues(errors))
        if proposal.project_sha != current_sha:
            errors.append(
                ValidationIssue(
                    code="project_sha_mismatch",
                    path="project_sha",
                    message=f"Proposal targets SHA '{proposal.project_sha}' but project is at '{current_sha}'.",
                )
            )
        return ValidationResult(valid=not errors, warnings=warnings, errors=_dedupe_issues(errors))


def build_project_index(project: Project) -> ProjectIndex:
    packages: dict[str, Package] = {}
    package_paths: dict[str, str] = {}
    files: dict[str, FileInfo] = {}
    methods: dict[str, MethodInfo] = {}
    outgoing: dict[str, set[ReferenceKey]] = {}
    incoming: dict[str, set[ReferenceKey]] = {}
    references: set[ReferenceKey] = set()
    package_files: dict[str, set[str]] = {}

    for package in project.packages:
        packages[package.name] = package
        package_paths[package.name] = _relative_path(package.path, project.root)
        package_files.setdefault(package.name, set())
        for source_file in package.files:
            relative_path = _relative_path(source_file.path, project.root)
            package_files[package.name].add(relative_path)
            method_names = tuple(method.qualname for method in source_file.methods)
            files[relative_path] = FileInfo(
                relative_path=relative_path,
                path=source_file.path,
                import_path=source_file.import_path,
                package_name=package.name,
                methods=method_names,
            )
            for method in source_file.methods:
                methods[method.qualname] = MethodInfo(
                    qualname=method.qualname,
                    name=method.name,
                    signature=method.signature,
                    line=method.line,
                    file_relative_path=relative_path,
                    package_name=package.name,
                )

    for reference in project.references:
        if reference.source_method is None:
            continue
        source_method = methods.get(reference.source_method)
        if source_method is None:
            continue
        key = (reference.source_method, reference.target_method, source_method.file_relative_path)
        references.add(key)
        outgoing.setdefault(reference.source_method, set()).add(key)
        incoming.setdefault(reference.target_method, set()).add(key)

    return ProjectIndex(
        packages=packages,
        package_paths=package_paths,
        files=files,
        methods=methods,
        references=references,
        outgoing=outgoing,
        incoming=incoming,
        package_files=package_files,
    )


def _reference_source_file(
    reference: ProposalReference,
    index: ProjectIndex,
    proposal_methods: dict[str, ProposalMethod],
) -> str:
    source_info = index.methods.get(reference.source_method)
    if source_info is not None:
        return source_info.file_relative_path
    proposal_method = proposal_methods.get(reference.source_method)
    if proposal_method is not None:
        return proposal_method.file_relative_path
    return reference.file_relative_path


def _proposal_filename(proposal: ProposalDocument, saved_at_ns: int) -> str:
    timestamp = proposal.created_at.replace(":", "").replace("-", "").replace("T", "_").replace("Z", "")
    safe_id = proposal.id.replace("/", "_")
    return f"{saved_at_ns:020d}__{timestamp}__{safe_id}.json"


def _relative_path(path: str, root: str) -> str:
    return str(Path(path).resolve().relative_to(Path(root).resolve()))


def _validate_relative_project_path(
    raw_path: str,
    path: str,
    errors: list[ValidationIssue],
) -> str | None:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        errors.append(
            ValidationIssue(
                code="absolute_path_not_allowed",
                path=path,
                message=f"Path '{raw_path}' must be project-relative.",
            )
        )
        return None
    if raw_path.strip() == "":
        errors.append(
            ValidationIssue(
                code="empty_relative_path",
                path=path,
                message="Relative path must not be empty.",
            )
        )
        return None
    if any(part == ".." for part in candidate.parts):
        errors.append(
            ValidationIssue(
                code="parent_escape_not_allowed",
                path=path,
                message=f"Path '{raw_path}' must not escape the project root.",
            )
        )
        return None
    return candidate.as_posix()


def _proposal_method_index(proposal: ProposalDocument, qualname: str) -> int:
    for index, method in enumerate(proposal.methods):
        if method.qualname == qualname:
            return index
    return 0


def _dedupe_issues(issues: list[ValidationIssue]) -> list[ValidationIssue]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[ValidationIssue] = []
    for issue in issues:
        key = (issue.code, issue.path, issue.message)
        if key in seen:
            continue
        seen.add(key)
        unique.append(issue)
    return unique


def _build_package_states(index: ProjectIndex, proposal: ProposalDocument) -> dict[str, IterationState]:
    states = {name: IterationState.PRESENT for name in index.packages}
    for package in proposal.packages:
        states[package.name] = IterationState(package.iteration_state.value)
    return states


def _build_file_states(index: ProjectIndex, proposal: ProposalDocument) -> dict[str, IterationState]:
    states = {path: IterationState.PRESENT for path in index.files}
    for source_file in proposal.files:
        states[source_file.relative_path] = IterationState(source_file.iteration_state.value)
    return states


def _build_method_states(index: ProjectIndex, proposal: ProposalDocument) -> dict[str, IterationState]:
    states = {name: IterationState.PRESENT for name in index.methods}
    for method in proposal.methods:
        states[method.qualname] = IterationState(method.iteration_state.value)
    return states


def _build_reference_states(index: ProjectIndex, proposal: ProposalDocument) -> dict[ReferenceKey, IterationState]:
    states = {key: IterationState.PRESENT for key in index.references}
    for reference in proposal.references:
        key = (reference.source_method, reference.target_method, reference.file_relative_path)
        states[key] = IterationState(reference.iteration_state.value)
    return states
