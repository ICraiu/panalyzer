from __future__ import annotations

from pydantic import BaseModel, Field


class ArchitectureNode(BaseModel):
    """A graph node suitable for machines and humans."""

    id: str = Field(description="Stable node identifier")
    kind: str = Field(description="Node type: package, file, method")
    label: str = Field(description="Human-readable display label")
    parent_id: str | None = Field(default=None, description="Containing node identifier")
    path: str | None = Field(default=None, description="Absolute path for package/file nodes")
    import_path: str | None = Field(default=None, description="Import path for file/method nodes")
    qualname: str | None = Field(default=None, description="Qualified name for method nodes")
    signature: str | None = Field(default=None, description="Method or class signature when relevant")
    line: int | None = Field(default=None, description="Source line number when relevant")


class ArchitectureEdge(BaseModel):
    """A graph edge suitable for machines and humans."""

    id: str = Field(description="Stable edge identifier")
    kind: str = Field(description="Edge type: calls")
    source_id: str = Field(description="Source node identifier")
    target_id: str = Field(description="Target node identifier")
    expression: str = Field(description="Call expression as found in source")
    line: int = Field(description="Source line where the relation occurs")
    resolution: str = Field(description="How the relation target was resolved")


class ArchitectureSection(BaseModel):
    """A hierarchical section summary for grouped display."""

    id: str = Field(description="Stable section identifier")
    kind: str = Field(description="Section type: package or file")
    label: str = Field(description="Human-readable label")
    node_ids: list[str] = Field(
        default_factory=list,
        description="Node identifiers directly contained in this section",
    )
    child_sections: list[ArchitectureSection] = Field(
        default_factory=list,
        description="Nested package/file sections",
    )


class ArchitectureSummary(BaseModel):
    """Top-level summary counts for quick orientation."""

    package_count: int = Field(description="Number of packages")
    file_count: int = Field(description="Number of files")
    method_count: int = Field(description="Number of methods")
    internal_call_count: int = Field(description="Number of internal method-call edges")


class ArchitectureDocument(BaseModel):
    """Canonical architecture artifact for GPT and human inspection."""

    root: str = Field(description="Absolute root path that was analyzed")
    summary: ArchitectureSummary = Field(description="High-level counts")
    sections: list[ArchitectureSection] = Field(
        default_factory=list,
        description="Grouped package/file sections for structured inspection",
    )
    nodes: list[ArchitectureNode] = Field(
        default_factory=list,
        description="Flat graph nodes with stable identifiers",
    )
    edges: list[ArchitectureEdge] = Field(
        default_factory=list,
        description="Flat graph edges with stable identifiers",
    )
