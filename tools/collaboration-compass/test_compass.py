import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOL = Path(__file__).with_name("compass.py")


class CollaborationCompassTests(unittest.TestCase):
    def run_tool(self, idea):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "idea.json"
            path.write_text(json.dumps(idea), encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(TOOL), str(path)],
                text=True,
                capture_output=True,
                check=True,
            ).stdout

    def test_complete_idea_scores_full_marks(self):
        output = self.run_tool(
            {
                "title": "Receipt review queue",
                "problem": "Humans need a fast way to review agent residue.",
                "users": ["human maintainer", "agent contributor"],
                "artifact": "Markdown review queue generated from receipts.",
                "human_benefit": "Maintainers see risk notes before opening files.",
                "agent_benefit": "Agents can target follow-up work at reviewed gaps.",
                "review_plan": "Compare output against fixture receipt logs.",
                "risks": ["Could hide context if summaries are too terse"],
                "rollback": "Delete the generated report; source receipts are unchanged.",
            }
        )
        self.assertIn("**Score:** 7/7", output)
        self.assertIn("Buildable enough", output)
        self.assertIn("✅ **At least two stakeholders are named:** human maintainer, agent contributor", output)

    def test_sparse_idea_names_missing_fields(self):
        output = self.run_tool(
            {
                "title": "Vibes board",
                "problem": "Ideas get vague.",
                "artifact": "A board.",
                "users": ["agent"],
            }
        )
        self.assertIn("**Score:** 1/7", output)
        self.assertIn("Still mostly vibes", output)
        self.assertIn("human_benefit", output)
        self.assertIn("rollback", output)
        self.assertIn("⚠️ **At least two stakeholders are named:** agent", output)


if __name__ == "__main__":
    unittest.main()
