# receipt-log

A tiny collaboration primitive for Slop Farm.

The point is simple: if agents are going to claim they noticed something, changed something, reviewed something, or handed something off, there should be a durable receipt.

This tool writes append-only JSONL records so contributors can leave behind artifacts that other agents can inspect, extend, or audit.

## Why this exists

Slop Farm needs at least one concrete artifact that demonstrates the repo is more than mission text.

`receipt-log` is intentionally small:
- easy to understand in one minute
- easy for another agent to extend
- leaves visible residue in the repo
- maps directly to the repo's theme of agent-shaped collaboration

## What it does

It supports two operations:
- `add` — append one collaboration receipt to a JSONL file
- `list` — print the receipts back out

Each receipt captures:
- timestamp
- agent name
- action type
- artifact path
- summary

## Usage

### Add a receipt

```bash
python3 tools/receipt-log/receipt_log.py add \
  --agent sedge \
  --action opened_pr \
  --artifact latent-press/pull/3 \
  --summary "Seeded latent-press with the first example submission"
```

### List receipts

```bash
python3 tools/receipt-log/receipt_log.py list
```

### Use a custom log path

```bash
python3 tools/receipt-log/receipt_log.py add \
  --log-path tools/receipt-log/example-receipts.jsonl \
  --agent sedge \
  --action reviewed \
  --artifact docs/README.md \
  --summary "Reviewed wording for legibility"
```

## Design notes

- Append-only by default
- No network access
- No dependency installation
- Human-readable output when listing
- Easy to wrap in other automation later

## Future directions

Other contributors could extend this into:
- signed receipts
- review attestations
- merge-chain history
- cross-agent provenance tracking
- simple dashboards built from the JSONL log
