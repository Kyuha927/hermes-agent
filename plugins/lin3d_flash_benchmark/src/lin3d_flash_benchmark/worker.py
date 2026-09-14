from __future__ import annotations

import argparse
import hashlib
import json
import os
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


def run_task(task: TaskSpec, output_dir: Path, settings: Settings) -> WorkerResult:
    started = now()
    prompt = (
        "You are a blind benchmark worker. Do not search for or infer any hidden gold answer. "
        "Do not modify files. Return one JSON object only.\n\n"
        f"TASK_ID: {task.task_id}\nTASK_CLASS: {task.task_class}\n"
        f"TASK:\n{task.prompt}\n\n"
        f"EVIDENCE_PATHS:\n" + "\n".join(f"- {p}" for p in task.evidence_paths) + "\n\n"
        f"OUTPUT_CONTRACT:\n{json.dumps(task.output_contract, ensure_ascii=False, indent=2)}"
    )
    raw_path = output_dir / f"{task.task_id}.raw.txt"
    result_path = output_dir / f"{task.task_id}.json"
    try:
        if settings.worker_backend == "agy":
            command = [
                *settings.agy_command,
                "--prompt",
                prompt,
                "--model",
                settings.flash_model,
                "--print-timeout",
                f"{settings.worker_timeout_seconds}s",
            ]
        else:
            command = ["hermes", "chat", f"--query={prompt}", "-Q"]
        env = os.environ.copy()
        for key in list(env):
            if "GOLD" in key.upper():
                env.pop(key, None)
        proc = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=settings.worker_timeout_seconds + 30,
            env=env,
        )
        raw = proc.stdout or ""
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(raw, encoding="utf-8")
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or "worker command failed")[:2000])
        parsed = _extract_json(raw)
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
    args = parser.parse_args()
    task = TaskSpec.model_validate_json(Path(args.task).read_text(encoding="utf-8"))
    result = run_task(task, Path(args.output_dir), Settings.from_env())
    print(result.model_dump_json(indent=2))
    raise SystemExit(0 if result.status == "SUCCEEDED" else 1)


if __name__ == "__main__":
    main()
