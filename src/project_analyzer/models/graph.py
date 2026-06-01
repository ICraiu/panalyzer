from __future__ import annotations

from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    """Interactive graph node for the web viewer."""

    id: str = Field(description="Stable node identifier")
    kind: str = Field(description="Node type: package, file, method")
    label: str = Field(description="Display label")
    parent_id: str | None = Field(default=None, description="Containing node identifier")
    path: str | None = Field(default=None, description="Absolute filesystem path")
    import_path: str | None = Field(default=None, description="Python import path")
    qualname: str | None = Field(default=None, description="Qualified symbol name")
    signature: str | None = Field(default=None, description="Method or class signature")
    line: int | None = Field(default=None, description="Source line number")


class GraphEdge(BaseModel):
    """Interactive graph edge for the web viewer."""

    id: str = Field(description="Stable edge identifier")
    kind: str = Field(description="Edge type: calls")
    source_id: str = Field(description="Caller node identifier")
    target_id: str = Field(description="Callee node identifier")
    line: int = Field(description="Source line number of the call")
    expression: str = Field(description="Call expression")
    resolution: str = Field(description="Resolution strategy used by the analyzer")


class GraphSummary(BaseModel):
    """Top-level graph counts."""

    package_count: int = Field(description="Number of packages")
    file_count: int = Field(description="Number of files")
    method_count: int = Field(description="Number of methods")
    edge_count: int = Field(description="Number of edges")


class GraphDocument(BaseModel):
    """Interactive graph document returned to the web UI."""

    root: str = Field(description="Analyzed project root")
    summary: GraphSummary = Field(description="Graph counts")
    nodes: list[GraphNode] = Field(default_factory=list, description="Graph nodes")
    edges: list[GraphEdge] = Field(default_factory=list, description="Graph edges")
