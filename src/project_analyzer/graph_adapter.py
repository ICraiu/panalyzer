from __future__ import annotations

from .models import (
    GraphDocument,
    GraphEdge,
    GraphFileNode,
    GraphMethodNode,
    GraphPackageNode,
    GraphSummary,
    Project,
)
from .presentation import display_name, node_id


class GraphDocumentAdapter:
    """Build interactive graph data from the project domain."""

    def to_document(self, project: Project) -> GraphDocument:
        nodes: list[GraphPackageNode | GraphFileNode | GraphMethodNode] = []
        method_node_ids: dict[str, str] = {}

        for package in project.packages:
            package_id = node_id("pkg", package.name)
            nodes.append(
                GraphPackageNode(
                    id=package_id,
                    label=package.name,
                    path=package.path,
                )
            )

            for source_file in package.files:
                file_id = node_id("file", source_file.import_path)
                nodes.append(
                    GraphFileNode(
                        id=file_id,
                        label=source_file.import_path,
                        parent_id=package_id,
                        path=source_file.path,
                        import_path=source_file.import_path,
                    )
                )

                for method in source_file.methods:
                    method_id = node_id("method", method.qualname)
                    nodes.append(
                        GraphMethodNode(
                            id=method_id,
                            label=_method_display_label(method.name, method.signature, method.line),
                            parent_id=file_id,
                            path=source_file.path,
                            import_path=source_file.import_path,
                            qualname=method.qualname,
                            signature=method.signature,
                            line=method.line,
                        )
                    )
                    method_node_ids[method.qualname] = method_id

        line_targets_by_source: dict[tuple[str, int], set[str]] = {}
        for reference in project.references:
            if reference.source_method is None:
                continue
            if reference.target_method not in method_node_ids:
                continue
            line_targets_by_source.setdefault(
                (reference.source_method, reference.line),
                set(),
            ).add(reference.target_method)

        edges: list[GraphEdge] = []
        seen_edges: set[str] = set()
        for reference in project.references:
            if reference.source_method is None:
                continue
            if reference.target_method not in method_node_ids:
                continue
            if _is_constructor_edge_shadowed(reference, line_targets_by_source):
                continue
            source_id = method_node_ids.get(reference.source_method)
            target_id = method_node_ids.get(reference.target_method)
            if source_id is None or target_id is None:
                continue
            edge_id = f"{source_id}:{target_id}:{reference.line}"
            if edge_id in seen_edges:
                continue
            seen_edges.add(edge_id)
            edges.append(
                GraphEdge(
                    id=edge_id,
                    source_id=source_id,
                    target_id=target_id,
                    line=reference.line,
                )
            )

        return GraphDocument(
            root=project.root,
            summary=GraphSummary(
                package_count=len(project.packages),
                file_count=sum(len(package.files) for package in project.packages),
                method_count=sum(
                    len(source_file.methods)
                    for package in project.packages
                    for source_file in package.files
                ),
                edge_count=len(edges),
            ),
            nodes=sorted(nodes, key=lambda item: item.id),
            edges=edges,
        )


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
