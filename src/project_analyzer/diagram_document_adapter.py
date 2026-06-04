from __future__ import annotations

from .graph_adapter import GraphDocumentAdapter
from .models import (
    DiagramDocument,
    DiagramFile,
    DiagramPackage,
    DiagramSummary,
    DiagramTransition,
    GraphFileNode,
    GraphMethodNode,
    GraphPackageNode,
    Project,
)


class DiagramDocumentAdapter:
    """Build the package/file transition view used as the exported architecture base."""

    def to_document(self, project: Project) -> DiagramDocument:
        graph = GraphDocumentAdapter().to_document(project)

        packages: list[DiagramPackage] = []
        files: list[DiagramFile] = []
        file_by_id: dict[str, GraphFileNode] = {}
        method_to_file_id: dict[str, str] = {}
        method_qualname_by_id: dict[str, str] = {}

        for node in graph.nodes:
            if isinstance(node, GraphPackageNode):
                packages.append(
                    DiagramPackage(
                        id=node.id,
                        name=node.label,
                        path=node.path,
                    )
                )
            elif isinstance(node, GraphFileNode):
                files.append(
                    DiagramFile(
                        id=node.id,
                        package_id=node.parent_id,
                        import_path=node.import_path,
                        path=node.path,
                    )
                )
                file_by_id[node.id] = node
            else:
                assert isinstance(node, GraphMethodNode)
                method_to_file_id[node.id] = node.parent_id
                method_qualname_by_id[node.id] = node.qualname

        transitions_by_id: dict[str, DiagramTransition] = {}
        for edge in graph.edges:
            source_file_id = method_to_file_id.get(edge.source_id)
            target_file_id = method_to_file_id.get(edge.target_id)
            if source_file_id is None or target_file_id is None:
                continue
            if source_file_id == target_file_id:
                continue

            source_file = file_by_id[source_file_id]
            target_file = file_by_id[target_file_id]
            transition_id = f"transition_{source_file_id}_{target_file_id}"
            transition = transitions_by_id.get(transition_id)
            if transition is None:
                transitions_by_id[transition_id] = DiagramTransition(
                    id=transition_id,
                    source_file_id=source_file_id,
                    target_file_id=target_file_id,
                    source_import_path=source_file.import_path,
                    target_import_path=target_file.import_path,
                )
                transition = transitions_by_id[transition_id]
            target_method = method_qualname_by_id.get(edge.target_id)
            if target_method is None:
                continue
            if target_method not in transition.referenced_methods:
                transition.referenced_methods.append(target_method)

        packages.sort(key=lambda item: item.id)
        files.sort(key=lambda item: item.id)
        for transition in transitions_by_id.values():
            transition.referenced_methods.sort()
        transitions = sorted(transitions_by_id.values(), key=lambda item: item.id)

        return DiagramDocument(
            root=project.root,
            summary=DiagramSummary(
                package_count=len(packages),
                file_count=len(files),
                transition_count=len(transitions),
            ),
            packages=packages,
            files=files,
            transitions=transitions,
        )
