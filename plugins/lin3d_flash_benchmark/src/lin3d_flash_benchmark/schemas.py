from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class RunStatus(StrEnum):
    PREFLIGHT = "PREFLIGHT"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"


class PromotionClass(StrEnum):
    FLASH_ALLOWED = "FLASH_ALLOWED"
    FLASH_WITH_SOL_REVIEW = "FLASH_WITH_SOL_REVIEW"
    SOL_ONLY = "SOL_ONLY"


class StartRequest(BaseModel):
    workspace: Path
    benchmark_packet: Path
    task_matrix: Path
    routing_policy: Path
    evidence_schema: Path
    hidden_gold: Path
    evidence_bundle: Path
    max_workers: int = Field(default=8, ge=1, le=8)
    execute: bool = False
    label: str = Field(default="lin-aster-r14h-flash38", min_length=3, max_length=80)

    @field_validator("label")
    @classmethod
    def validate_label(cls, value: str) -> str:
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
        if any(ch not in allowed for ch in value):
            raise ValueError("label may only contain letters, numbers, '-' and '_'")
        return value


class PreflightReport(BaseModel):
    ok: bool
    execution_enabled: bool
    controller_model: str
    worker_model: str
    judge_model: str
    max_workers: int
    resolved_paths: dict[str, str]
    command_checks: dict[str, bool]
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RunRecord(BaseModel):
    run_id: str
    label: str
    status: RunStatus
    created_at: str
    updated_at: str
    run_dir: str
    request: dict[str, Any]
    pid: int | None = None
    return_code: int | None = None
    error: str | None = None


class TaskSpec(BaseModel):
    task_id: str
    task_class: str
    repeat: int = Field(ge=1)
    prompt: str
    evidence_paths: list[str] = Field(default_factory=list)
    output_contract: dict[str, Any] = Field(default_factory=dict)


class WorkerResult(BaseModel):
    task_id: str
    task_class: str
    status: Literal["SUCCEEDED", "FAILED"]
    model: str
    started_at: str
    finished_at: str
    output: dict[str, Any] | None = None
    raw_output_path: str | None = None
    error: str | None = None
    receipt_sha256: str
