import tempfile
import unittest
from pathlib import Path

from dashboard.app import (
    artifact_rows,
    collect_evidence,
    evidence_packet_map,
    metric_rows,
    presentation_summary,
    reproduction_command_rows,
    safe_claim_boundary_text,
    reviewer_checklist,
)


class DashboardEvidenceTests(unittest.TestCase):
    def test_collects_existing_release_evidence(self):
        evidence = collect_evidence()
        self.assertEqual(evidence["status"]["claim_status"], "PASS")
        self.assertEqual(evidence["status"]["strategy_freeze"], "PASS")
        self.assertIn("agentic_candidate_v1", evidence["metrics"])
        self.assertGreater(evidence["candidate_metrics"]["return_multiple"], 1.0)
        self.assertIn(evidence["status"]["real_market_evidence"], {"PASS", "PENDING"})
        self.assertIn("real_market", evidence)
        summary = presentation_summary(evidence)
        self.assertEqual(summary["presentation_release"], "v0.3.1-presentation-ui")
        self.assertIn("SPY", summary["ticker_coverage"])
        self.assertEqual(summary["official_mode"], "Sealed CSV")
        self.assertIn("No live trading readiness", summary["non_claims"])
        self.assertNotIn("SOTA", safe_claim_boundary_text(evidence))
        checklist = reviewer_checklist(evidence)
        self.assertTrue(any(row["check"] == "Read-only viewer" for row in checklist))
        self.assertTrue(any(row["check"] == "Financial boundary" for row in checklist))
        packet_map = evidence_packet_map(evidence)
        self.assertTrue(any(row["group"] == "Release gate" for row in packet_map))
        self.assertTrue(any(row["group"] == "Official packet" for row in packet_map))
        self.assertTrue(all("reviewer_question" in row for row in packet_map))
        commands = reproduction_command_rows()
        self.assertTrue(any(row["purpose"] == "Open viewer" for row in commands))
        self.assertTrue(all("place orders" not in row["boundary"].lower() for row in commands[:-1]))

    def test_missing_evidence_is_pending_not_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            evidence = collect_evidence(Path(tmpdir))
        self.assertEqual(evidence["status"]["claim_status"], "PENDING")
        self.assertEqual(evidence["status"]["forward_validation"], "Pending")
        self.assertEqual(evidence["status"]["real_market_evidence"], "PENDING")
        self.assertEqual(presentation_summary(evidence)["real_market_status"], "PENDING")
        rows = artifact_rows(evidence["paths"])
        self.assertTrue(rows)
        self.assertTrue(all(row["status"] == "PENDING" for row in rows))
        checklist = reviewer_checklist(evidence)
        self.assertEqual(checklist[0]["status"], "PASS")
        self.assertIn("PENDING", {row["status"] for row in checklist})
        packet_map = evidence_packet_map(evidence)
        self.assertTrue(packet_map)
        self.assertIn("PENDING", {row["status"] for row in packet_map})

    def test_metric_rows_put_candidate_first(self):
        rows = metric_rows(
            {
                "baseline": {"family": "baseline", "total_return": 0.1},
                "candidate": {"family": "candidate", "total_return": 0.2},
            }
        )
        self.assertEqual(rows[0]["family"], "candidate")


if __name__ == "__main__":
    unittest.main()
