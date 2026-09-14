from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .config import Settings
from .schemas import StartRequest
from .service import BenchmarkService

settings = Settings.from_env()
service = BenchmarkService(settings)
mcp = FastMCP(
    "LIN 3D Flash Benchmark",
    instructions=(
        "Codex-controlled, fail-closed benchmark app for blind Gemini 3.8 Flash High Blender QA. "
        "It never edits the production GLB or canon. Start actions require server-side execution enablement."
    ),
    stateless_http=True,
    json_response=True,
)


@mcp.tool()
def app_health() -> dict[str, Any]:
    """Check app, Codex controller, and Gemini worker route readiness without starting work."""
    return service.health()


@mcp.tool()
def benchmark_preflight(
    workspace: str,
    benchmark_packet: str,
    task_matrix: str,
    routing_policy: str,
    evidence_schema: str,
    hidden_gold: str,
    evidence_bundle: str,
    max_workers: int = 8,
) -> dict[str, Any]:
    """Validate fixed files, commands, models, path boundaries, and concurrency; perform no benchmark."""
    request = StartRequest(
        workspace=Path(workspace),
        benchmark_packet=Path(benchmark_packet),
        task_matrix=Path(task_matrix),
        routing_policy=Path(routing_policy),
        evidence_schema=Path(evidence_schema),
        hidden_gold=Path(hidden_gold),
        evidence_bundle=Path(evidence_bundle),
        max_workers=max_workers,
        execute=False,
    )
    return service.preflight(request).model_dump(mode="json")


@mcp.tool()
def start_flash_benchmark(
    workspace: str,
    benchmark_packet: str,
    task_matrix: str,
    routing_policy: str,
    evidence_schema: str,
    hidden_gold: str,
    evidence_bundle: str,
    max_workers: int = 8,
    execute: bool = False,
    label: str = "lin-aster-r14h-flash38",
) -> dict[str, Any]:
    """Create a benchmark run. execute=false is a safe dry-run; execute=true starts Codex if enabled."""
    return service.start(
        StartRequest(
            workspace=Path(workspace),
            benchmark_packet=Path(benchmark_packet),
            task_matrix=Path(task_matrix),
            routing_policy=Path(routing_policy),
            evidence_schema=Path(evidence_schema),
            hidden_gold=Path(hidden_gold),
            evidence_bundle=Path(evidence_bundle),
            max_workers=max_workers,
            execute=execute,
            label=label,
        )
    )


@mcp.tool()
def benchmark_status(run_id: str) -> dict[str, Any]:
    """Return durable run state and whether the owned Codex controller process is alive."""
    return service.status(run_id)


@mcp.tool()
def benchmark_results(run_id: str) -> dict[str, Any]:
    """Return hashable worker, judge, promotion, and controller artifacts for one run."""
    return service.results(run_id)


@mcp.tool()
def cancel_flash_benchmark(run_id: str) -> dict[str, Any]:
    """Cancel only the controller process group owned by the specified benchmark run."""
    return service.cancel(run_id)


@mcp.tool()
def promote_routing(run_id: str, apply: bool = False) -> dict[str, Any]:
    """Review a promotion candidate; applying it requires a separate server-side routing-write permit."""
    return service.promote(run_id, apply=apply)


def main() -> None:
    mcp.run(
        transport="streamable-http",
        host=settings.mcp_host,
        port=settings.mcp_port,
        streamable_http_path="/mcp",
    )


if __name__ == "__main__":
    main()
