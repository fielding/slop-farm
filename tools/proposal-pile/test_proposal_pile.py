#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import proposal_pile


class OpenProposalTests(unittest.TestCase):
    def test_open_proposals_excludes_resolved_parent_rows(self) -> None:
        proposals = [
            {
                "proposal_id": "prp_original",
                "timestamp": "2026-04-11T18:44:00+00:00",
                "agent": "sedge",
                "title": "Build a viewer",
                "summary": "Prototype a receipt viewer.",
                "status": "proposed",
            },
            {
                "proposal_id": "prp_adopted",
                "timestamp": "2026-05-06T12:34:08+00:00",
                "agent": "sedge",
                "title": "Viewer landed",
                "summary": "The viewer proposal landed.",
                "status": "adopted",
                "parent_proposal": "prp_original",
            },
            {
                "proposal_id": "prp_unresolved",
                "timestamp": "2026-05-06T12:35:00+00:00",
                "agent": "sedge",
                "title": "Add another primitive",
                "summary": "Still needs a decision.",
                "status": "proposed",
            },
        ]

        self.assertEqual(
            [item["proposal_id"] for item in proposal_pile.find_open_proposals(proposals)],
            ["prp_unresolved"],
        )


if __name__ == "__main__":
    unittest.main()
