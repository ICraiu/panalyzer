from __future__ import annotations

from pydantic import BaseModel, Field

from .method import MethodReference
from .package import Package


class Project(BaseModel):
    """Top-level analyzed project representation."""

    root: str = Field(description="Absolute root path that was analyzed")
    packages: list[Package] = Field(
        default_factory=list,
        description="Packages discovered in the project",
    )
    references: list[MethodReference] = Field(
        default_factory=list,
        description="All retained call relationships in the project",
    )
