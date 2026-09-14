from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import Settings
from .process import write_json_atomic
from .schemas import TaskSpec, WorkerResult


def now() -> str:
    return datetime.now(UTC).isoformat()


def _extract_json(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    try:
        value = json.loads(stripped)
        if not isinstance(value, dict):
            raise ValueError("worker output must be a JSON object")
        return value
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("worker output contained no JSON object")
        value = json.loads(stripped[start : end + 1])
        if not isinstance(value, dict):
            raise ValueError("worker output must be a JSON object")
        return value


def _within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _resolve_evidence(task: TaskSpec, evidence_root: Path) -> list[Path]:
    root = evidence_root.resolve(strict=True)
    resolved: list[Path] = []
    for raw_path in task.evidence_paths:
        path = Path(raw_path).expanduser().resolve(strict=True)
        if not _within(path, root):
            raise ValueError(f"worker evidence escapes snapshot root: {path}")
        if not path.is_file():
            raise ValueError(f"worker evidence is not a regular file: {path}")
        resolved.append(path)
    return resolved


def _worker_prompt(task: TaskSpec, evidence_paths: list[Path]) -> str:
    return (
        "You are a blind benchmark worker. The hidden gold answer is unavailable and must not be "
        "searched for or inferred from filenames. Work only from the listed snapshot evidence. "
        "Do not modify files. Return one JSON object only.\n\n"
        f"TASK_ID: {task.task_id}\nTASK_CLASS: {task.task_class}\n"
        f"TASK:\n{task.prompt}\n\n"
        "EVIDENCE_PATHS:\n"
        + "\n".join(f"- {path}" for path in evidence_paths)
        + "\n\n"
        "REQUIRED ENVELOPE:\n"
        "{\n"
        f'  "task_id": "{task.task_id}",\n'
        f'  "task_class": "{task.task_class}",\n'
        '  "claims": [],\n'
        '  "unknowns": [],\n'
        '  "evidence": [],\n'
        '  "confidence": 0.0,\n'
        '  "production_mutation_performed": false,\n'
        '  "result": {}\n'
        "}\n\n"
        "The result object must satisfy this task-specific contract:\n"
        + json.dumps(task.output_contract, ensure_ascii=False, indent=2)
    )


def build_agy_command(
    *,
    settings: Settings,
    prompt: str,
    evidence_root: Path,
    schema_path: Path,
) -> list[str]:
    command = [
        *settings.agy_command,
        "--prompt",
        prompt,
        "--model",
        settings.flash_model,
        "--effort",
        settings.agy_effort,
        "--json-schema",
        str(schema_path),
        "--add-dir",
        str(evidence_root),
        "--print-timeout",
        f"{settings.worker_timeout_seconds}s",
    ]
    if settings.agy_sandbox:
        command.append("--sandbox")
    return command


def run_task(
    task: TaskSpec,
    output_dir: Path,
    settings: Settings,
    evidence_root: Path,
    schema_path: Path,
) -> WorkerResult:
    started = now()
    task_dir = output_dir / task.task_id
    task_dir.mkdir(parents=True, exist_ok=False)
    evidence_paths = _resolve_evidence(task, evidence_root)
    prompt = _worker_prompt(task, evidence_paths)
    worker_schema = task_dir / "worker_output_schema.json"
    shutil.copy2(schema_path, worker_schema)
    worker_schema.chmod(0o444)
    raw_path = task_dir / "raw.txt"
    result_path = task_dir / "result.json"
    try:
        if settings.worker_backend == "agy":
            command = build_agy_command(
                settings=settings,
                prompt=prompt,
                evidence_root=evidence_root,
                schema_path=worker_schema,
            )
        else:
            command = ["hermes", "chat", f"--query={prompt}", "-Q"]
        env = os.environ.copy()
        blocked_markers = ("GOLD", "JUDGE", "RUN_MANIFEST", "CONTROLLER_ONLY")
        for key in list(env):
            if any(marker in key.upper() for marker in blocked_markers):
                env.pop(key, None)
        proc = subprocess.run(
            command,
            cwd=task_dir,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=settings.worker_timeout_seconds + 30,
            env=env,
        )
        raw = proc.stdout or ""
        raw_path.write_text(raw, encoding="utf-8")
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or "worker command failed")[:2000])
        parsed = _extract_json(raw)
        if parsed.get("task_id") != task.task_id or parsed.get("task_class") != task.task_class:
            raise ValueError("worker output identity does not match assigned task")
        if parsed.get("production_mutation_performed") is not False:
            raise ValueError("worker did not attest production_mutation_performed=false")
        receipt = WorkerResult(
            task_id=task.task_id,
            task_class=task.task_class,
            status="SUCCEEDED",
            model=settings.flash_model,
            started_at=started,
            finished_at=now(),
            output=parsed,
            raw_output_path=str(raw_path),
            receipt_sha256="",
        )
    except Exception as exc:
        receipt = WorkerResult(
            task_id=task.task_id,
            task_class=task.task_class,
            status="FAILED",
            model=settings.flash_model,
            started_at=started,
            finished_at=now(),
            error=str(exc),
            raw_output_path=str(raw_path) if raw_path.exists() else None,
            receipt_sha256="",
        )
    payload = receipt.model_dump(mode="json")
    payload["receipt_sha256"] = hashlib.sha256(
        json.dumps({**payload, "receipt_sha256": ""}, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    write_json_atomic(result_path, payload)
    return WorkerResult.model_validate(payload)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--evidence-root", required=True)
    parser.add_argument("--schema", required=True)
    args = parser.parse_args()
    task = TaskSpec.model_validate_json(Path(args.task).read_text(encoding="utf-8"))
    result = run_task(
        task,
        Path(args.output_dir),
        Settings.from_env(),
        Path(args.evidence_root),
        Path(args.schema),
    )
    print(result.model_dump_json(indent=2))
    raise SystemExit(0 if result.status == "SUCCEEDED" else 1)


if __name__ == "__main__":
    main()
