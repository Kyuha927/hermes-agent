from __future__ import annotations

import json
import os
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import Settings


@dataclass(frozen=True)
class ControllerLaunch:
    args: list[str]
    env: dict[str, str]
    cwd: Path


def build_controller_launch(
    settings: Settings,
    *,
    workspace: Path,
    manifest_path: Path,
    prompt_path: Path,
) -> ControllerLaunch:
    prompt = prompt_path.read_text(encoding="utf-8")
    args = [
        *settings.codex_command,
        "exec",
        "--model",
        settings.controller_model,
        "--json",
        "--cd",
        str(workspace),
        prompt,
    ]
    env = os.environ.copy()
    env.update(
        {
            "LIN3D_RUN_MANIFEST": str(manifest_path),
            "LIN3D_FLASH_MODEL": settings.flash_model,
            "LIN3D_JUDGE_MODEL": settings.judge_model,
            "LIN3D_MAX_WORKERS": str(settings.max_workers),
            "LIN3D_GOLD_VISIBLE_TO_WORKERS": "0",
        }
    )
    return ControllerLaunch(args=args, env=env, cwd=workspace)


def launch_controller(launch: ControllerLaunch, stdout_path: Path, stderr_path: Path) -> subprocess.Popen[bytes]:
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stdout_handle = stdout_path.open("wb")
    stderr_handle = stderr_path.open("wb")
    try:
        return subprocess.Popen(
            launch.args,
            cwd=launch.cwd,
            env=launch.env,
            stdout=stdout_handle,
            stderr=stderr_handle,
            start_new_session=True,
        )
    finally:
        stdout_handle.close()
        stderr_handle.close()


def terminate_process_group(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return


def process_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def write_json_atomic(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)
