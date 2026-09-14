# LIN 3D Flash Benchmark — Web ChatGPT App

A fail-closed remote MCP app that reuses the existing Codex/Hermes/Antigravity/Blender stack to benchmark **Gemini 3.8 Flash (High)** on bounded LIN ASTER Blender QA tasks.

## Roles

- **Web ChatGPT app:** launch/status/results UI and permission boundary.
- **Codex / GPT-5.6 Sol:** sole controller and integrator.
- **Gemini 3.8 Flash High:** isolated blind workers, up to eight in parallel.
- **GPT-5.6 Pro:** unresolved scoring disputes only.
- **Astra:** disabled for this benchmark.
- **Blender Pro Bridge / MCP / headless / GUI:** evidence routes; production writes remain disabled.

## Safety defaults

- `LIN3D_ENABLE_EXECUTION=0`: preflight only.
- `LIN3D_ENABLE_ROUTING_WRITES=0`: promotion creates a review artifact only.
- Every supplied file must resolve under `LIN3D_ALLOWED_ROOTS`.
- Worker processes never receive the hidden-gold path or GOLD-named environment variables.
- The app accepts no shell command, executable path, model override, or arbitrary environment from ChatGPT tool input.
- Cancellation targets only the controller process group owned by the selected run.
- No production GLB, canon, `.blend`, Tripo credit, or account setting may be modified.

## Tools exposed to ChatGPT

1. `app_health`
2. `benchmark_preflight`
3. `start_flash_benchmark`
4. `benchmark_status`
5. `benchmark_results`
6. `cancel_flash_benchmark`
7. `promote_routing`

`start_flash_benchmark(..., execute=false)` creates a complete dry-run manifest. Actual execution additionally requires `LIN3D_ENABLE_EXECUTION=1` on the server.

## Install

```bash
cd plugins/lin3d_flash_benchmark
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
```

Prerequisites:

- Codex CLI authenticated and available as `codex`.
- Antigravity CLI authenticated and available as `agy`.
- `agy --model 'Gemini 3.8 Flash (High)'` must pass a one-line smoke.
- The benchmark packet, task matrix, policy, schema and hidden-gold evidence must exist below the allowlisted root.

## Run and connect to Web ChatGPT

```bash
set -a; source .env; set +a
lin3d-flash-benchmark
```

The MCP server uses streamable HTTP. For a server on a local/private Mac, connect it through **Secure MCP Tunnel**; Web ChatGPT cannot connect directly to localhost. In ChatGPT developer mode, create a custom app and scan the tunnel MCP endpoint. OpenAI currently documents full write/action MCP support for Business and Enterprise/Edu; Pro availability may be limited to read/fetch actions. The app itself is ready either way, and `app_health`, preflight, status and results remain read-oriented.

Do not put a public unauthenticated endpoint on the internet. Use tunnel/workspace authentication and set app permissions to **ask before writes**.

## One-click prompt

```text
@LIN 3D Flash Benchmark
Run app_health. If healthy, preflight the R14H benchmark packet with max_workers=8.
Show blockers. Do not execute until I explicitly say 실행.
```

After approval:

```text
Start the preflighted benchmark with execute=true. Keep production mutation off, use Codex GPT-5.6 Sol as controller, Gemini 3.8 Flash High as blind workers, and no Astra.
```

## Expected controller artifacts

- `worker_aggregate.json`
- `benchmark_result.json`
- `promotion_candidate.json`
- `controller_receipt.json`

The Codex controller is instructed to run the packaged `lin3d-flash-controller` command and then score against the hidden gold. The hidden gold is present only in the controller manifest; workers receive task prompts and explicitly listed evidence paths only.

## Current limitation

This repository change builds and tests the app source. Registering the app in a specific ChatGPT workspace and starting the Secure MCP Tunnel require that workspace's developer-mode permission and the user's authenticated Mac session; those credentials are intentionally not committed.
