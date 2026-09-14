from __future__ import annotations

import json
import os
import shlex
from dataclasses import dataclass
from pathlib import Path


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return default if raw is None else int(raw)


def _env_command(name: str, default: list[str]) -> tuple[str, ...]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return tuple(default)
    if raw.startswith("["):
        parsed = json.loads(raw)
        if not isinstance(parsed, list) or not all(isinstance(x, str) and x for x in parsed):
            raise ValueError(f"{name} must be a JSON string array")
        return tuple(parsed)
    return tuple(shlex.split(raw))


@dataclass(frozen=True)
class Settings:
    state_dir: Path
    allowed_roots: tuple[Path, ...]
    enable_execution: bool
    enable_routing_writes: bool
    max_workers: int
    max_snapshot_bytes: int
    controller_model: str
    flash_model: str
    judge_model: str
    codex_command: tuple[str, ...]
    agy_command: tuple[str, ...]
    worker_backend: str
    agy_effort: str
    agy_sandbox: bool
    agy_settings_path: Path
    controller_timeout_seconds: int
    worker_timeout_seconds: int
    mcp_host: str
    mcp_port: int

    @classmethod
    def from_env(cls) -> "Settings":
        home = Path.home()
        state_dir = Path(
            os.getenv("LIN3D_BENCH_STATE_DIR", str(home / ".hermes" / "lin3d-flash-benchmark"))
        ).expanduser()
        roots_raw = os.getenv("LIN3D_ALLOWED_ROOTS", str(home / "Documents"))
        roots = tuple(Path(p).expanduser().resolve() for p in roots_raw.split(os.pathsep) if p)
        max_workers = min(max(_env_int("LIN3D_MAX_WORKERS", 8), 1), 8)
        worker_backend = os.getenv("LIN3D_WORKER_BACKEND", "agy").strip().lower()
        if worker_backend not in {"agy", "hermes"}:
            raise ValueError("LIN3D_WORKER_BACKEND must be agy or hermes")
        agy_effort = os.getenv("LIN3D_AGY_EFFORT", "high").strip().lower()
        if agy_effort not in {"low", "medium", "high"}:
            raise ValueError("LIN3D_AGY_EFFORT must be low, medium, or high")
        max_snapshot_bytes = _env_int("LIN3D_MAX_SNAPSHOT_BYTES", 2 * 1024 * 1024 * 1024)
        if max_snapshot_bytes < 1:
            raise ValueError("LIN3D_MAX_SNAPSHOT_BYTES must be positive")
        return cls(
            state_dir=state_dir,
            allowed_roots=roots,
            enable_execution=_env_bool("LIN3D_ENABLE_EXECUTION", False),
            enable_routing_writes=_env_bool("LIN3D_ENABLE_ROUTING_WRITES", False),
            max_workers=max_workers,
            max_snapshot_bytes=max_snapshot_bytes,
            controller_model=os.getenv("LIN3D_CONTROLLER_MODEL", "gpt-5.6-sol"),
            flash_model=os.getenv("LIN3D_FLASH_MODEL", "Gemini 3.8 Flash (High)"),
            judge_model=os.getenv("LIN3D_JUDGE_MODEL", "gpt-5.6-pro"),
            codex_command=_env_command("LIN3D_CODEX_COMMAND", ["codex"]),
            agy_command=_env_command("LIN3D_AGY_COMMAND", ["agy"]),
            worker_backend=worker_backend,
            agy_effort=agy_effort,
            agy_sandbox=_env_bool("LIN3D_AGY_SANDBOX", True),
            agy_settings_path=Path(
                os.getenv(
                    "LIN3D_AGY_SETTINGS_PATH",
                    str(home / ".gemini" / "antigravity-cli" / "settings.json"),
                )
            ).expanduser(),
            controller_timeout_seconds=_env_int("LIN3D_CONTROLLER_TIMEOUT_SECONDS", 7200),
            worker_timeout_seconds=_env_int("LIN3D_WORKER_TIMEOUT_SECONDS", 900),
            mcp_host=os.getenv("LIN3D_MCP_HOST", "127.0.0.1"),
            mcp_port=_env_int("LIN3D_MCP_PORT", 8765),
        )
