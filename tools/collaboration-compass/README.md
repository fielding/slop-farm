# Collaboration Compass

A tiny, local-only rubric for turning “this might improve human/AI collaboration” into an inspectable proposal scorecard.

It is intentionally not an optimizer and not a judge. It asks for a feature idea in JSON, scores a few reviewable dimensions, and prints the weak spots another contributor should inspect before building.

## Input

Create a JSON file with these fields:

```json
{
  "title": "Receipt-review handoff queue",
  "problem": "Agents leave receipts, but humans need a quick way to see what changed and what needs review.",
  "users": ["human maintainer", "agent contributor"],
  "artifact": "A local report that groups receipts by changed file and risk note.",
  "human_benefit": "Humans can review residue without reading every JSONL line.",
  "agent_benefit": "Agents get a clearer target for useful follow-up work.",
  "review_plan": "Run the report against fixture receipts and compare it to the raw log.",
  "risks": ["Could over-summarize important context"],
  "rollback": "Delete the generated report; no source data is changed."
}
```

## Usage

Safe/default mode reads one local JSON file and prints a Markdown scorecard:

```bash
python3 tools/collaboration-compass/compass.py examples/idea.json
```

There is no network access, no dependency install, and no file mutation.

## Scoring

The compass awards one point for each inspectable collaboration property:

- named human-side benefit
- named agent-side benefit
- concrete artifact/residue
- review plan
- explicit risks
- rollback path
- at least two user roles/stakeholders

Scores are prompts, not authority:

- `6-7`: buildable enough for a small PR
- `4-5`: needs one sharper review hook
- `0-3`: still mostly vibes

## Failure modes

- The rubric can reward well-written bad ideas; reviewers still need judgment.
- Sparse input produces sparse output instead of inventing confidence.
- This tool does not validate safety beyond checking whether risks and rollback were named.
