#!/usr/bin/env python3
"""Score a human/AI collaboration feature idea as an inspectable Markdown card."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REQUIRED_TEXT_FIELDS = (
    "title",
    "problem",
    "artifact",
    "human_benefit",
    "agent_benefit",
    "review_plan",
    "rollback",
)


@dataclass(frozen=True)
class Check:
    key: str
    label: str
    passed: bool
    note: str


def _clean_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _clean_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def load_idea(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"Expected a JSON object in {path}")
    return data


def evaluate(idea: dict[str, Any]) -> list[Check]:
    users = _clean_list(idea.get("users"))
    risks = _clean_list(idea.get("risks"))
    return [
        Check(
            "human_benefit",
            "Human benefit is named",
            bool(_clean_text(idea.get("human_benefit"))),
            _clean_text(idea.get("human_benefit")) or "missing",
        ),
        Check(
            "agent_benefit",
            "Agent benefit is named",
            bool(_clean_text(idea.get("agent_benefit"))),
            _clean_text(idea.get("agent_benefit")) or "missing",
        ),
        Check(
            "artifact",
            "Concrete residue/artifact exists",
            bool(_clean_text(idea.get("artifact"))),
            _clean_text(idea.get("artifact")) or "missing",
        ),
        Check(
            "review_plan",
            "Review plan is explicit",
            bool(_clean_text(idea.get("review_plan"))),
            _clean_text(idea.get("review_plan")) or "missing",
        ),
        Check(
            "risks",
            "Risks are named",
            bool(risks),
            "; ".join(risks) if risks else "missing",
        ),
        Check(
            "rollback",
            "Rollback path is named",
            bool(_clean_text(idea.get("rollback"))),
            _clean_text(idea.get("rollback")) or "missing",
        ),
        Check(
            "users",
            "At least two stakeholders are named",
            len(users) >= 2,
            ", ".join(users) if users else "missing",
        ),
    ]


def recommendation(score: int) -> str:
    if score >= 6:
        return "Buildable enough for a small, reviewable PR."
    if score >= 4:
        return "Promising, but sharpen one or two review hooks before building."
    return "Still mostly vibes; name the artifact, review plan, and rollback before building."


def render_markdown(idea: dict[str, Any], checks: list[Check]) -> str:
    title = _clean_text(idea.get("title")) or "Untitled collaboration idea"
    problem = _clean_text(idea.get("problem")) or "No problem statement provided."
    score = sum(1 for check in checks if check.passed)
    lines = [
        f"# Collaboration Compass: {title}",
        "",
        f"**Score:** {score}/{len(checks)} — {recommendation(score)}",
        "",
        "## Problem",
        problem,
        "",
        "## Checks",
    ]
    for check in checks:
        marker = "✅" if check.passed else "⚠️"
        lines.append(f"- {marker} **{check.label}:** {check.note}")
    missing = [field for field in REQUIRED_TEXT_FIELDS if not _clean_text(idea.get(field))]
    if missing:
        lines.extend(["", "## Missing text fields", ", ".join(missing)])
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("idea_json", type=Path, help="Path to a local collaboration idea JSON file")
    args = parser.parse_args(argv)
    idea = load_idea(args.idea_json)
    sys.stdout.write(render_markdown(idea, evaluate(idea)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
