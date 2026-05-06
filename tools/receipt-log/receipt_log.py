#!/usr/bin/env python3
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

DEFAULT_LOG_PATH = Path("tools/receipt-log/receipts.jsonl")
REQUIRED_FIELDS = ("timestamp", "agent", "action", "artifact", "summary")
CORE_PROVENANCE_FIELDS = ("receipt_id", "source", "session", "host")
LINKAGE_FIELDS = ("parent_receipt",)
ALL_TRACKED_FIELDS = CORE_PROVENANCE_FIELDS + LINKAGE_FIELDS


def canonical_receipt_payload(receipt: dict[str, Any]) -> str:
    """Return the stable JSON payload used for receipt fingerprinting."""
    return json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def receipt_fingerprint(receipt: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_receipt_payload(receipt).encode("utf-8")).hexdigest()


def log_fingerprint(row_hashes: list[str]) -> str:
    return hashlib.sha256("\n".join(row_hashes).encode("utf-8")).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def make_receipt_id(timestamp: str, agent: str, action: str, artifact: str, summary: str) -> str:
    payload = "\n".join([timestamp, agent, action, artifact, summary])
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"rct_{digest}"


def build_receipt(
    agent: str,
    action: str,
    artifact: str,
    summary: str,
    source: str | None,
    session: str | None,
    host: str | None,
    parent_receipt: str | None,
) -> dict[str, Any]:
    timestamp = utc_now()
    receipt = {
        "receipt_id": make_receipt_id(timestamp, agent, action, artifact, summary),
        "timestamp": timestamp,
        "agent": agent,
        "action": action,
        "artifact": artifact,
        "summary": summary,
    }
    if source:
        receipt["source"] = source
    if session:
        receipt["session"] = session
    if host:
        receipt["host"] = host
    if parent_receipt:
        receipt["parent_receipt"] = parent_receipt
    return receipt


def append_receipt(
    log_path: Path,
    agent: str,
    action: str,
    artifact: str,
    summary: str,
    source: str | None,
    session: str | None,
    host: str | None,
    parent_receipt: str | None,
) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    receipt = build_receipt(agent, action, artifact, summary, source, session, host, parent_receipt)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(receipt, ensure_ascii=False) + "\n")
    print(f"appended receipt {receipt['receipt_id']} to {log_path}")


