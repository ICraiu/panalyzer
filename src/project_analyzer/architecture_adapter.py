from __future__ import annotations

import json

from .models import (
    ArchitectureDocument,
    ArchitectureEdge,
    ArchitectureFileNode,
    ArchitectureMethodNode,
    ArchitecturePackageNode,
    ArchitectureSection,
    ArchitectureSummary,
    Project,
)
from .presentation import display_name, node_id


class ArchitectureDocumentAdapter:
    """Build a GPT-readable architecture document from the domain model."""

    def to_document(self, project: Project) -> ArchitectureDocument:
        node_map: dict[str, ArchitecturePackageNode | ArchitectureFileNode | ArchitectureMethodNode] = {}
        edge_map: dict[str, ArchitectureEdge] = {}
        method_paths: dict[str, str] = {}
        sections: list[ArchitectureSection] = []

        for package in project.packages:
            package_id = node_id("pkg", package.name)
            package_node = ArchitecturePackageNode(
                id=package_id,
                label=package.name,
                path=package.path,
            )
            node_map[package_id] = package_node

            file_sections: list[ArchitectureSection] = []
            file_node_ids: list[str] = []

            for source_file in package.files:
                file_id = node_id("file", source_file.import_path)
                file_node = ArchitectureFileNode(
                    id=file_id,
                    label=source_file.import_path,
                    parent_id=package_id,
                    path=source_file.path,
                    import_path=source_file.import_path,
                )
                node_map[file_id] = file_node
                file_node_ids.append(file_id)

                method_node_ids: list[str] = []
                for method in source_file.methods:
                    method_id = node_id("method", method.qualname)
                    method_label = _method_display_label(method.name, method.signature, method.line)
                    method_node = ArchitectureMethodNode(
                        id=method_id,
                        label=method_label,
                        parent_id=file_id,
                        path=source_file.path,
                        import_path=source_file.import_path,
                        qualname=method.qualname,
                        signature=method.signature,
                        line=method.line,
                    )
                    node_map[method_id] = method_node
                    method_paths[method.qualname] = method_id
                    method_node_ids.append(method_id)

                file_sections.append(
                    ArchitectureSection(
                        id=file_id,
                        kind="file",
                        label=source_file.import_path,
                        node_ids=method_node_ids,
                    )
                )

            sections.append(
                ArchitectureSection(
                    id=package_id,
                    kind="package",
                    label=package.name,
                    node_ids=file_node_ids,
                    child_sections=file_sections,
                )
            )

        line_targets_by_source: dict[tuple[str, int], set[str]] = {}
        for reference in project.references:
            if reference.source_method is None:
                continue
            if reference.target_method not in method_paths:
                continue
            line_targets_by_source.setdefault(
                (reference.source_method, reference.line),
                set(),
            ).add(reference.target_method)

        for reference in project.references:
            if reference.source_method is None:
                continue
            if reference.target_method not in method_paths:
                continue
            if _is_constructor_edge_shadowed(reference, line_targets_by_source):
                continue
            source_id = method_paths.get(reference.source_method)
            target_id = method_paths.get(reference.target_method)
            if source_id is None or target_id is None:
                continue
            edge_id = node_id(
                "edge",
                f"{reference.source_method}:{reference.target_method}:{reference.line}",
            )
            edge_map[edge_id] = ArchitectureEdge(
                id=edge_id,
                source_id=source_id,
                target_id=target_id,
                line=reference.line,
            )

        return ArchitectureDocument(
            root=project.root,
            summary=ArchitectureSummary(
                package_count=len(project.packages),
                file_count=sum(len(package.files) for package in project.packages),
                method_count=sum(
                    len(source_file.methods)
                    for package in project.packages
                    for source_file in package.files
                ),
                internal_call_count=len(edge_map),
            ),
            sections=sections,
            nodes=sorted(node_map.values(), key=lambda item: item.id),
            edges=sorted(edge_map.values(), key=lambda item: item.id),
        )

    def to_json(self, project: Project) -> str:
        document = self.to_document(project)
        return json.dumps(document.model_dump(mode="json"), indent=2)


def _method_display_label(name: str, signature: str, line: int) -> str:
    method_name = display_name(name)
    if signature.startswith("class "):
        return f"class {method_name} | L{line}"
    return f"{method_name}(...) | L{line}"


def _is_constructor_edge_shadowed(
    reference,
    line_targets_by_source: dict[tuple[str, int], set[str]],
) -> bool:
    targets = line_targets_by_source.get((reference.source_method, reference.line), set())
    prefix = f"{reference.target_method}."
    return any(target.startswith(prefix) for target in targets)
