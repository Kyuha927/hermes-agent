from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path
from typing import Any

from .config import Settings
from .process import (
    build_controller_launch,
    launch_controller,
    process_exists,
    terminate_process_group,
    write_json_atomic,
)
from .prompts import controller_prompt
from .schemas import PreflightReport, RunStatus, StartRequest
from .security import command_available, require_directory, require_regular_file, resolve_allowed, sha256_file
from .store import RunStore


class BenchmarkService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings.from_env()
        self.settings.state_dir.mkdir(parents=True, exist_ok=True)
        self.store = RunStore(self.settings.state_dir / "runs.sqlite3")
        self._processes: dict[str, Any] = {}
        self._lock = threading.Lock()

    def preflight(self, request: StartRequest) -> PreflightReport:
        blockers: list[str] = []
        warnings: list[str] = []
        resolved: dict[str, str] = {}
        path_fields = {
            "workspace": (request.workspace, "dir"),
            "benchmark_packet": (request.benchmark_packet, "file"),
            "task_matrix": (request.task_matrix, "file"),
            "routing_policy": (request.routing_policy, "file"),
            "evidence_schema": (request.evidence_schema, "file"),
            "hidden_gold": (request.hidden_gold, "file"),
        }
        for name, (value, expected) in path_fields.items():
            try:
                path = resolve_allowed(value, self.settings.allowed_roots)
                path = require_directory(path) if expected == "dir" else require_regular_file(path)
                resolved[name] = str(path)
                if expected == "file":
                    resolved[f"{name}_sha256"] = sha256_file(path)
            except Exception as exc:
                blockers.append(f"{name}: {exc}")
        commands = {
            "codex": command_available(self.settings.codex_command),
            "worker": command_available(self.settings.agy_command)
            if self.settings.worker_backend == "agy"
            else command_available(("hermes",)),
        }
        for command_name, available in commands.items():
            if not available:
                blockers.append(f"missing command: {command_name}")
        if request.max_workers > self.settings.max_workers:
            blockers.append(
                f"requested max_workers={request.max_workers} exceeds server cap={self.settings.max_workers}"
            )
        if not self.settings.enable_execution:
            warnings.append("LIN3D_ENABLE_EXECUTION is disabled; only dry-run/preflight is permitted")
        return PreflightReport(
            ok=not blockers,
            execution_enabled=self.settings.enable_execution,
            controller_model=self.settings.controller_model,
            worker_model=self.settings.flash_model,
            judge_model=self.settings.judge_model,
            max_workers=min(request.max_workers, self.settings.max_workers),
            resolved_paths=resolved,
            command_checks=commands,
            blockers=blockers,
            warnings=warnings,
        )

    def start(self, request: StartRequest) -> dict[str, Any]:
        report = self.preflight(request)
        if not report.ok:
            return {"status": "BLOCKED", "preflight": report.model_dump(mode="json")}
        if request.execute and not self.settings.enable_execution:
            return {
                "status": "BLOCKED_EXECUTION_DISABLED",
                "preflight": report.model_dump(mode="json"),
            }
        run_id = f"{request.label}-{uuid.uuid4().hex[:12]}"
        run_dir = self.settings.state_dir / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        resolved = report.resolved_paths
        manifest = {
            "schema_version": 1,
            "run_id": run_id,
            "run_dir": str(run_dir),
            "workspace": resolved["workspace"],
            "benchmark_packet": resolved["benchmark_packet"],
            "task_matrix": resolved["task_matrix"],
            "routing_policy": resolved["routing_policy"],
            "evidence_schema": resolved["evidence_schema"],
            "hidden_gold": resolved["hidden_gold"],
            "max_workers": min(request.max_workers, self.settings.max_workers),
            "controller_model": self.settings.controller_model,
            "worker_model": self.settings.flash_model,
            "judge_model": self.settings.judge_model,
            "gold_visible_to_workers": False,
            "production_mutation_allowed": False,
            "astra_allowed": False,
        }
        manifest_path = run_dir / "manifest.json"
        prompt_path = run_dir / "controller_prompt.md"
        write_json_atomic(manifest_path, manifest)
        prompt_path.write_text(controller_prompt(manifest_path=manifest_path), encoding="utf-8")
        self.store.create(
            run_id=run_id,
            label=request.label,
            run_dir=run_dir,
            request=request.model_dump(mode="json"),
        )
        if not request.execute:
            self.store.update(run_id, status=RunStatus.PREFLIGHT)
            return {
                "status": "PREFLIGHT_READY",
                "run": self.store.get(run_id).model_dump(mode="json"),
                "preflight": report.model_dump(mode="json"),
                "manifest": manifest,
            }
        launch = build_controller_launch(
            self.settings,
            workspace=Path(resolved["workspace"]),
            manifest_path=manifest_path,
            prompt_path=prompt_path,
        )
        process = launch_controller(
            launch,
            stdout_path=run_dir / "controller.stdout.jsonl",
            stderr_path=run_dir / "controller.stderr.log",
        )
        with self._lock:
            self._processes[run_id] = process
        self.store.update(run_id, status=RunStatus.RUNNING, pid=process.pid)
        thread = threading.Thread(target=self._wait_for_process, args=(run_id, process), daemon=True)
        thread.start()
        return {
            "status": "RUNNING",
            "run": self.store.get(run_id).model_dump(mode="json"),
            "preflight": report.model_dump(mode="json"),
        }

    def _wait_for_process(self, run_id: str, process: Any) -> None:
        try:
            return_code = process.wait(timeout=self.settings.controller_timeout_seconds)
            status = RunStatus.SUCCEEDED if return_code == 0 else RunStatus.FAILED
            self.store.update(run_id, status=status, return_code=return_code)
        except Exception as exc:
            terminate_process_group(process.pid)
            self.store.update(run_id, status=RunStatus.FAILED, error=str(exc))
        finally:
            with self._lock:
                self._processes.pop(run_id, None)

    def status(self, run_id: str) -> dict[str, Any]:
        record = self.store.get(run_id)
        alive = bool(record.pid and process_exists(record.pid))
        return {"run": record.model_dump(mode="json"), "process_alive": alive}

    def results(self, run_id: str) -> dict[str, Any]:
        record = self.store.get(run_id)
        run_dir = Path(record.run_dir)
        artifacts = {}
        for name in [
            "worker_aggregate.json",
            "benchmark_result.json",
            "promotion_candidate.json",
            "controller_receipt.json",
        ]:
            path = run_dir / name
            if path.is_file():
                artifacts[name] = json.loads(path.read_text(encoding="utf-8"))
        return {"run": record.model_dump(mode="json"), "artifacts": artifacts}

    def cancel(self, run_id: str) -> dict[str, Any]:
        record = self.store.get(run_id)
        if record.status not in {RunStatus.QUEUED, RunStatus.RUNNING, RunStatus.CANCEL_REQUESTED}:
            return {"status": "NOOP", "run": record.model_dump(mode="json")}
        self.store.update(run_id, status=RunStatus.CANCEL_REQUESTED)
        if record.pid:
            terminate_process_group(record.pid)
        updated = self.store.update(run_id, status=RunStatus.CANCELLED)
        return {"status": "CANCELLED", "run": updated.model_dump(mode="json")}

    def promote(self, run_id: str, *, apply: bool = False) -> dict[str, Any]:
        record = self.store.get(run_id)
        run_dir = Path(record.run_dir)
        candidate_path = run_dir / "promotion_candidate.json"
        if not candidate_path.is_file():
            return {"status": "BLOCKED_NO_PROMOTION_CANDIDATE"}
        candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
        classes = candidate.get("task_classes")
        if not isinstance(classes, dict) or not classes:
            return {"status": "BLOCKED_INVALID_PROMOTION_CANDIDATE"}
        if apply and not self.settings.enable_routing_writes:
            return {"status": "BLOCKED_ROUTING_WRITES_DISABLED", "candidate": candidate}
        output_path = run_dir / ("routing_applied.json" if apply else "routing_review.json")
        write_json_atomic(output_path, candidate)
        return {
            "status": "APPLIED" if apply else "READY_FOR_REVIEW",
            "path": str(output_path),
            "candidate": candidate,
        }

    def health(self) -> dict[str, Any]:
        return {
            "status": "READY",
            "execution_enabled": self.settings.enable_execution,
            "routing_writes_enabled": self.settings.enable_routing_writes,
            "controller_model": self.settings.controller_model,
            "worker_model": self.settings.flash_model,
            "judge_model": self.settings.judge_model,
            "worker_backend": self.settings.worker_backend,
            "max_workers": self.settings.max_workers,
            "codex_available": command_available(self.settings.codex_command),
            "worker_available": command_available(self.settings.agy_command)
            if self.settings.worker_backend == "agy"
            else command_available(("hermes",)),
            "state_dir": str(self.settings.state_dir),
        }
