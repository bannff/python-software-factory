"""Concrete outputs for Foreman's governance-check tool."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ImportIssue(DTO):
    module: str
    file: str


class FileViolation(DTO):
    file: str
    lines: int
    over_by: int
    base_lines: int | None = None
    reason: str | None = None


class ProjectViolation(DTO):
    project: str
    path: str
    error: str


class ContractViolation(DTO):
    brick: str
    path: str
    tool: str
    issue: str


class ImportCheck(DTO):
    check: Literal["import_integrity"]
    passed: bool
    files_checked: int
    imports_checked: int
    adapters_skipped: int
    unresolved: list[ImportIssue]
    total_unresolved: int


class BranchCheck(DTO):
    check: Literal["branch_naming"]
    passed: bool
    branch: str | None = None
    source: str | None = None
    skipped: str | None = None
    error: str | None = None


class FileSizeCheck(DTO):
    check: Literal["file_sizes"]
    mode: str
    passed: bool
    max_lines: int
    files_checked: int
    violations: list[FileViolation]
    total_violations: int
    error: str | None = None


class BricksIndexCheck(DTO):
    check: Literal["bricks_index"]
    passed: bool
    components: int | None = None
    bases: int | None = None
    errors: list[str] | None = None
    error: str | None = None


class ProjectBaseCheck(DTO):
    check: Literal["project_has_base"]
    mode: str
    passed: bool
    projects_checked: int
    base_projects_checked: int | None = None
    violations: list[ProjectViolation]
    legacy_violations: list[ProjectViolation] | None = None
    resolved_violations: list[ProjectViolation] | None = None
    error: str | None = None


class ContractCheck(DTO):
    check: Literal["mcp_contracts"]
    passed: bool
    mode: str
    violations: list[ContractViolation]
    new_violations: list[ContractViolation] | None = None
    legacy_violations: list[ContractViolation] | None = None
    resolved_violations: list[ContractViolation] | None = None
    message: str | None = None
    error: str | None = None


class GuardianSummary(DTO):
    total: int
    passed: int
    failed: int


class GuardianOutput(DTO):
    passed: bool
    checks: list[
        ImportCheck | BranchCheck | FileSizeCheck | BricksIndexCheck | ProjectBaseCheck | ContractCheck
    ]
    summary: GuardianSummary
