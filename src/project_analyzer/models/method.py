from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class MethodKind(str, Enum):
    """The kind of callable this symbol represents."""

    FUNCTION = "function"
    METHOD = "method"
    ASYNC_FUNCTION = "async_function"
    CLASS = "class"


class MethodReference(BaseModel):
    """A call relationship discovered in the project."""

    source_method: str | None = Field(
        default=None,
        description="Fully qualified caller method name, or null for file-level calls",
    )
    target_method: str = Field(description="Resolved or inferred target method name")
    file_path: str = Field(description="File path where the call occurs")
    line: int = Field(description="Line number of the call")
    expression: str = Field(description="Call expression found in source code")
    resolution: str = Field(description="How the target method was resolved")
    internal: bool = Field(description="Whether the target resolves to a project method")


class Method(BaseModel):
    """Represents a class, function, async function, or method."""

    name: str = Field(description="Simple method/function/class name")
    qualname: str = Field(description="Fully qualified name")
    signature: str = Field(description="Rendered method or class signature")
    kind: MethodKind = Field(description="Callable kind")
    line: int = Field(description="Definition line number")
    calls: list[MethodReference] = Field(
        default_factory=list,
        description="Calls made from inside this method",
    )
