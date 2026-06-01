from __future__ import annotations

from pydantic import BaseModel, Field

from .source_file import SourceFile


class Package(BaseModel):
    """A Python package or directory grouping in the analyzed project."""

    name: str = Field(description="Dotted package name")
    path: str = Field(description="Absolute directory path for the package")
    files: list[SourceFile] = Field(
        default_factory=list,
        description="Source files that belong to this package",
    )
