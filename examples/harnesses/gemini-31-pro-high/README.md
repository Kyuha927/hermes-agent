# Gemini 3.1 Pro High Harness Example

This example packages a strict prompt harness for Gemini 3.1 Pro High.

It is for cases where Gemini's creative expansion is useful, but the workflow needs Opus-like discipline around intent, scope, non-goals, and drift checks.

## Files

- `harness.md` — copy-paste prompt template.
- `task-card.yaml` — structured task card example.
- `render_harness.py` — tiny helper that renders a task card into a full prompt.

## Render a prompt

From the repository root:

```bash
python examples/harnesses/gemini-31-pro-high/render_harness.py examples/harnesses/gemini-31-pro-high/task-card.yaml
```

Paste the rendered prompt into Gemini 3.1 Pro High, or pass it to a Hermes/OpenCode/Cline agent that uses Gemini as a design candidate generator.

## Recommended model split

```text
Gemini 3.1 Pro High = creative candidate generation and long-context digestion
M3 or GPT-5.4       = intent compression and over-design trimming
GPT-5.5             = risk candidate discovery
GLM or DeepSeek Pro = technical blocker triage
Kimi                = implementation
Opus/Fable          = final high-stakes design review
```

## Why this exists

Gemini can be excellent at creative design and long-context exploration, but it may drift when instructions are loose or stale context grows too large. This harness keeps it inside a narrow operating envelope:

```text
understand → generate candidates → trim → drift check → handoff
```

Do not skip the drift check when the output will drive automation or implementation.
