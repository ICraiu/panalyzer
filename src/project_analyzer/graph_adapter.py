from __future__ import annotations

from .architecture_adapter import ArchitectureDocumentAdapter, _is_constructor_edge_shadowed
from .models import (
    ArchitectureFileNode,
    ArchitectureMethodNode,
    ArchitecturePackageNode,
    GraphDocument,
    GraphEdge,
    GraphFileNode,
    GraphMethodNode,
    GraphPackageNode,
    GraphSummary,
    Project,
)


class GraphDocumentAdapter:
    """Build interactive graph data from the project domain."""

    def to_document(self, project: Project) -> GraphDocument:
        architecture = ArchitectureDocumentAdapter().to_document(project)
        nodes: list[GraphPackageNode | GraphFileNode | GraphMethodNode] = []
        for node in architecture.nodes:
            if isinstance(node, ArchitecturePackageNode):
                nodes.append(
                    GraphPackageNode(
                        id=node.id,
                        label=node.label,
                        path=node.path,
                    )
                )
            elif isinstance(node, ArchitectureFileNode):
                nodes.append(
                    GraphFileNode(
                        id=node.id,
                        label=node.label,
                        parent_id=node.parent_id,
                        path=node.path,
                        import_path=node.import_path,
                    )
                )
            else:
                assert isinstance(node, ArchitectureMethodNode)
                nodes.append(
                    GraphMethodNode(
                        id=node.id,
                        label=node.label,
                        parent_id=node.parent_id,
                        path=node.path,
                        import_path=node.import_path,
                        qualname=node.qualname,
                        signature=node.signature,
                        line=node.line,
                    )
                )

        method_node_ids = {
            node.qualname: node.id
            for node in architecture.nodes
            if isinstance(node, ArchitectureMethodNode)
        }
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
                package_count=architecture.summary.package_count,
                file_count=architecture.summary.file_count,
                method_count=architecture.summary.method_count,
                edge_count=len(edges),
            ),
            nodes=nodes,
            edges=edges,
        )
