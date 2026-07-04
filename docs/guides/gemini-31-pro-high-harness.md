# Gemini 3.1 Pro High Design Harness

This guide adds a strict harness for using Gemini 3.1 Pro High as a creative design candidate generator while reducing drift, over-expansion, and long-context degradation.

The harness is designed for workflows where Gemini is strong at creative expansion and multimodal/long-context ingestion, but should not be trusted as the final design judge.

## Model role

Use Gemini 3.1 Pro High for:

- creative design options
- worldbuilding and branch expansion
- long document, log, screenshot, or repository context digestion
- candidate generation
- handoff prompt creation for another execution model

Avoid using Gemini 3.1 Pro High as the only authority for:

- final technical approval
- destructive automation approval
- final security judgment
- one-shot architecture decisions without a drift check

## Recommended pipeline

```text
1. Compress intent and constraints.
2. Ask Gemini for 3 design candidates.
3. Ask Gemini to trim its own candidates.
4. Run a drift check against the original task card.
5. Hand the compressed plan to an execution or validation model.
```

Best companion roles:

```text
Gemini 3.1 Pro High = creative candidate generator
M3 or GPT-5.4       = intent compression / scope trimming
GPT-5.5             = risk candidate finder
GLM or DeepSeek Pro = technical blocker triage
Opus or Fable       = final high-stakes design judgment
Kimi                = fast implementation
```

## Task card discipline

Never give Gemini a raw long chat transcript when design quality matters. Give it a task card.

```text
[TASK CARD]

Goal:
{one concrete goal}

Current Context:
{1000-3000 characters of relevant context}

Invariants:
{rules that must not be broken}

Non-goals:
{things this task must not do}

Existing Decisions:
{decisions already made}

Pain Point:
{what is currently failing or unclear}

Desired Output:
{exact output format}

Stop Rule:
If information is missing, mark UNKNOWN instead of guessing.
```

## Harness prompt

Use the prompt in [`../../examples/harnesses/gemini-31-pro-high/harness.md`](../../examples/harnesses/gemini-31-pro-high/harness.md).

## Drift check rule

The drift check is mandatory. If Gemini returns `NEEDS_TRIM` or `FAIL`, do not execute the plan. Trim the plan first or send the plan to a separate validator.

Required drift checks:

1. Does the answer directly serve the original goal?
2. Did it violate any invariant?
3. Did it invade a non-goal?
4. Did it reverse an existing decision without permission?
5. Did it add unrequested features?
6. Can the MVP be smaller?

## Practical usage in Hermes

A useful Hermes setup is:

```text
router/design-agent:
  model: Gemini 3.1 Pro High
  role: candidate generation only

validation-agent:
  model: GLM-5.2 Max or DeepSeek V4 Pro
  role: technical blocker triage

execution-agent:
  model: Kimi K2.7 or Gemini execution layer
  role: implement the final handoff prompt

final-review-agent:
  model: Opus/Fable, only for high-stakes design calls
```

Keep Gemini away from direct destructive tools unless another agent has already approved the plan.
