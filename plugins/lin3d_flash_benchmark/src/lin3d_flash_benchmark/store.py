from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .schemas import RunRecord, RunStatus


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class RunStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    label TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    run_dir TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    pid INTEGER,
                    return_code INTEGER,
                    error TEXT
                )
                """
            )

    def create(self, *, run_id: str, label: str, run_dir: Path, request: dict[str, Any]) -> RunRecord:
        now = utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO runs (
                    run_id, label, status, created_at, updated_at, run_dir, request_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    label,
                    RunStatus.QUEUED.value,
                    now,
                    now,
                    str(run_dir),
                    json.dumps(request, ensure_ascii=False, sort_keys=True),
                ),
            )
        return self.get(run_id)

    def update(self, run_id: str, **fields: Any) -> RunRecord:
        allowed = {"status", "pid", "return_code", "error"}
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"Unknown run fields: {sorted(unknown)}")
        if "status" in fields and isinstance(fields["status"], RunStatus):
            fields["status"] = fields["status"].value
        fields["updated_at"] = utc_now()
        assignments = ", ".join(f"{key} = ?" for key in fields)
        values = list(fields.values()) + [run_id]
        with self._connect() as connection:
            cursor = connection.execute(f"UPDATE runs SET {assignments} WHERE run_id = ?", values)
            if cursor.rowcount != 1:
                raise KeyError(run_id)
        return self.get(run_id)

    def get(self, run_id: str) -> RunRecord:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(run_id)
        return RunRecord(
            run_id=row["run_id"],
            label=row["label"],
            status=RunStatus(row["status"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            run_dir=row["run_dir"],
            request=json.loads(row["request_json"]),
            pid=row["pid"],
            return_code=row["return_code"],
            error=row["error"],
        )

    def list_recent(self, limit: int = 20) -> list[RunRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT run_id FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self.get(row["run_id"]) for row in rows]
