import os
from pathlib import Path

from lin3d_flash_benchmark.config import Settings
from lin3d_flash_benchmark.schemas import StartRequest
from lin3d_flash_benchmark.service import BenchmarkService


def settings(tmp_path: Path, *, max_snapshot_bytes: int = 1024 * 1024) -> Settings:
    return Settings(
        state_dir=tmp_path / "state",
        allowed_roots=(tmp_path.resolve(),),
        enable_execution=False,
        enable_routing_writes=False,
        max_workers=8,
        max_snapshot_bytes=max_snapshot_bytes,
        controller_model="gpt-5.6-sol",
        flash_model="gemini-3.8-flash-high",
        probe_worker_model=False,
        judge_model="gpt-5.6-pro",
        codex_command=("python",),
        agy_command=("python",),
        worker_backend="agy",
        agy_effort="high",
        agy_sandbox=True,
        agy_settings_path=tmp_path / "missing-settings.json",
        controller_timeout_seconds=30,
        worker_timeout_seconds=30,
        mcp_host="127.0.0.1",
        mcp_port=8765,
    )


def create_inputs(tmp_path: Path) -> StartRequest:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    evidence = workspace / "evidence"
    evidence.mkdir()
    (evidence / "view.txt").write_text("evidence", encoding="utf-8")
    files = {}
    for name in ["packet.md", "matrix.json", "policy.json", "schema.json", "gold.json"]:
        path = workspace / name
        path.write_text("{}", encoding="utf-8")
        files[name] = path
    return StartRequest(
        workspace=workspace,
        benchmark_packet=files["packet.md"],
        task_matrix=files["matrix.json"],
        routing_policy=files["policy.json"],
        evidence_schema=files["schema.json"],
        hidden_gold=files["gold.json"],
        evidence_bundle=evidence,
        max_workers=8,
        execute=False,
    )


def test_preflight_and_dry_run(tmp_path: Path) -> None:
    service = BenchmarkService(settings(tmp_path))
    request = create_inputs(tmp_path)
    report = service.preflight(request)
    assert report.ok
    assert not report.execution_enabled
    result = service.start(request)
    assert result["status"] == "PREFLIGHT_READY"
    assert result["manifest"]["gold_visible_to_workers"] is False
    assert result["manifest"]["production_mutation_allowed"] is False
    assert result["manifest"]["astra_allowed"] is False
    assert result["manifest"]["worker_terminal_sandbox"] is True
    run_dir = Path(result["run"]["run_dir"])
    evidence_copy = run_dir / "inputs" / "evidence" / "view.txt"
    assert evidence_copy.read_text() == "evidence"
    assert evidence_copy.stat().st_mode & 0o222 == 0
    assert (run_dir / "controller_only" / "hidden_gold.json").is_file()
    assert (run_dir / "input_snapshot_receipt.json").is_file()


def test_execute_is_blocked_when_server_disabled(tmp_path: Path) -> None:
    service = BenchmarkService(settings(tmp_path))
    request = create_inputs(tmp_path).model_copy(update={"execute": True})
    result = service.start(request)
    assert result["status"] == "BLOCKED_EXECUTION_DISABLED"


def test_evidence_symlink_is_rejected(tmp_path: Path) -> None:
    if not hasattr(os, "symlink"):
        return
    service = BenchmarkService(settings(tmp_path))
    request = create_inputs(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    (request.evidence_bundle / "escape.txt").symlink_to(outside)
    report = service.preflight(request)
    assert not report.ok
    assert any("symlink" in blocker for blocker in report.blockers)


def test_evidence_snapshot_size_is_bounded(tmp_path: Path) -> None:
    service = BenchmarkService(settings(tmp_path, max_snapshot_bytes=3))
    request = create_inputs(tmp_path)
    report = service.preflight(request)
    assert not report.ok
    assert any("MAX_SNAPSHOT_BYTES" in blocker for blocker in report.blockers)
