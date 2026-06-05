from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class IterationState(str, Enum):
    PRESENT = "present"
    ADD = "add"
    CHANGE = "change"
    REMOVE = "remove"


class ProposalState(str, Enum):
    ADD = "add"
    CHANGE = "change"
    REMOVE = "remove"


class ProposalPackage(BaseModel):
    name: str = Field(description="Package identity")
    relative_path: str = Field(description="Project-relative directory path")
    iteration_state: ProposalState


class ProposalFile(BaseModel):
    relative_path: str = Field(description="Project-relative file path")
    import_path: str = Field(description="Python import path")
    package_name: str = Field(description="Containing package identity")
    iteration_state: ProposalState


class ProposalMethod(BaseModel):
    qualname: str = Field(description="Method identity")
    name: str = Field(description="Simple method name")
    file_relative_path: str = Field(description="Containing file identity")
    signature: str | None = Field(default=None, description="Rendered signature")
    line: int | None = Field(default=None, description="Definition line if known")
    iteration_state: ProposalState


class ProposalReference(BaseModel):
    source_method: str = Field(description="Caller method identity")
    target_method: str = Field(description="Callee method identity")
    file_relative_path: str = Field(description="Project-relative file path of the callsite")
    iteration_state: ProposalState


class ProposalDocument(BaseModel):
    id: str
    name: str
    created_at: str
    author: str
    source_model: str
    rationale: str
    project_sha: str
    packages: list[ProposalPackage] = Field(default_factory=list)
    files: list[ProposalFile] = Field(default_factory=list)
    methods: list[ProposalMethod] = Field(default_factory=list)
    references: list[ProposalReference] = Field(default_factory=list)


class ValidationIssue(BaseModel):
    code: str
    path: str
    message: str


class ValidationResult(BaseModel):
    valid: bool
    warnings: list[ValidationIssue] = Field(default_factory=list)
    errors: list[ValidationIssue] = Field(default_factory=list)


class ProposalSaveResult(BaseModel):
    proposal: ProposalDocument
    validation: ValidationResult


class ProposalSummary(BaseModel):
    id: str
    name: str
    created_at: str
    author: str
    source_model: str
    rationale: str
    project_sha: str
    validation: ValidationResult

