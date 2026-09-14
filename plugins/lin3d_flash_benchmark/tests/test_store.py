from pathlib import Path

from lin3d_flash_benchmark.schemas import RunStatus
from lin3d_flash_benchmark.store import RunStore


def test_store_round_trip(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "runs.sqlite3")
    created = store.create(run_id="run-1", label="test", run_dir=tmp_path / "run", request={"x": 1})
    assert created.status == RunStatus.QUEUED
    updated = store.update("run-1", status=RunStatus.RUNNING, pid=123)
    assert updated.status == RunStatus.RUNNING
    assert updated.pid == 123
    assert store.get("run-1").request == {"x": 1}
