#!/usr/bin/env python3
import hashlib
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import receipt_log


class ReceiptValidationTests(unittest.TestCase):
    def test_validate_rejects_unknown_parent_receipt(self) -> None:
        log_path = Path(self._testMethodName + ".jsonl")
        try:
            log_path.write_text(
                json.dumps(
                    {
                        "receipt_id": "rct_child",
                        "timestamp": "2026-05-13T00:00:00+00:00",
                        "agent": "sedge",
                        "action": "reviewed",
                        "artifact": "tools/receipt-log",
                        "summary": "Claims a lineage link that does not exist",
                        "parent_receipt": "rct_missing",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            self.assertEqual(receipt_log.validate_receipts(log_path), 1)
        finally:
            log_path.unlink(missing_ok=True)


class ReceiptFingerprintTests(unittest.TestCase):
    def test_receipt_fingerprint_uses_stable_canonical_json(self) -> None:
        first = {"agent": "sedge", "artifact": "tools/receipt-log", "action": "audited_log"}
        same_data_different_order = {"action": "audited_log", "artifact": "tools/receipt-log", "agent": "sedge"}

        self.assertEqual(
            receipt_log.receipt_fingerprint(first),
            receipt_log.receipt_fingerprint(same_data_different_order),
        )

        expected_payload = json.dumps(first, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        self.assertEqual(
            receipt_log.receipt_fingerprint(first),
            hashlib.sha256(expected_payload.encode("utf-8")).hexdigest(),
        )

    def test_log_fingerprint_changes_when_row_order_changes(self) -> None:
        original = ["a" * 64, "b" * 64]
        reversed_rows = list(reversed(original))

        self.assertNotEqual(
            receipt_log.log_fingerprint(original),
            receipt_log.log_fingerprint(reversed_rows),
        )


if __name__ == "__main__":
    unittest.main()
