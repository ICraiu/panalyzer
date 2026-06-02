from __future__ import annotations

import math
from pathlib import Path

from .models import Method, Project
from .presentation import display_name, node_id


class D2DiagramAdapter:
    """Render the project domain as D2 diagram text."""

    _PACKAGE_COLORS = [
        "#E8F3FF",
        "#EAF7E8",
        "#FFF4DB",
        "#FDEBEC",
        "#F2ECFF",
        "#E8F7F6",
    ]

    def to_diagram(self, project: Project) -> str:
        edge_lines: list[str] = []
        seen_edges: set[tuple[str, str, int]] = set()
        method_paths: dict[str, str] = {}
        line_targets_by_source: dict[tuple[str, int], set[str]] = {}
        for package in project.packages:
            package_id = node_id("pkg", package.name)
            for source_file in package.files:
                file_id = node_id("file", source_file.import_path)
                for method in source_file.methods:
                    method_id = node_id("method", method.qualname)
                    method_paths[method.qualname] = f"{package_id}.{file_id}.{method_id}"

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
            edge_key = (reference.source_method, reference.target_method, reference.line)
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)
            if _is_constructor_edge_shadowed(reference, line_targets_by_source):
                continue
            source_path = method_paths.get(reference.source_method)
            target_path = method_paths.get(reference.target_method)
            if source_path is None or target_path is None:
                continue
            edge_lines.append(f"{source_path} -> {target_path}")

        lines = [
            "direction: right",
            "",
        ]

        if len(project.packages) > 1:
            lines.extend(
                [
                    f"grid-columns: {math.ceil(math.sqrt(len(project.packages)))}",
                    "grid-gap: 120",
                    "",
                ]
            )

        for index, package in enumerate(project.packages):
            package_id = node_id("pkg", package.name)
            package_color = self._PACKAGE_COLORS[index % len(self._PACKAGE_COLORS)]
            lines.extend(
                [
                    f"{package_id}: {{",
                    f'  label: "{_escape(package.name)}"',
                    "  direction: right",
                    "  style: {",
                    f'    fill: "{package_color}"',
                    '    stroke: "#7A6A4F"',
                    "    stroke-width: 1",
                    "  }",
                ]
            )

            for source_file in package.files:
                file_id = node_id("file", source_file.import_path)
                file_label = f"{Path(source_file.path).name} | {source_file.import_path}"
                lines.extend(
                    [
                        f"  {file_id}: {{",
                        f'    label: "{_escape(file_label)}"',
                        "    direction: down",
                        "    style: {",
                        '      fill: "#FFFDF8"',
                        '      stroke: "#8B8170"',
                        "      stroke-width: 1",
                        "    }",
                    ]
                )

                for method in source_file.methods:
                    method_id = node_id("method", method.qualname)
                    method_label = _method_label(method)
                    lines.extend(
                        [
                            f'    {method_id}: "{_escape(method_label)}"',
                        ]
                    )

                lines.append("  }")

            lines.append("}")
            lines.append("")
        lines.extend(edge_lines)
        return "\n".join(lines).rstrip() + "\n"


def _method_label(method: Method) -> str:
    method_name = display_name(method.name)
    if method.signature.startswith("class "):
        return f"class {method_name} | L{method.line}"
    return f"{method_name}(...) | L{method.line}"


def _is_constructor_edge_shadowed(
    reference,
    line_targets_by_source: dict[tuple[str, int], set[str]],
) -> bool:
    targets = line_targets_by_source.get((reference.source_method, reference.line), set())
    prefix = f"{reference.target_method}."
    return any(target.startswith(prefix) for target in targets)


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
