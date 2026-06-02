from __future__ import annotations

from pydantic import BaseModel, Field

from .method import Method


class SourceFile(BaseModel):
    """Represents a Python source file in the project."""

    path: str = Field(description="Absolute file path on disk")
    import_path: str = Field(description="Python import path for this file")
    methods: list[Method] = Field(
        default_factory=list,
        description="Classes/functions/methods defined in this file",
    )
