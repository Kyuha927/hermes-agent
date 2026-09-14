from pathlib import Path

import pytest

from lin3d_flash_benchmark.security import SecurityError, resolve_allowed


def test_path_must_be_below_allowlist(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    inside = allowed / "x.txt"
    inside.write_text("x", encoding="utf-8")
    assert resolve_allowed(inside, (allowed.resolve(),)) == inside.resolve()


def test_path_escape_is_blocked(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("x", encoding="utf-8")
    with pytest.raises(SecurityError):
        resolve_allowed(outside, (allowed.resolve(),))
