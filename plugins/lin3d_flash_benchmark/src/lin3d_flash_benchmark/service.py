from __future__ import annotations

import json
import shutil
import stat
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
from .security import (
    SecurityError,
    command_available,
    require_directory,
    require_regular_file,
    resolve_allowed,
    sha256_file,
)
from .store import RunStore


class BenchmarkService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings.from_env()
        self.settings.state_dir.mkdir(parents=True, exist_ok=True)
        self.store = RunStore(self.settings.state_dir / "runs.sqlite3")
        self._processes: dict[str, Any] = {}
        self._lock = threading.Lock()

    def _inspect_evidence_bundle(self, source: Path) -> tuple[list[Path], int]:
        source = source.resolve(strict=True)
        files: list[Path] = []
        total_bytes = 0
        for path in sorted(source.rglob("*")):
            if path.is_symlink():
                raise SecurityError(f"Evidence bundle contains a symlink: {path}")
            if path.is_dir():
                continue
            if not path.is_file():
                raise SecurityError(f"Evidence bundle contains a non-regular entry: {path}")
            resolved = path.resolve(strict=True)
            if resolved != source and source not in resolved.parents:
                raise SecurityError(f"Evidence entry escapes its source root: {path}")
            total_bytes += resolved.stat().st_size
            if total_bytes > self.settings.max_snapshot_bytes:
                raise SecurityError(
                    "Evidence bundle exceeds LIN3D_MAX_SNAPSHOT_BYTES "
                    f"({total_bytes} > {self.settings.max_snapshot_bytes})"
                )
            files.append(resolved)
        if not files:
            raise SecurityError("Evidence bundle contains no regular files")
        return files, total_bytes

    def _agy_sandbox_config(self) -> dict[str, Any]:
        path = self.settings.agy_settings_path
        result: dict[str, Any] = {
            "path": str(path),
            "exists": path.is_file(),
            "enableTerminalSandbox": None,
            "toolPermission": None,
            "proceed_in_sandbox": False,
        }
        if not path.is_file():
            return result
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            result["error"] = str(exc)
            return result
        result["enableTerminalSandbox"] = payload.get("enableTerminalSandbox")
        result["toolPermission"] = payload.get("toolPermission")
        result["proceed_in_sandbox"] = (
            payload.get("enableTerminalSandbox") is True
            and payload.get("toolPermission") == "proceed-in-sandbox"
        )
        return result

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
            "evidence_bundle": (request.evidence_bundle, "dir"),
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
        if "evidence_bundle" in resolved:
            try:
                evidence_files, evidence_bytes = self._inspect_evidence_bundle(
                    Path(resolved["evidence_bundle"])
                )
                resolved["evidence_file_count"] = str(len(evidence_files))
                resolved["evidence_total_bytes"] = str(evidence_bytes)
            except Exception as exc:
                blockers.append(f"evidence_bundle_snapshot: {exc}")
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
        if self.settings.worker_backend == "agy" and self.settings.agy_sandbox:
            sandbox_config = self._agy_sandbox_config()
            if not sandbox_config["proceed_in_sandbox"]:
                warnings.append(
                    "Antigravity CLI will be forced through --sandbox, but settings.json is not "
                    "confirmed as enableTerminalSandbox=true and toolPermission=proceed-in-sandbox; "
                    "headless workers may pause or fail rather than execute tools."
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

    @staticmethod
    def _copy_file(source: Path, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        return destination

    @staticmethod
    def _make_tree_read_only(root: Path) -> None:
        for path in sorted(root.rglob("*"), reverse=True):
            if path.is_file():
                path.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
            elif path.is_dir():
                path.chmod(
                    stat.S_IRUSR
                    | stat.S_IXUSR
                    | stat.S_IRGRP
                    | stat.S_IXGRP
                    | stat.S_IROTH
                    | stat.S_IXOTH
                )
        root.chmod(
            stat.S_IRUSR
            | stat.S_IXUSR
            | stat.S_IRGRP
            | stat.S_IXGRP
            | stat.S_IROTH
            | stat.S_IXOTH
        )

    def _copy_evidence_bundle(self, source: Path, destination: Path) -> tuple[list[Path], int]:
        files, total_bytes = self._inspect_evidence_bundle(source)
        source = source.resolve(strict=True)
        destination.mkdir(parents=True, exist_ok=False)
        copied: list[Path] = []
        for file_path in files:
            relative = file_path.relative_to(source)
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file_path, target)
            copied.append(target)
        self._make_tree_read_only(destination)
        return copied, total_bytes

    def _snapshot_inputs(self, resolved: dict[str, str], run_dir: Path) -> dict[str, str]:
        inputs = run_dir / "inputs"
        controller_only = run_dir / "controller_only"
        snapshot = {
            "benchmark_packet": str(
                self._copy_file(
                    Path(resolved["benchmark_packet"]), inputs / "benchmark_packet.md"
                )
            ),
            "task_matrix": str(
                self._copy_file(Path(resolved["task_matrix"]), inputs / "task_matrix.json")
            ),
            "routing_policy": str(
                self._copy_file(Path(resolved["routing_policy"]), inputs / "routing_policy.json")
            ),
            "evidence_schema": str(
                self._copy_file(Path(resolved["evidence_schema"]), inputs / "evidence_schema.json")
            ),
            "hidden_gold": str(
                self._copy_file(
                    Path(resolved["hidden_gold"]), controller_only / "hidden_gold.json"
                )
            ),
        }
        evidence_destination = inputs / "evidence"
        copied_evidence, evidence_bytes = self._copy_evidence_bundle(
            Path(resolved["evidence_bundle"]), evidence_destination
        )
        snapshot["evidence_bundle"] = str(evidence_destination)
        for path in [
            Path(snapshot["benchmark_packet"]),
            Path(snapshot["task_matrix"]),
            Path(snapshot["routing_policy"]),
            Path(snapshot["evidence_schema"]),
            Path(snapshot["hidden_gold"]),
        ]:
            path.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        receipt: dict[str, Any] = {
            "snapshot_total_bytes": evidence_bytes,
            "source_workspace": resolved["workspace"],
        }
        for name, raw_path in snapshot.items():
            path = Path(raw_path)
            if path.is_file():
                receipt[name] = {"path": raw_path, "sha256": sha256_file(path)}
            else:
                receipt[name] = {
                    "path": raw_path,
                    "files": [
                        {"path": str(p.relative_to(path)), "sha256": sha256_file(p)}
                        for p in copied_evidence
                    ],
                }
        write_json_atomic(run_dir / "input_snapshot_receipt.json", receipt)
        return snapshot

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
        try:
            snapshot = self._snapshot_inputs(resolved, run_dir)
        except Exception as exc:
            shutil.rmtree(run_dir, ignore_errors=True)
            return {
                "status": "BLOCKED_SNAPSHOT_FAILED",
                "error": str(exc),
                "preflight": report.model_dump(mode="json"),
            }
        manifest = {
            "schema_version": 2,
            "run_id": run_id,
            "run_dir": str(run_dir),
            "source_workspace": resolved["workspace"],
            **snapshot,
            "max_workers": min(request.max_workers, self.settings.max_workers),
            "controller_model": self.settings.controller_model,
            "worker_model": self.settings.flash_model,
            "judge_model": self.settings.judge_model,
            "gold_visible_to_workers": False,
            "production_mutation_allowed": False,
            "astra_allowed": False,
            "worker_terminal_sandbox": self.settings.agy_sandbox,
            "controller_sandbox": "workspace-write limited to run_dir snapshot",
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
            run_dir=run_dir,
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
            "input_snapshot_receipt.json",
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
            "worker_terminal_sandbox": self.settings.agy_sandbox,
            "agy_sandbox_config": self._agy_sandbox_config(),
            "max_workers": self.settings.max_workers,
            "max_snapshot_bytes": self.settings.max_snapshot_bytes,
            "codex_available": command_available(self.settings.codex_command),
            "worker_available": command_available(self.settings.agy_command)
            if self.settings.worker_backend == "agy"
            else command_available(("hermes",)),
            "state_dir": str(self.settings.state_dir),
        }
