from __future__ import annotations

from pydantic import BaseModel, Field

from .proposal import IterationState, ProposalSummary, ValidationIssue


class GraphPackageNode(BaseModel):
    """Interactive package node for the web viewer."""

    id: str = Field(description="Stable node identifier")
    label: str = Field(description="Display label")
    path: str = Field(description="Absolute filesystem path")
    iteration_state: IterationState = Field(default=IterationState.PRESENT)


class GraphFileNode(BaseModel):
    """Interactive file node for the web viewer."""

    id: str = Field(description="Stable node identifier")
    label: str = Field(description="Display label")
    parent_id: str = Field(description="Containing package node identifier")
    path: str = Field(description="Absolute filesystem path")
    import_path: str = Field(description="Python import path")
    iteration_state: IterationState = Field(default=IterationState.PRESENT)


class GraphMethodNode(BaseModel):
    """Interactive method node for the web viewer."""

    id: str = Field(description="Stable node identifier")
    label: str = Field(description="Display label")
    parent_id: str = Field(description="Containing file node identifier")
    path: str = Field(description="Absolute filesystem path")
    import_path: str = Field(description="Python import path")
    qualname: str = Field(description="Qualified symbol name")
    signature: str = Field(description="Method or class signature")
    line: int = Field(description="Source line number")
    iteration_state: IterationState = Field(default=IterationState.PRESENT)


class GraphEdge(BaseModel):
    """Interactive graph edge for the web viewer."""

    id: str = Field(description="Stable edge identifier")
    source_id: str = Field(description="Caller node identifier")
    target_id: str = Field(description="Callee node identifier")
    line: int = Field(description="Source line number of the call")
    iteration_state: IterationState = Field(default=IterationState.PRESENT)


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
    nodes: list[GraphPackageNode | GraphFileNode | GraphMethodNode] = Field(
        default_factory=list,
        description="Graph nodes",
    )
    edges: list[GraphEdge] = Field(default_factory=list, description="Graph edges")
    active_proposal: ProposalSummary | None = Field(default=None)
    warnings: list[ValidationIssue] = Field(default_factory=list)
