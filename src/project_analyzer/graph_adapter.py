from __future__ import annotations

from .architecture_adapter import ArchitectureDocumentAdapter, _is_constructor_edge_shadowed
from .models import GraphDocument, GraphEdge, GraphNode, GraphSummary, Project


class GraphDocumentAdapter:
    """Build interactive graph data from the project domain."""

    def to_document(self, project: Project) -> GraphDocument:
        architecture = ArchitectureDocumentAdapter().to_document(project)
        nodes = [
            GraphNode(
                id=node.id,
                kind=node.kind,
                label=node.label,
                parent_id=node.parent_id,
                path=node.path,
                import_path=node.import_path,
                qualname=node.qualname,
                signature=node.signature,
                line=node.line,
            )
            for node in architecture.nodes
        ]

        method_node_ids = {
            node.qualname: node.id
            for node in architecture.nodes
            if node.kind == "method" and node.qualname is not None
        }
        line_targets_by_source: dict[tuple[str, int], set[str]] = {}
        for reference in project.references:
            if reference.source_method is None or not reference.internal:
                continue
            line_targets_by_source.setdefault(
                (reference.source_method, reference.line),
                set(),
            ).add(reference.target_method)

        edges: list[GraphEdge] = []
        seen_edges: set[str] = set()
        for reference in project.references:
            if reference.source_method is None or not reference.internal:
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
                    kind="calls",
                    source_id=source_id,
                    target_id=target_id,
                    line=reference.line,
                    expression=reference.expression,
                    resolution=reference.resolution,
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
