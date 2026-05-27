from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from angelos_os.agent_harness import (
    AGENTIC_NON_CLAIMS,
    AGENT_ROLES,
    AgentHarnessConfig,
    LLMAgentProvider,
    default_agent_harness_bars,
    run_stock_agent_harness,
)
from angelos_os.stock_harness import Bar
from ops.run_stock_agent_harness_claim_gate import run_agentic_claim_gate


ROOT = Path(__file__).resolve().parents[1]


class StockAgentHarnessTests(unittest.TestCase):
    def test_runs_all_roles_and_keeps_default_crash_case(self):
        report = run_stock_agent_harness().to_dict()
        self.assertEqual(report["schema"], "stock_agent_harness_report_v1")
        self.assertEqual([decision["role"] for decision in report["transcript"]], AGENT_ROLES)
        self.assertEqual(report["final_verdict"]["verdict"], "KEEP")
        self.assertEqual(report["config"]["provider"], "deterministic")

    def test_deterministic_provider_produces_stable_fingerprint(self):
        first = run_stock_agent_harness().to_dict()
        second = run_stock_agent_harness().to_dict()
        self.assertEqual(first["manifest"]["fingerprint"], second["manifest"]["fingerprint"])

    def test_data_quality_failure_hard_rejects(self):
        bars = [
            Bar(date="2020-01-01", open=100.0, high=90.0, low=110.0, close=100.0, volume=1000.0),
            Bar(date="2020-01-02", open=100.0, high=101.0, low=99.0, close=100.0, volume=1000.0),
            Bar(date="2020-01-03", open=100.0, high=101.0, low=99.0, close=100.0, volume=1000.0),
        ]
        report = run_stock_agent_harness(bars=bars).to_dict()
        self.assertEqual(report["final_verdict"]["verdict"], "REJECT")
        self.assertIn("data_quality_failure", report["final_verdict"]["risk_flags"])
        self.assertEqual(report["agent_decisions"]["DataSentinel"]["verdict"], "REJECT")

    def test_non_claims_are_preserved_in_report_and_contract(self):
        report = run_stock_agent_harness().to_dict()
        contract = json.loads(
            (ROOT / "benchmarks" / "agentic_verification_v1" / "claim_contract.json").read_text(
                encoding="utf-8"
            )
        )
        for non_claim in AGENTIC_NON_CLAIMS:
            self.assertIn(non_claim, report["claim"]["non_claims"])
            self.assertIn(non_claim, contract["non_claims"])

    def test_optional_llm_provider_is_excluded_from_official_gate(self):
        gate = run_agentic_claim_gate()
        by_id = {assertion["id"]: assertion for assertion in gate["assertions"]}
        self.assertTrue(by_id["llm_provider_excluded_from_official_gate"]["passed"])
        with self.assertRaises(RuntimeError):
            run_stock_agent_harness(
                config=AgentHarnessConfig(provider="llm"),
                provider=LLMAgentProvider(api_key_env="STOCK_AGENT_HARNESS_MISSING_KEY"),
            )

    def test_agentic_claim_gate_passes(self):
        gate = run_agentic_claim_gate()
        self.assertEqual(gate["schema"], "stock_agent_harness_claim_gate_v1")
        self.assertEqual(gate["status"], "passed")
        self.assertTrue(gate["agentic_claim_ready"])

    def test_cli_emits_parseable_json(self):
        completed = subprocess.run(
            [
                sys.executable,
                "ops/run_stock_agent_harness.py",
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
        self.assertEqual(payload["schema"], "stock_agent_harness_report_v1")
        self.assertEqual(payload["final_verdict"]["verdict"], "KEEP")

    def test_default_bars_are_reusable(self):
        bars = default_agent_harness_bars()
        self.assertGreaterEqual(len(bars), 8)
        self.assertEqual(bars[0].date, "2020-01-01")


if __name__ == "__main__":
    unittest.main()
