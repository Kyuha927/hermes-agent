# Gemini 3.1 Pro High Standalone Opus-Like Harness

This guide adds a standalone harness for using Gemini 3.1 Pro High as a single-model design system.

The goal is not to create a multi-model workflow. The goal is to make Gemini behave more like an Opus-style designer by forcing it through stable internal phases:

```text
intent lock → context pruning → evidence map → design candidates → self-critique → reductive edit → drift/evidence check → final plan
```

Use this harness when Gemini's creativity is valuable, but loose prompts cause drift, over-design, forgotten constraints, unsupported leaps, or long-context degradation.

## What this harness tries to emulate

Opus-like design behavior usually means:

- preserving the user's actual intent
- identifying non-goals and scope boundaries
- resisting unnecessary architecture changes
- choosing what to discard
- producing a small, testable plan
- separating facts, assumptions, hypotheses, and unknowns
- avoiding unsupported inferential leaps
- making a final decision without pretending uncertainty vanished

This harness asks Gemini to simulate those behaviors inside one response.

## Anti-hallucination gates

Gemini Pro High can be creative enough to make plausible but unsupported jumps. The harness therefore includes explicit evidence control:

1. **No leap rule** — do not jump from a weak clue to a strong conclusion.
2. **Evidence map** — classify information as FACT, ASSUMPTION, HYPOTHESIS, or UNKNOWN before designing.
3. **Inference ladder** — when inferring, show evidence → inference → confidence.
4. **Confidence cap** — incomplete evidence cannot produce HIGH confidence.
5. **Decision guard** — hypotheses can shape candidates, but cannot become final reasons unless validated or accepted as risk.
6. **Claim budget** — only make claims needed for the task.

These gates reduce hallucination by making unsupported claims visible before they can become design decisions.

## Model role

Use Gemini 3.1 Pro High as a standalone:

- intent interpreter
- evidence mapper
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

Known Facts:
{facts that are explicitly given or directly observed}

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
3. **Evidence Map** — classify available information into facts, assumptions, hypotheses, and unknowns.
4. **Candidate Design** — create three distinct designs.
5. **Opus-Style Self-Critique** — attack each design for unsupported leaps, drift, over-design, fragile assumptions, and implementation risk.
6. **Reductive Edit** — discard 80% of nice-to-have ideas and keep the smallest viable design.
7. **Final Plan** — pick one direction and produce a compact implementation handoff.
8. **Drift and Evidence Check** — verify that the final plan still serves the original task and only relies on labeled evidence/assumptions.

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
= prune context
= map evidence
= design options
= self-critique
= trim scope
= choose final MVP
= run drift/evidence check
= produce handoff prompt
```

Then paste or route the final handoff prompt to whatever executor you prefer.

The harness itself assumes no second model. It only needs a filled task card.
