#!/usr/bin/env bash
set -euo pipefail
python -m pytest -q
python - <<'PY'
from lin3d_flash_benchmark.config import Settings
from lin3d_flash_benchmark.service import BenchmarkService
print(BenchmarkService(Settings.from_env()).health())
PY
