#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

DEFAULT_LOG_PATH = Path("tools/receipt-log/receipts.jsonl")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def append_receipt(log_path: Path, agent: str, action: str, artifact: str, summary: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    receipt = {
        "timestamp": utc_now(),
        "agent": agent,
        "action": action,
        "artifact": artifact,
        "summary": summary,
    }
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(receipt, ensure_ascii=False) + "\n")
    print(f"appended receipt to {log_path}")


def list_receipts(log_path: Path) -> int:
    if not log_path.exists():
        print(f"no receipts yet at {log_path}")
        return 0

    with log_path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"[{i}] invalid json: {e}", file=sys.stderr)
                continue
            print(f"[{i}] {item.get('timestamp')} | {item.get('agent')} | {item.get('action')}")
            print(f"    artifact: {item.get('artifact')}")
            print(f"    summary:  {item.get('summary')}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Append-only collaboration receipt log")
    parser.add_argument("--log-path", default=str(DEFAULT_LOG_PATH), help="Path to JSONL receipt log")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="Append a receipt")
    add_parser.add_argument("--agent", required=True)
    add_parser.add_argument("--action", required=True)
    add_parser.add_argument("--artifact", required=True)
    add_parser.add_argument("--summary", required=True)

    subparsers.add_parser("list", help="List receipts")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    log_path = Path(args.log_path)

    if args.command == "add":
        append_receipt(log_path, args.agent, args.action, args.artifact, args.summary)
        return 0
    if args.command == "list":
        return list_receipts(log_path)

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
