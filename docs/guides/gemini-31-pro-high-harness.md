# Gemini 3.1 Pro High Standalone Opus-Like Harness

This guide adds a standalone harness for using Gemini 3.1 Pro High as a single-model design system.

The goal is not to create a multi-model workflow. The goal is to make Gemini behave more like an Opus-style designer by forcing it through stable internal phases:

```text
intent lock → context pruning → design candidates → self-critique → reductive edit → drift check → final plan
```

Use this harness when Gemini's creativity is valuable, but loose prompts cause drift, over-design, forgotten constraints, or long-context degradation.

## What this harness tries to emulate

Opus-like design behavior usually means:

- preserving the user's actual intent
- identifying non-goals and scope boundaries
- resisting unnecessary architecture changes
- choosing what to discard
- producing a small, testable plan
- separating assumptions from facts
- making a final decision without pretending uncertainty vanished

This harness asks Gemini to simulate those behaviors inside one response.

## Model role

Use Gemini 3.1 Pro High as a standalone:

- intent interpreter
- creative design generator
- skeptical reviewer
- reductive editor
- final design planner

Do not require a second model for the harness to function.

## Required input shape

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

## Internal phases

The harness forces Gemini through these phases:

1. **Intent Lock** — restate the goal, invariants, non-goals, missing information, and success criteria.
2. **Context Pruning** — decide what context matters now and what should be ignored.
3. **Candidate Design** — create three distinct designs.
4. **Opus-Style Self-Critique** — attack each design for drift, over-design, fragile assumptions, and implementation risk.
5. **Reductive Edit** — discard 80% of nice-to-have ideas and keep the smallest viable design.
6. **Final Plan** — pick one direction and produce a compact implementation handoff.
7. **Drift Check** — verify that the final plan still serves the original task.

## Harness prompt

Use the standalone prompt in [`../../examples/harnesses/gemini-31-pro-high/harness.md`](../../examples/harnesses/gemini-31-pro-high/harness.md).

## When to use it

Good fits:

- creative-system design
- architecture planning
- worldbuilding system rules
- automation strategy
- product feature scoping
- prompt/agent harness design
- refactor planning before execution

Poor fits:

- direct implementation without a plan
- security-critical final approval
- destructive automation without human confirmation
- very short one-off answers

## Practical usage in Hermes, Antigravity, Cline, or OpenCode

Use Gemini with this harness as a **single design agent**.

Recommended behavior:

```text
Gemini 3.1 Pro High Standalone Harness
= understand intent
= design options
= self-critique
= trim scope
= choose final MVP
= produce handoff prompt
```

Then paste or route the final handoff prompt to whatever executor you prefer.

The harness itself assumes no second model. It only needs a filled task card.
