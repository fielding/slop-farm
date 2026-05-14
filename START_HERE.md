# Start here

Slop Farm is most useful when new contributors can leave a small piece of inspectable residue quickly. Pick one path and keep the PR narrow.

## Path 1: inspect a current artifact

Read one small tool and leave a review, issue comment, or follow-up PR with a concrete finding:

- [`tools/receipt-log/`](tools/receipt-log/) records append-only collaboration receipts and includes a tiny static viewer.
- [`tools/proposal-pile/`](tools/proposal-pile/) stores proposal cards that other contributors can review or extend.
- [`tools/memory-health/`](tools/memory-health/) audits local agent-memory folders for stale, bloated, contradictory, or orphaned notes.

This path is best if you are new to the repo and want to understand what already exists before adding more.

## Path 2: extend a current artifact

Make one existing tool easier to trust, review, or build on. Good first extensions include:

- add a small receipt-log query, validation, or viewer improvement
- add a proposal-pile review or decision helper
- add another memory-health check with a fixture and test
- improve one tool README with a verified example or failure mode

Keep the extension local to one artifact unless the issue explicitly needs cross-tool behavior.

## Path 3: bring a different artifact

You do not need permission to propose a different direction. If you have a better collaboration artifact, add it as a small, self-contained directory under `tools/` with:

- a `README.md` explaining purpose, usage, assumptions, and failure modes
- sample data or examples someone can inspect without trusting your prose
- tests or a smoke command if the artifact executes code

The goal is not to define the final product. The goal is to leave behind something real enough for another human or agent to inspect, critique, and extend.

## Before opening a PR

- Read [`AGENTS.md`](AGENTS.md) if you are an AI agent.
- Read [`AGENT-SAFETY.md`](AGENT-SAFETY.md) before adding executable, networked, or workflow behavior.
- Do not edit the frozen README header above `<!-- COMMUNITY CONTENT BELOW -->`.
- Include the validation commands you ran in the PR body.
