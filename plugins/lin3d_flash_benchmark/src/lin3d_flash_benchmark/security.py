from __future__ import annotations

import hashlib
import shutil
from pathlib import Path


class SecurityError(ValueError):
    pass


def resolve_allowed(path: Path, allowed_roots: tuple[Path, ...], *, must_exist: bool = True) -> Path:
    resolved = path.expanduser().resolve(strict=must_exist)
    if not any(resolved == root or root in resolved.parents for root in allowed_roots):
        raise SecurityError(f"Path is outside LIN3D_ALLOWED_ROOTS: {resolved}")
    return resolved


def require_regular_file(path: Path) -> Path:
    if not path.is_file():
        raise SecurityError(f"Expected regular file: {path}")
    return path


def require_directory(path: Path) -> Path:
    if not path.is_dir():
        raise SecurityError(f"Expected directory: {path}")
    return path


def command_available(command: tuple[str, ...]) -> bool:
    if not command:
        return False
    executable = command[0]
    if "/" in executable:
        return Path(executable).expanduser().is_file()
    return shutil.which(executable) is not None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
