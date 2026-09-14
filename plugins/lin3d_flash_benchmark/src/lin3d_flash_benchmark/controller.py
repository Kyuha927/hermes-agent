from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .config import Settings
from .process import write_json_atomic
from .schemas import TaskSpec
from .worker import run_task


def execute_manifest(manifest_path: Path) -> dict[str, object]:
    settings = Settings.from_env()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    run_dir = Path(manifest["run_dir"])
    matrix_path = Path(manifest["task_matrix"])
    evidence_dir = Path(manifest["evidence_bundle"])
    schema_path = Path(manifest["evidence_schema"])
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    default_evidence = [str(p) for p in sorted(evidence_dir.rglob("*")) if p.is_file()]
    tasks = []
    for item in matrix["tasks"]:
        task = TaskSpec.model_validate(item)
        if not task.evidence_paths:
            task = task.model_copy(update={"evidence_paths": default_evidence})
        tasks.append(task)
    max_workers = min(int(manifest["max_workers"]), settings.max_workers, 8)
    worker_dir = run_dir / "workers"
    worker_dir.mkdir(parents=True, exist_ok=True)
    results = []
    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="flash38") as pool:
        futures = {
            pool.submit(run_task, task, worker_dir, settings, evidence_dir, schema_path): task
            for task in tasks
        }
        for future in as_completed(futures):
            results.append(future.result().model_dump(mode="json"))
    aggregate = {
        "status": "SUCCEEDED" if all(r["status"] == "SUCCEEDED" for r in results) else "PARTIAL",
        "worker_model": settings.flash_model,
        "max_workers": max_workers,
        "task_count": len(tasks),
        "results": sorted(results, key=lambda item: item["task_id"]),
    }
    write_json_atomic(run_dir / "worker_aggregate.json", aggregate)
    return aggregate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()
    result = execute_manifest(Path(args.manifest))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
