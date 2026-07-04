#!/usr/bin/env python3
"""Render the Gemini 3.1 Pro High harness prompt from a YAML task card.

Usage:
    python examples/harnesses/gemini-31-pro-high/render_harness.py examples/harnesses/gemini-31-pro-high/task-card.yaml

This helper intentionally has a tiny surface area. It does not call any model. It only turns a structured task card into a prompt that can be pasted into Gemini, Hermes, Cline, OpenCode, or another agent harness.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


def _as_block(value: Any) -> str:
    """Render a YAML value as a readable prompt block."""
    if value is None:
        return "UNKNOWN"
    if isinstance(value, str):
        return value.strip() or "UNKNOWN"
    if isinstance(value, list):
        if not value:
            return "UNKNOWN"
        return "\n".join(f"- {item}" for item in value)
    return str(value)


def render(task: dict[str, Any]) -> str:
    goal = _as_block(task.get("goal"))
    current_context = _as_block(task.get("current_context"))
    invariants = _as_block(task.get("invariants"))
    non_goals = _as_block(task.get("non_goals"))
    existing_decisions = _as_block(task.get("existing_decisions"))
    pain_point = _as_block(task.get("pain_point"))
    desired_output = _as_block(task.get("desired_output"))

    return f"""You are not the final decision maker.
You are a creative design candidate generator and scope-trimming editor.

Your goal is to preserve the user's real intent and current task boundaries while using Gemini's creative strength to produce better design candidates.

[OPERATING RULES]
1. Do not solve immediately. First restate the goal, constraints, non-goals, and missing information.
2. Produce at least three distinct design options.
3. For every option, include risks and features to discard.
4. Before selecting a final direction, remove over-design, scope creep, and unrequested features.
5. Do not reverse existing decisions unless explicitly instructed.
6. If information is missing, write UNKNOWN instead of inventing details.
7. End with a compressed handoff prompt for the next execution model.
8. Do not claim final correctness. Your output still needs validation.

[TASK CARD]
Goal:
{goal}

Current Context:
{current_context}

Invariants:
{invariants}

Non-goals:
{non_goals}

Existing Decisions:
{existing_decisions}

Pain Point:
{pain_point}

Desired Output:
{desired_output}

[OUTPUT FORMAT]

1. UNDERSTANDING
- Understood goal:
- Critical constraints:
- Non-goals:
- Missing or ambiguous information:
- Success criteria:

2. DESIGN OPTIONS

A.
- Core idea:
- Why it fits the goal:
- Pros:
- Risks:
- MVP:
- Discard:

B.
- Core idea:
- Why it fits the goal:
- Pros:
- Risks:
- MVP:
- Discard:

C.
- Core idea:
- Why it fits the goal:
- Pros:
- Risks:
- MVP:
- Discard:

3. TRIMMED FINAL DESIGN
- Selected direction:
- Why this direction:
- Minimal MVP:
- Explicitly out of scope:
- Fallback if this fails:

4. DRIFT CHECK
- Status: PASS | NEEDS_TRIM | FAIL
- Goal drift:
- Invariant violations:
- Non-goal invasion:
- Existing decision reversal:
- Over-design:
- What must be removed before execution:

5. HANDOFF PROMPT
Write a concise prompt, under 1000 characters, for the next execution model.
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a Gemini 3.1 Pro High design harness prompt.")
    parser.add_argument("task_card", type=Path, help="Path to a YAML task card.")
    args = parser.parse_args()

    data = yaml.safe_load(args.task_card.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("Task card must be a YAML mapping/object.")

    print(render(data))


if __name__ == "__main__":
    main()
