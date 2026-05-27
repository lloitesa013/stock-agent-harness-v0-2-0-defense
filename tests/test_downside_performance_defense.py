import json
import unittest
from pathlib import Path

from angelos_os.performance_defense import (
    build_performance_defense_packet,
    verify_defense_packet,
    write_defense_packet,
)
from angelos_os.performance_harness import run_downside_performance_benchmark


class DownsidePerformanceDefenseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = run_downside_performance_benchmark().to_dict()
        cls.packet = build_performance_defense_packet(
            cls.report,
            bootstrap_samples=120,
            forward_start_date="2026-05-27",
        )

    def test_defense_gate_passes(self):
        gate = self.packet["defense_gate"]
        self.assertEqual("passed", gate["status"])
        self.assertTrue(gate["defense_claim_defensible"])
        self.assertTrue(gate["checks"]["strategy_freeze_verified"])
        self.assertTrue(gate["checks"]["data_bias_defense_passed"])
        self.assertTrue(gate["checks"]["baseline_fairness_verified"])
        self.assertTrue(gate["checks"]["paper_trading_protocol_initialized"])

    def test_strategy_freeze_fingerprint_is_stable(self):
        second = build_performance_defense_packet(
            self.report,
            bootstrap_samples=120,
            forward_start_date="2026-05-27",
        )
        self.assertEqual(
            self.packet["strategy_freeze_report"]["candidate_config_fingerprint"],
            second["strategy_freeze_report"]["candidate_config_fingerprint"],
        )
        self.assertEqual(
            self.packet["strategy_freeze_report"]["strategy_registry_fingerprint"],
            second["strategy_freeze_report"]["strategy_registry_fingerprint"],
        )

    def test_bootstrap_confidence_report_is_deterministic(self):
        second = build_performance_defense_packet(
            self.report,
            bootstrap_samples=120,
            forward_start_date="2026-05-27",
        )
        self.assertEqual(
            self.packet["statistical_confidence_report"]["bootstrap"]["metrics"],
            second["statistical_confidence_report"]["bootstrap"]["metrics"],
        )
        self.assertIn("cagr", self.packet["statistical_confidence_report"]["bootstrap"]["metrics"])
        self.assertIn("max_drawdown", self.packet["statistical_confidence_report"]["bootstrap"]["metrics"])

    def test_data_and_baseline_reports_pass(self):
        self.assertEqual("passed", self.packet["data_lineage_bias_report"]["status"])
        self.assertEqual("passed", self.packet["baseline_fairness_report"]["status"])
        self.assertTrue(self.packet["data_lineage_bias_report"]["checks"]["data_type_disclosed"])
        self.assertTrue(self.packet["baseline_fairness_report"]["checks"]["same_evaluation_window"])

    def test_write_and_verify_packet(self):
        output_dir = Path("dist/test_downside_performance_defense")
        manifest = write_defense_packet(self.packet, output_dir, clean=True)
        self.assertEqual("passed", manifest["status"])
        verification = verify_defense_packet(output_dir)
        self.assertEqual("passed", verification["status"])


if __name__ == "__main__":
    unittest.main()
