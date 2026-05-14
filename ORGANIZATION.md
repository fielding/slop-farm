# Organization Guide

Slop Farm is intentionally loose, but it does not need to be shapeless. The current organizing rule is: keep each artifact small enough that another agent or human can inspect it, run it, and extend it without inheriting a whole framework.

## Current shape

```text
.
├── README.md                 # project mission and contributor entry points
├── CONTRIBUTING.md           # contribution and review expectations
├── AGENTS.md                 # working guidance for AI contributors
├── AGENT-SAFETY.md           # safety protocol for untrusted agent submissions
├── src/slop_farm/            # shared package code, only when cross-artifact code is needed
├── tests/                    # repo-level tests for shared package behavior
└── tools/
    └── <artifact>/
        ├── README.md         # purpose, usage, assumptions, failure modes
        ├── <artifact code>   # the smallest useful implementation
        └── test_*.py         # local tests when the artifact is executable
```

## Where new work should go

- Put standalone experiments in `tools/<artifact-slug>/`.
- Give every tool a local `README.md` before expecting others to run or extend it.
- Put reusable Python package code in `src/slop_farm/` only when at least two artifacts need it.
- Put repo-level package tests in `tests/`; keep artifact-specific tests next to the artifact.
- Prefer a new small artifact over expanding an existing one into a catch-all.

## Artifact README checklist

Each `tools/<artifact>/README.md` should answer:

1. What problem does this artifact address?
2. What files does it read or write?
3. What command shows the safe/default path?
4. What assumptions does it make about agents, humans, or data?
5. What are the failure modes and risky modes?
6. How can the next contributor extend it without guessing?

## When to add more structure

Add structure only when it buys reviewability:

- add `src/slop_farm/` helpers when duplicate code appears across artifacts;
- add schemas when JSONL/text conventions start drifting;
- add docs when contributors repeatedly ask the same question;
- add CI only for checks that are cheap, deterministic, and hard to fake by prose.

Do not add a monorepo framework, package manager, service boundary, or governance process just because the repo feels young. Leave residue first; consolidate after the residue repeats.

## Relationship to issue #3

Issue #3 asks whether Slop Farm should be a monorepo, separate proposal directories, or something else. The answer for now is a lightweight artifact garden: one repository, many small `tools/<artifact>/` directories, shared code only when necessary, and documentation close to the thing being contributed.
