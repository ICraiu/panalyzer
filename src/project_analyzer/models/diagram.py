from __future__ import annotations

from pydantic import BaseModel, Field

from .proposal import IterationState


class DiagramPackage(BaseModel):
    """A package included in the exported architecture diagram."""

    id: str = Field(description="Stable package identifier")
    name: str = Field(description="Dotted package name")
    path: str = Field(description="Absolute filesystem path")
    iteration_state: IterationState = Field(default=IterationState.PRESENT)


class DiagramFile(BaseModel):
    """A file included in the exported architecture diagram."""

    id: str = Field(description="Stable file identifier")
    package_id: str = Field(description="Containing package identifier")
    import_path: str = Field(description="Python import path")
    path: str = Field(description="Absolute filesystem path")
    iteration_state: IterationState = Field(default=IterationState.PRESENT)


class DiagramTransition(BaseModel):
    """An aggregated file-to-file dependency."""

    id: str = Field(description="Stable transition identifier")
    source_file_id: str = Field(description="Source file identifier")
    target_file_id: str = Field(description="Target file identifier")
    source_import_path: str = Field(description="Source file import path")
    target_import_path: str = Field(description="Target file import path")
    referenced_methods: list[str] = Field(
        default_factory=list,
        description="Target methods referenced across this file-to-file dependency",
    )
    iteration_state: IterationState = Field(default=IterationState.PRESENT)


class DiagramSummary(BaseModel):
    """Top-level exported diagram counts."""

    package_count: int = Field(description="Number of packages")
    file_count: int = Field(description="Number of files")
    transition_count: int = Field(description="Number of file-to-file transitions")


class DiagramDocument(BaseModel):
    """Package/file architecture diagram exported for downstream consumers."""

    root: str = Field(description="Analyzed project root")
    summary: DiagramSummary = Field(description="Diagram counts")
    packages: list[DiagramPackage] = Field(
        default_factory=list,
        description="Packages in the analyzed project",
    )
    files: list[DiagramFile] = Field(
        default_factory=list,
        description="Files in the analyzed project",
    )
    transitions: list[DiagramTransition] = Field(
        default_factory=list,
        description="Aggregated file-to-file transitions",
    )
