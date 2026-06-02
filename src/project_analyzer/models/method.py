from __future__ import annotations

from pydantic import BaseModel, Field


class MethodReference(BaseModel):
    """A call relationship discovered in the project."""

    source_method: str | None = Field(
        default=None,
        description="Fully qualified caller method name, or null for file-level calls",
    )
    target_method: str = Field(description="Resolved or inferred target method name")
    file_path: str = Field(description="File path where the call occurs")
    line: int = Field(description="Line number of the call")


class Method(BaseModel):
    """Represents a class, function, async function, or method."""

    name: str = Field(description="Simple method/function/class name")
    qualname: str = Field(description="Fully qualified name")
    signature: str = Field(description="Rendered method or class signature")
    line: int = Field(description="Definition line number")
