#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec python -m lin3d_flash_benchmark.server
