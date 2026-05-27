from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

from angelos_os.performance_harness import (
    PERFORMANCE_NON_CLAIMS,
    default_strategy_registry,
    run_downside_performance_benchmark,
    write_performance_evidence_packet,
)
from ops.run_downside_performance_claim_gate import run_downside_performance_claim_gate


ROOT = Path(__file__).resolve().parents[1]


class DownsidePerformanceHarnessTests(unittest.TestCase):
    def test_strategy_registry_contains_required_baselines_and_candidate(self):
        strategy_ids = [strategy.strategy_id for strategy in default_strategy_registry()]
        self.assertEqual(
            strategy_ids,
            [
                "cash",
                "buy_and_hold_spy",
                "equal_weight",
                "sma_crossover",
                "simple_momentum",
                "mean_reversion",
                "volatility_targeting",
                "stock_harness_ma_cash",
                "agentic_candidate_v1",
            ],
        )

    def test_candidate_is_top_return_and_calmar_under_included_benchmark(self):
        report = run_downside_performance_benchmark().to_dict()
        self.assertTrue(report["performance_gate"]["performance_claim_publishable"])
        self.assertEqual(report["rankings"]["total_return"][0]["strategy_id"], "agentic_candidate_v1")
        self.assertEqual(report["rankings"]["cagr"][0]["strategy_id"], "agentic_candidate_v1")
        self.assertEqual(report["rankings"]["calmar_ratio"][0]["strategy_id"], "agentic_candidate_v1")
        candidate = report["metrics_by_strategy"]["agentic_candidate_v1"]
        buy_hold = report["metrics_by_strategy"]["buy_and_hold_spy"]
        self.assertGreater(candidate["return_multiple"], 1.8)
        self.assertLess(candidate["max_drawdown"], buy_hold["max_drawdown"])

    def test_performance_fingerprint_is_deterministic(self):
        first = run_downside_performance_benchmark().to_dict()
        second = run_downside_performance_benchmark().to_dict()
        self.assertEqual(first["manifest"]["fingerprint"], second["manifest"]["fingerprint"])

    def test_negative_controls_are_detected(self):
        report = run_downside_performance_benchmark().to_dict()
        controls = report["negative_controls"]
        self.assertTrue(controls["lookahead_leak_detected"])
        self.assertTrue(controls["overfit_trap_rejected"])
        self.assertTrue(report["robustness"]["lookahead_audit"]["passed"])

    def test_non_claims_preserved(self):
        report = run_downside_performance_benchmark().to_dict()
        contract = json.loads(
            (ROOT / "benchmarks" / "downside_performance_v1" / "claim_contract.json").read_text(
                encoding="utf-8"
            )
        )
        for non_claim in PERFORMANCE_NON_CLAIMS:
            self.assertIn(non_claim, report["claim"]["non_claims"])
            self.assertIn(non_claim, contract["non_claims"])

    def test_evidence_packet_writes_required_files_and_hash_manifest(self):
        report = run_downside_performance_benchmark()
        output_dir = ROOT / "dist" / "test_downside_performance_evidence"
        if output_dir.exists():
            shutil.rmtree(str(output_dir))
        manifest = write_performance_evidence_packet(report, output_dir, clean=False)
        self.assertEqual(manifest["status"], "passed")
        required = {
            "metrics.json",
            "baseline_comparison.json",
            "robustness_report.json",
            "performance_gate.json",
            "claim_contract.json",
            "equity_curves.csv",
            "trades.csv",
            "PERFORMANCE_MANIFEST.json",
        }
        self.assertTrue(required.issubset({entry["path"] for entry in manifest["files"]}))
        with (output_dir / "equity_curves.csv").open("r", newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertGreater(len(rows), 100)

    def test_performance_claim_gate_passes(self):
        gate = run_downside_performance_claim_gate(
            evidence_dir=ROOT / "dist" / "test_downside_performance_gate_evidence"
        )
        self.assertEqual(gate["schema"], "downside_performance_claim_gate_v1")
        self.assertEqual(gate["status"], "passed")
        self.assertTrue(gate["performance_claim_publishable"])

    def test_cli_emits_parseable_json(self):
        completed = subprocess.run(
            [
                sys.executable,
                "ops/run_downside_performance_benchmark.py",
                "--pretty",
            ],
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["schema"], "stock_harness_downside_performance_report_v1")
        self.assertTrue(payload["performance_gate"]["performance_claim_publishable"])


if __name__ == "__main__":
    unittest.main()