def parse_receipts(log_path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    receipts: list[dict[str, Any]] = []
    errors: list[str] = []

    if not log_path.exists():
        return receipts, errors

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
            receipts.append(item)
    return receipts, errors


def validate_receipts(log_path: Path) -> int:
    if not log_path.exists():
        print(f"no receipts yet at {log_path}")
        return 0

    receipts, errors = parse_receipts(log_path)
    seen_ids: set[str] = set()

    for i, item in enumerate(receipts, start=1):
        missing = [field for field in REQUIRED_FIELDS if not item.get(field)]
        if missing:
            errors.append(f"[{i}] missing required fields: {', '.join(missing)}")

        receipt_id = item.get("receipt_id")
        if receipt_id:
            if receipt_id in seen_ids:
                errors.append(f"[{i}] duplicate receipt_id: {receipt_id}")
            seen_ids.add(receipt_id)

    if errors:
        print(f"validation failed for {log_path}", file=sys.stderr)
        for err in errors:
            print(f"- {err}", file=sys.stderr)
        return 1

    print(f"validated {len(receipts)} receipts in {log_path}")
    if receipts:
        with_ids = sum(1 for item in receipts if item.get("receipt_id"))
        with_source = sum(1 for item in receipts if item.get("source"))
        with_session = sum(1 for item in receipts if item.get("session"))
        with_host = sum(1 for item in receipts if item.get("host"))
        print(f"- receipt_id coverage: {with_ids}/{len(receipts)}")
        print(f"- source coverage:     {with_source}/{len(receipts)}")
        print(f"- session coverage:    {with_session}/{len(receipts)}")
        print(f"- host coverage:       {with_host}/{len(receipts)}")
    return 0


def list_receipts(log_path: Path) -> int:
    if not log_path.exists():
        print(f"no receipts yet at {log_path}")
        return 0

    receipts, errors = parse_receipts(log_path)
    for err in errors:
        print(err, file=sys.stderr)

    for i, item in enumerate(receipts, start=1):
        receipt_id = item.get("receipt_id", "-")
        print(f"[{i}] {item.get('timestamp')} | {item.get('agent')} | {item.get('action')} | {receipt_id}")
        print(f"    artifact: {item.get('artifact')}")
        print(f"    summary:  {item.get('summary')}")
        if item.get("source"):
            print(f"    source:   {item.get('source')}")
        if item.get("session"):
            print(f"    session:  {item.get('session')}")
        if item.get("host"):
            print(f"    host:     {item.get('host')}")
        if item.get("parent_receipt"):
            print(f"    parent:   {item.get('parent_receipt')}")
    return 1 if errors else 0


def summarize_receipts(log_path: Path, json_output: bool = False) -> int:
    if not log_path.exists():
        print(f"no receipts yet at {log_path}")
        return 0

    receipts, errors = parse_receipts(log_path)
    for err in errors:
        print(err, file=sys.stderr)

    total = len(receipts)
    with_ids = sum(1 for item in receipts if item.get("receipt_id"))
    with_source = sum(1 for item in receipts if item.get("source"))
    with_session = sum(1 for item in receipts if item.get("session"))
    with_host = sum(1 for item in receipts if item.get("host"))
    with_parent = sum(1 for item in receipts if item.get("parent_receipt"))

    action_counts: dict[str, int] = {}
    legacy_rows = 0
    provenance_rich_rows = 0
    legacy_examples: list[str] = []
    for i, item in enumerate(receipts, start=1):
        action = str(item.get("action", "-"))
        action_counts[action] = action_counts.get(action, 0) + 1
        has_provenance = any(item.get(field) for field in ("receipt_id", "source", "session", "host", "parent_receipt"))
        if has_provenance:
            provenance_rich_rows += 1
        else:
            legacy_rows += 1
            legacy_examples.append(f"[{i}] {item.get('timestamp')} | {item.get('action')} | {item.get('artifact')}")

    if provenance_rich_rows > legacy_rows:
        migration_status = "provenance-rich rows now outnumber legacy rows"
    elif provenance_rich_rows < legacy_rows:
        migration_status = "legacy rows still outnumber provenance-rich rows"
    else:
        migration_status = "provenance-rich rows and legacy rows are tied"

    latest = receipts[-1] if receipts else None
    payload = {
        "log_path": str(log_path),
        "total_receipts": total,
        "provenance_coverage": {
            "receipt_id": f"{with_ids}/{total}",
            "source": f"{with_source}/{total}",
            "session": f"{with_session}/{total}",
            "host": f"{with_host}/{total}",
            "parent": f"{with_parent}/{total}",
        },
        "actions": dict(sorted(action_counts.items())),
        "migration_state": {
            "provenance_rich_rows": provenance_rich_rows,
            "legacy_rows": legacy_rows,
            "status": migration_status,
        },
        "legacy_examples": legacy_examples[:5],
        "latest_receipt": latest,
    }

    if json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1 if errors else 0

    print(f"log_path: {log_path}")
    print(f"total_receipts: {total}")

    if not receipts:
        return 1 if errors else 0

    print("provenance_coverage:")
    print(f"  receipt_id: {with_ids}/{total}")
    print(f"  source:     {with_source}/{total}")
    print(f"  session:    {with_session}/{total}")
    print(f"  host:       {with_host}/{total}")
    print(f"  parent:     {with_parent}/{total}")

    print("actions:")
    for action in sorted(action_counts):
        print(f"  {action}: {action_counts[action]}")

    print("migration_state:")
    print(f"  provenance_rich_rows: {provenance_rich_rows}")
    print(f"  legacy_rows:          {legacy_rows}")
    print(f"  status:               {migration_status}")

    if legacy_examples:
        print("legacy_examples:")
        for example in legacy_examples[:5]:
            print(f"  {example}")

    print("latest_receipt:")
    print(f"  timestamp: {latest.get('timestamp')}")
    print(f"  action:    {latest.get('action')}")
    print(f"  artifact:  {latest.get('artifact')}")
    print(f"  receipt_id:{' ' if latest.get('receipt_id') else ''}{latest.get('receipt_id', '-')}")

    return 1 if errors else 0


def report_gaps(log_path: Path, json_output: bool = False) -> int:
    if not log_path.exists():
        print(f"no receipts yet at {log_path}")
        return 0

    receipts, errors = parse_receipts(log_path)
    for err in errors:
        print(err, file=sys.stderr)

    rows_with_gaps: list[dict[str, Any]] = []
    core_gap_rows = 0
    linkage_gap_rows = 0
    for i, item in enumerate(receipts, start=1):
        missing_core = [field for field in CORE_PROVENANCE_FIELDS if not item.get(field)]
        missing_linkage = [field for field in LINKAGE_FIELDS if not item.get(field)]
        if not missing_core and not missing_linkage:
            continue

        if missing_core:
            core_gap_rows += 1
        elif missing_linkage:
            linkage_gap_rows += 1

        row = {
            "index": i,
            "timestamp": item.get("timestamp"),
            "action": item.get("action"),
            "artifact": item.get("artifact"),
            "missing_core": missing_core,
            "missing_linkage": missing_linkage,
            "summary": item.get("summary"),
        }
        rows_with_gaps.append(row)

    payload = {
        "log_path": str(log_path),
        "total_receipts": len(receipts),
        "core_gap_rows": {"present": core_gap_rows, "total": len(receipts)},
        "linkage_gap_rows": {"present": linkage_gap_rows, "total": len(receipts)},
        "status": {
            "core_provenance": "complete" if core_gap_rows == 0 else "needs_repair",
            "linkage": "complete" if linkage_gap_rows == 0 else "optional_gaps_remaining",
        },
        "core_gap_examples": [row for row in rows_with_gaps if row["missing_core"]][:5],
        "linkage_gap_examples": [row for row in rows_with_gaps if (not row["missing_core"] and row["missing_linkage"])][:5],
        "rows": rows_with_gaps,
    }

    if json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1 if errors else 0

    for row in rows_with_gaps:
        print(f"[{row['index']}] {row['timestamp']} | {row['action']} | {row['artifact']}")
        if row["missing_core"]:
            print(f"    missing_core:    {', '.join(row['missing_core'])}")
        if row["missing_linkage"]:
            print(f"    missing_linkage: {', '.join(row['missing_linkage'])}")
        print(f"    summary:         {row['summary']}")

    if core_gap_rows == 0 and linkage_gap_rows == 0:
        print("all receipts carry every tracked provenance and linkage field")
    else:
        print(f"core_gap_rows:    {core_gap_rows}/{len(receipts)}")
        print(f"linkage_gap_rows: {linkage_gap_rows}/{len(receipts)}")
        print("status:")
        print(f"  core_provenance: {'complete' if core_gap_rows == 0 else 'needs_repair'}")
        print(f"  linkage:         {'complete' if linkage_gap_rows == 0 else 'optional_gaps_remaining'}")

    return 1 if errors else 0


def collect_artifact_rows(receipts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    artifact_rows: dict[str, dict[str, Any]] = {}
    for i, item in enumerate(receipts, start=1):
        artifact = str(item.get("artifact") or "-")
        row = artifact_rows.setdefault(
            artifact,
            {
                "artifact": artifact,
                "receipt_count": 0,
                "actions": {},
                "latest_timestamp": None,
                "latest_action": None,
                "latest_receipt_id": None,
                "core_gap_rows": 0,
                "linkage_gap_rows": 0,
                "linked_rows": 0,
                "unlinked_provenance_rich_rows": 0,
                "latest_missing_core": [],
                "latest_missing_linkage": [],
                "current_core_status": "unknown",
                "current_linkage_status": "unknown",
                "current_parent_receipt": None,
                "suggested_parent_receipt": None,
                "rows": [],
            },
        )
        row["receipt_count"] += 1
        action = str(item.get("action") or "-")
        row["actions"][action] = row["actions"].get(action, 0) + 1
        row["latest_timestamp"] = item.get("timestamp")
        row["latest_action"] = item.get("action")
        row["latest_receipt_id"] = item.get("receipt_id")

        missing_core = [field for field in CORE_PROVENANCE_FIELDS if not item.get(field)]
        missing_linkage = [field for field in LINKAGE_FIELDS if not item.get(field)]
        if missing_core:
            row["core_gap_rows"] += 1
        elif missing_linkage:
            row["linkage_gap_rows"] += 1

        parent_receipt = item.get("parent_receipt")
        if parent_receipt:
            row["linked_rows"] += 1

        row["latest_missing_core"] = missing_core
        row["latest_missing_linkage"] = missing_linkage
        row["current_core_status"] = "needs_repair" if missing_core else "complete"
        row["current_linkage_status"] = "optional_gaps_remaining" if (not missing_core and missing_linkage) else "complete"
        row["current_parent_receipt"] = parent_receipt

        suggested_parent = None
        if not missing_core and not parent_receipt:
            for earlier in reversed(row["rows"]):
                earlier_receipt_id = earlier.get("receipt_id")
                if earlier_receipt_id:
                    suggested_parent = earlier_receipt_id
                    break
        row["suggested_parent_receipt"] = suggested_parent

        row["rows"].append(
            {
                "index": i,
                "timestamp": item.get("timestamp"),
                "action": item.get("action"),
                "receipt_id": item.get("receipt_id"),
                "summary": item.get("summary"),
                "source": item.get("source"),
                "session": item.get("session"),
                "host": item.get("host"),
                "parent_receipt": parent_receipt,
                "missing_core": missing_core,
                "missing_linkage": missing_linkage,
                "suggested_parent_receipt": suggested_parent,
            }
        )

    for row in artifact_rows.values():
        referenced_receipts = {entry["parent_receipt"] for entry in row["rows"] if entry.get("parent_receipt")}
        unresolved = 0
        for entry in row["rows"]:
            if entry["missing_core"]:
                continue
            if entry.get("parent_receipt"):
                continue
            receipt_id = entry.get("receipt_id")
            if receipt_id and receipt_id in referenced_receipts:
                continue
            unresolved += 1
        row["unlinked_provenance_rich_rows"] = unresolved

    return sorted(artifact_rows.values(), key=lambda row: (-row["receipt_count"], row["artifact"]))


def report_artifacts(log_path: Path, json_output: bool = False) -> int:
    if not log_path.exists():
        print(f"no receipts yet at {log_path}")
        return 0

    receipts, errors = parse_receipts(log_path)
    for err in errors:
        print(err, file=sys.stderr)

    artifacts = collect_artifact_rows(receipts)
    payload = {
        "log_path": str(log_path),
        "total_receipts": len(receipts),
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
    }

    if json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1 if errors else 0

    print(f"log_path: {log_path}")
    print(f"total_receipts: {len(receipts)}")
    print(f"artifact_count: {len(artifacts)}")
    for row in artifacts:
        actions_text = ", ".join(f"{k}={row['actions'][k]}" for k in sorted(row["actions"]))
        print(f"- {row['artifact']}")
        print(f"  receipt_count: {row['receipt_count']}")
        print(f"  actions: {actions_text}")
        print(f"  latest: {row['latest_timestamp']} | {row['latest_action']} | {row['latest_receipt_id'] or '-'}")
        print(f"  historical_core_gap_rows: {row['core_gap_rows']}")
        print(f"  historical_linkage_gap_rows: {row['linkage_gap_rows']}")
        print(f"  current_core_status: {row['current_core_status']}")
        if row['latest_missing_core']:
            print(f"  current_missing_core: {', '.join(row['latest_missing_core'])}")
        print(f"  current_linkage_status: {row['current_linkage_status']}")
        print(f"  linked_rows: {row['linked_rows']}")
        print(f"  unlinked_provenance_rich_rows: {row['unlinked_provenance_rich_rows']}")
        if row['current_parent_receipt']:
            print(f"  current_parent_receipt: {row['current_parent_receipt']}")
        if row['latest_missing_linkage']:
            print(f"  current_missing_linkage: {', '.join(row['latest_missing_linkage'])}")
        if row['suggested_parent_receipt']:
            print(f"  suggested_parent_receipt: {row['suggested_parent_receipt']}")

    return 1 if errors else 0


def report_fingerprints(log_path: Path, json_output: bool = False, tail: int = 5) -> int:
    if not log_path.exists():
        print(f"no receipts yet at {log_path}")
        return 0

    receipts, errors = parse_receipts(log_path)
    for err in errors:
        print(err, file=sys.stderr)

    rows = []
    for i, item in enumerate(receipts, start=1):
        row_hash = receipt_fingerprint(item)
        rows.append(
            {
                "index": i,
                "receipt_id": item.get("receipt_id"),
                "timestamp": item.get("timestamp"),
                "action": item.get("action"),
                "artifact": item.get("artifact"),
                "sha256": row_hash,
            }
        )

    fingerprint = log_fingerprint([row["sha256"] for row in rows])
    payload = {
        "log_path": str(log_path),
        "total_receipts": len(receipts),
        "log_fingerprint_sha256": fingerprint,
        "latest_receipt_sha256": rows[-1]["sha256"] if rows else None,
        "rows": rows,
    }

    if json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1 if errors else 0

    print(f"log_path: {log_path}")
    print(f"total_receipts: {len(receipts)}")
    print(f"log_fingerprint_sha256: {fingerprint}")
    if not rows:
        return 1 if errors else 0

    print(f"latest_receipt_sha256: {rows[-1]['sha256']}")
    shown_rows = rows[-tail:] if tail else []
    print(f"last_{len(shown_rows)}_rows:")
    for row in shown_rows:
        receipt_id = row.get("receipt_id") or "-"
        print(f"  [{row['index']}] {row['sha256']} | {receipt_id} | {row.get('action')} | {row.get('artifact')}")

    return 1 if errors else 0


def inspect_artifact(log_path: Path, artifact: str, json_output: bool = False) -> int:
    if not log_path.exists():
        print(f"no receipts yet at {log_path}")
        return 0

    receipts, errors = parse_receipts(log_path)
    for err in errors:
        print(err, file=sys.stderr)

    artifacts = collect_artifact_rows(receipts)
    match = next((row for row in artifacts if row["artifact"] == artifact), None)
    if match is None:
        print(f"artifact not found: {artifact}", file=sys.stderr)
        return 1

    payload = {
        "log_path": str(log_path),
        "artifact": match,
    }

    if json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1 if errors else 0

    actions_text = ", ".join(f"{k}={match['actions'][k]}" for k in sorted(match["actions"]))
    print(f"log_path: {log_path}")
    print(f"artifact: {match['artifact']}")
    print(f"receipt_count: {match['receipt_count']}")
    print(f"actions: {actions_text}")
    print(f"latest: {match['latest_timestamp']} | {match['latest_action']} | {match['latest_receipt_id'] or '-'}")
    print(f"historical_core_gap_rows: {match['core_gap_rows']}")
    print(f"historical_linkage_gap_rows: {match['linkage_gap_rows']}")
    print(f"current_core_status: {match['current_core_status']}")
    if match['latest_missing_core']:
        print(f"current_missing_core: {', '.join(match['latest_missing_core'])}")
    print(f"current_linkage_status: {match['current_linkage_status']}")
    print(f"linked_rows: {match['linked_rows']}")
    print(f"unlinked_provenance_rich_rows: {match['unlinked_provenance_rich_rows']}")
    if match['current_parent_receipt']:
        print(f"current_parent_receipt: {match['current_parent_receipt']}")
    if match['latest_missing_linkage']:
        print(f"current_missing_linkage: {', '.join(match['latest_missing_linkage'])}")
    if match['suggested_parent_receipt']:
        print(f"suggested_parent_receipt: {match['suggested_parent_receipt']}")
    print("rows:")
    for row in match["rows"]:
        print(f"  [{row['index']}] {row['timestamp']} | {row['action']} | {row['receipt_id'] or '-'}")
        print(f"      summary: {row['summary']}")
        if row['source']:
            print(f"      source: {row['source']}")
        if row['session']:
            print(f"      session: {row['session']}")
        if row['host']:
            print(f"      host: {row['host']}")
        if row['parent_receipt']:
            print(f"      parent_receipt: {row['parent_receipt']}")
        if row['missing_core']:
            print(f"      missing_core: {', '.join(row['missing_core'])}")
        if row['missing_linkage']:
            print(f"      missing_linkage: {', '.join(row['missing_linkage'])}")
        if row['suggested_parent_receipt']:
            print(f"      suggested_parent_receipt: {row['suggested_parent_receipt']}")

    return 1 if errors else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Append-only collaboration receipt log")
    parser.add_argument("--log-path", default=str(DEFAULT_LOG_PATH), help="Path to JSONL receipt log")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="Append a receipt")
    add_parser.add_argument("--agent", required=True)
    add_parser.add_argument("--action", required=True)
    add_parser.add_argument("--artifact", required=True)
    add_parser.add_argument("--summary", required=True)
    add_parser.add_argument("--source", help="Provenance for where this receipt came from (for example github_pr or local_run)")
    add_parser.add_argument("--session", help="Session or run identifier tied to this receipt")
    add_parser.add_argument("--host", help="Host or machine name where the action happened")
    add_parser.add_argument("--parent-receipt", help="Receipt ID this action extends or audits")

    subparsers.add_parser("list", help="List receipts")
    subparsers.add_parser("validate", help="Validate receipt log structure and provenance coverage")
    summary_parser = subparsers.add_parser("summary", help="Print compact log stats and latest receipt info")
    summary_parser.add_argument("--json", action="store_true", help="Emit summary as JSON for machine consumption")
    gaps_parser = subparsers.add_parser("gaps", help="List receipts that still lack tracked provenance fields")
    gaps_parser.add_argument("--json", action="store_true", help="Emit gap details as JSON for machine consumption")
    artifacts_parser = subparsers.add_parser("artifacts", help="Group receipts by artifact and show lineage/coverage at that level")
    artifacts_parser.add_argument("--json", action="store_true", help="Emit artifact groups as JSON for machine consumption")
    fingerprint_parser = subparsers.add_parser("fingerprint", help="Compute tamper-evident SHA-256 fingerprints for receipt rows and the full log")
    fingerprint_parser.add_argument("--json", action="store_true", help="Emit fingerprints as JSON for machine consumption")
    fingerprint_parser.add_argument("--tail", type=int, default=5, help="Number of recent row hashes to show in text output")
    inspect_parser = subparsers.add_parser("inspect", help="Show the full receipt lineage for one artifact")
    inspect_parser.add_argument("artifact", help="Exact artifact path/name to inspect")
    inspect_parser.add_argument("--json", action="store_true", help="Emit artifact lineage as JSON for machine consumption")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    log_path = Path(args.log_path)

    if args.command == "add":
        append_receipt(
            log_path,
            args.agent,
            args.action,
            args.artifact,
            args.summary,
            args.source,
            args.session,
            args.host,
            args.parent_receipt,
        )
        return 0
    if args.command == "list":
        return list_receipts(log_path)
    if args.command == "validate":
        return validate_receipts(log_path)
    if args.command == "summary":
        return summarize_receipts(log_path, json_output=args.json)
    if args.command == "gaps":
        return report_gaps(log_path, json_output=args.json)
    if args.command == "artifacts":
        return report_artifacts(log_path, json_output=args.json)
    if args.command == "fingerprint":
        return report_fingerprints(log_path, json_output=args.json, tail=max(args.tail, 0))
    if args.command == "inspect":
        return inspect_artifact(log_path, args.artifact, json_output=args.json)

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
