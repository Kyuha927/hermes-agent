from pathlib import Path

from lin3d_flash_benchmark.config import Settings
from lin3d_flash_benchmark.schemas import StartRequest
from lin3d_flash_benchmark.service import BenchmarkService


def settings(tmp_path: Path) -> Settings:
    return Settings(
        state_dir=tmp_path / "state",
        allowed_roots=(tmp_path.resolve(),),
        enable_execution=False,
        enable_routing_writes=False,
        max_workers=8,
        controller_model="gpt-5.6-sol",
        flash_model="Gemini 3.8 Flash (High)",
        judge_model="gpt-5.6-pro",
        codex_command=("python",),
        agy_command=("python",),
        worker_backend="agy",
        controller_timeout_seconds=30,
        worker_timeout_seconds=30,
        mcp_host="127.0.0.1",
        mcp_port=8765,
    )


def create_inputs(tmp_path: Path) -> StartRequest:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
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


def test_execute_is_blocked_when_server_disabled(tmp_path: Path) -> None:
    service = BenchmarkService(settings(tmp_path))
    request = create_inputs(tmp_path).model_copy(update={"execute": True})
    result = service.start(request)
    assert result["status"] == "BLOCKED_EXECUTION_DISABLED"
