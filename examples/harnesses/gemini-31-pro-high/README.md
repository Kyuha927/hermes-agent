# Gemini 3.1 Pro High Standalone Harness Example

This example packages a strict standalone prompt harness for Gemini 3.1 Pro High.

It is for cases where Gemini's creative expansion is useful, but the workflow needs Opus-like discipline around intent, scope, non-goals, self-critique, reductive editing, and drift checks.

The harness does not require any companion model. Gemini must run the full design loop by itself.

## Files

- `harness.md` — copy-paste standalone prompt template.
- `task-card.yaml` — structured task card example.
- `render_harness.py` — tiny helper that renders a task card into a full prompt.

## Render a prompt

From the repository root:

```bash
python examples/harnesses/gemini-31-pro-high/render_harness.py examples/harnesses/gemini-31-pro-high/task-card.yaml
```

Paste the rendered prompt into Gemini 3.1 Pro High, or use it inside Antigravity, Hermes, Cline, OpenCode, or another tool where Gemini is the only design model.

## Standalone loop

```text
intent lock
→ context pruning
→ three design candidates
→ Opus-style self-critique
→ reductive edit
→ final design
→ drift check
→ implementation handoff
```

## Why this exists

Gemini can be excellent at creative design and long-context exploration, but it may drift when instructions are loose or stale context grows too large. This harness narrows its operating envelope without depending on Opus, GLM, GPT, M3, or any other model.

Use it when you want Gemini Pro High to act less like a free-form idea generator and more like a disciplined design architect.
