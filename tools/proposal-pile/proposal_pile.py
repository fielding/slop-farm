#!/usr/bin/env python3
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

DEFAULT_LOG_PATH = Path("tools/proposal-pile/proposals.jsonl")
REQUIRED_FIELDS = ("proposal_id", "timestamp", "agent", "title", "summary", "status")
VALID_STATUSES = {"proposed", "adopted", "rejected", "superseded"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def make_proposal_id(timestamp: str, agent: str, title: str, summary: str) -> str:
    payload = "\n".join([timestamp, agent, title, summary])
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"prp_{digest}"


def build_proposal(
    agent: str,
    title: str,
    summary: str,
    status: str,
    artifact: str | None,
    rationale: str | None,
    next_step: str | None,
    parent_proposal: str | None,
) -> dict[str, Any]:
    timestamp = utc_now()
    proposal = {
        "proposal_id": make_proposal_id(timestamp, agent, title, summary),
        "timestamp": timestamp,
        "agent": agent,
        "title": title,
        "summary": summary,
        "status": status,
    }
    if artifact:
        proposal["artifact"] = artifact
    if rationale:
        proposal["rationale"] = rationale
    if next_step:
        proposal["next_step"] = next_step
    if parent_proposal:
        proposal["parent_proposal"] = parent_proposal
    return proposal


def append_proposal(
    log_path: Path,
    agent: str,
    title: str,
    summary: str,
    status: str,
    artifact: str | None,
    rationale: str | None,
    next_step: str | None,
    parent_proposal: str | None,
) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    proposal = build_proposal(agent, title, summary, status, artifact, rationale, next_step, parent_proposal)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(proposal, ensure_ascii=False) + "\n")
    print(f"appended proposal {proposal['proposal_id']} to {log_path}")


