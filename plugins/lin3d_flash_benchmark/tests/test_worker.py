from pathlib import Path

from lin3d_flash_benchmark.config import Settings
from lin3d_flash_benchmark.worker import _extract_json, build_agy_command


def test_extract_json_plain() -> None:
    assert _extract_json('{"ok": true}') == {"ok": True}


def test_extract_json_fenced() -> None:
    assert _extract_json('```json\n{"ok": true}\n```') == {"ok": True}


def test_extract_json_with_preface() -> None:
    assert _extract_json('result follows\n{"ok": true}\nend') == {"ok": True}


def test_agy_command_is_sandboxed_and_never_skips_permissions(tmp_path: Path) -> None:
    settings = Settings(
        state_dir=tmp_path / "state",
        allowed_roots=(tmp_path,),
        enable_execution=True,
        enable_routing_writes=False,
        max_workers=8,
        max_snapshot_bytes=1024,
        controller_model="gpt-5.6-sol",
        flash_model="Gemini 3.8 Flash (High)",
        judge_model="gpt-5.6-pro",
        codex_command=("codex",),
        agy_command=("agy",),
        worker_backend="agy",
        agy_effort="high",
        agy_sandbox=True,
        agy_settings_path=tmp_path / "settings.json",
        controller_timeout_seconds=30,
        worker_timeout_seconds=30,
        mcp_host="127.0.0.1",
        mcp_port=8765,
    )
    command = build_agy_command(
        settings=settings,
        prompt="test",
        evidence_root=tmp_path,
        schema_path=tmp_path / "schema.json",
    )
    assert "--sandbox" in command
    assert "--add-dir" in command
    assert "--json-schema" in command
    assert "--effort" in command
    assert "--dangerously-skip-permissions" not in command