def parse_proposals(log_path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    proposals: list[dict[str, Any]] = []
    errors: list[str] = []

    if not log_path.exists():
        return proposals, errors

    with log_path.open("r", encoding="utf-8") as f:
        for i, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as e:
                errors.append(f"[{i}] invalid json: {e}")
                continue
            if not isinstance(item, dict):
                errors.append(f"[{i}] expected object, got {type(item).__name__}")
                continue
            proposals.append(item)
    return proposals, errors


def validate_proposals(log_path: Path) -> int:
    if not log_path.exists():
        print(f"no proposals yet at {log_path}")
        return 0

    proposals, errors = parse_proposals(log_path)
    seen_ids: set[str] = set()

    for i, item in enumerate(proposals, start=1):
        missing = [field for field in REQUIRED_FIELDS if not item.get(field)]
        if missing:
            errors.append(f"[{i}] missing required fields: {', '.join(missing)}")

        proposal_id = item.get("proposal_id")
        if proposal_id:
            if proposal_id in seen_ids:
                errors.append(f"[{i}] duplicate proposal_id: {proposal_id}")
            seen_ids.add(proposal_id)

        status = item.get("status")
        if status and status not in VALID_STATUSES:
            errors.append(f"[{i}] invalid status: {status}")

    if errors:
        print(f"validation failed for {log_path}", file=sys.stderr)
        for err in errors:
            print(f"- {err}", file=sys.stderr)
        return 1

    print(f"validated {len(proposals)} proposals in {log_path}")
    return 0


def list_proposals(log_path: Path) -> int:
    if not log_path.exists():
        print(f"no proposals yet at {log_path}")
        return 0

    proposals, errors = parse_proposals(log_path)
    for err in errors:
        print(err, file=sys.stderr)

    for i, item in enumerate(proposals, start=1):
        print(f"[{i}] {item.get('timestamp')} | {item.get('status')} | {item.get('proposal_id')}")
        print(f"    title:    {item.get('title')}")
        print(f"    summary:  {item.get('summary')}")
        print(f"    agent:    {item.get('agent')}")
        if item.get("artifact"):
            print(f"    artifact: {item.get('artifact')}")
        if item.get("next_step"):
            print(f"    next:     {item.get('next_step')}")
        if item.get("parent_proposal"):
            print(f"    parent:   {item.get('parent_proposal')}")
    return 1 if errors else 0


def summarize_proposals(log_path: Path, json_output: bool = False) -> int:
    if not log_path.exists():
        print(f"no proposals yet at {log_path}")
        return 0

    proposals, errors = parse_proposals(log_path)
    for err in errors:
        print(err, file=sys.stderr)

    status_counts: dict[str, int] = {}
    artifact_counts: dict[str, int] = {}
    for item in proposals:
        status = str(item.get("status") or "-")
        status_counts[status] = status_counts.get(status, 0) + 1
        artifact = str(item.get("artifact") or "-")
        artifact_counts[artifact] = artifact_counts.get(artifact, 0) + 1

    payload = {
        "log_path": str(log_path),
        "total_proposals": len(proposals),
        "status_counts": dict(sorted(status_counts.items())),
        "artifacts_touched": dict(sorted(artifact_counts.items())),
        "latest_proposal": proposals[-1] if proposals else None,
    }

    if json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1 if errors else 0

    print(f"log_path: {log_path}")
    print(f"total_proposals: {len(proposals)}")
    print("status_counts:")
    for status in sorted(status_counts):
        print(f"  {status}: {status_counts[status]}")
    print("artifacts_touched:")
    for artifact in sorted(artifact_counts):
        print(f"  {artifact}: {artifact_counts[artifact]}")
    if proposals:
        latest = proposals[-1]
        print("latest_proposal:")
        print(f"  proposal_id: {latest.get('proposal_id')}")
        print(f"  status:      {latest.get('status')}")
        print(f"  title:       {latest.get('title')}")
    return 1 if errors else 0


def find_open_proposals(proposals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return proposed rows that have not been resolved by a later child row."""
    resolved_parent_ids = {
        str(item.get("parent_proposal"))
        for item in proposals
        if item.get("parent_proposal") and item.get("status") in {"adopted", "rejected", "superseded"}
    }
    return [
        item
        for item in proposals
        if item.get("status") == "proposed" and item.get("proposal_id") not in resolved_parent_ids
    ]


def list_open_proposals(log_path: Path, json_output: bool = False) -> int:
    if not log_path.exists():
        print(f"no proposals yet at {log_path}")
        return 0

    proposals, errors = parse_proposals(log_path)
    for err in errors:
        print(err, file=sys.stderr)

    open_items = find_open_proposals(proposals)
    payload = {
        "log_path": str(log_path),
        "total_open_proposals": len(open_items),
        "open_proposals": open_items,
    }

    if json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1 if errors else 0

    print(f"log_path: {log_path}")
    print(f"total_open_proposals: {len(open_items)}")
    for item in open_items:
        print(f"- {item.get('proposal_id')} | {item.get('artifact') or '-'} | {item.get('title')}")
        if item.get("next_step"):
            print(f"  next: {item.get('next_step')}")
    return 1 if errors else 0


def inspect_proposal(log_path: Path, proposal_id: str, json_output: bool = False) -> int:
    if not log_path.exists():
        print(f"no proposals yet at {log_path}")
        return 0

    proposals, errors = parse_proposals(log_path)
    for err in errors:
        print(err, file=sys.stderr)

    match = next((item for item in proposals if item.get("proposal_id") == proposal_id), None)
    if match is None:
        print(f"proposal not found: {proposal_id}", file=sys.stderr)
        return 1

    if json_output:
        print(json.dumps({"log_path": str(log_path), "proposal": match}, ensure_ascii=False, indent=2))
        return 1 if errors else 0

    print(f"log_path: {log_path}")
    for key in ("proposal_id", "timestamp", "agent", "status", "title", "summary", "artifact", "rationale", "next_step", "parent_proposal"):
        if match.get(key):
            print(f"{key}: {match.get(key)}")
    return 1 if errors else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Append-only proposal pile for small collaboration ideas")
    parser.add_argument("--log-path", default=str(DEFAULT_LOG_PATH), help="Path to JSONL proposal log")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="Append a proposal")
    add_parser.add_argument("--agent", required=True)
    add_parser.add_argument("--title", required=True)
    add_parser.add_argument("--summary", required=True)
    add_parser.add_argument("--status", default="proposed", choices=sorted(VALID_STATUSES))
    add_parser.add_argument("--artifact")
    add_parser.add_argument("--rationale")
    add_parser.add_argument("--next-step")
    add_parser.add_argument("--parent-proposal")

    subparsers.add_parser("list", help="List proposals")
    subparsers.add_parser("validate", help="Validate proposal log structure")
    summary_parser = subparsers.add_parser("summary", help="Print compact proposal stats")
    summary_parser.add_argument("--json", action="store_true", help="Emit summary as JSON")
    open_parser = subparsers.add_parser("open", help="List unresolved proposed rows")
    open_parser.add_argument("--json", action="store_true", help="Emit open proposals as JSON")
    inspect_parser = subparsers.add_parser("inspect", help="Inspect one proposal by ID")
    inspect_parser.add_argument("proposal_id")
    inspect_parser.add_argument("--json", action="store_true", help="Emit proposal as JSON")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    log_path = Path(args.log_path)

    if args.command == "add":
        append_proposal(
            log_path,
            args.agent,
            args.title,
            args.summary,
            args.status,
            args.artifact,
            args.rationale,
            args.next_step,
            args.parent_proposal,
        )
        return 0
    if args.command == "list":
        return list_proposals(log_path)
    if args.command == "validate":
        return validate_proposals(log_path)
    if args.command == "summary":
        return summarize_proposals(log_path, json_output=args.json)
    if args.command == "open":
        return list_open_proposals(log_path, json_output=args.json)
    if args.command == "inspect":
        return inspect_proposal(log_path, args.proposal_id, json_output=args.json)

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
