import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import csv
import json
from pathlib import Path

from angelos_os.real_market_harness import (
    REAL_MARKET_END,
    REAL_MARKET_START,
    REAL_MARKET_TICKERS,
    build_real_market_data_manifest,
    download_real_market_csvs,
    load_sealed_real_market_universe,
    real_market_strategy_registry,
)


ROOT = Path(__file__).resolve().parents[1]
REAL_MARKET_DIR = ROOT / "benchmarks" / "real_market_data_v1"
SEALED_CSV_DIR = REAL_MARKET_DIR / "sealed_csv"
SAMPLE_CSV = REAL_MARKET_DIR / "sample_csv" / "SAMPLE_ETF.csv"


def sealed_csv_available():
    return all((SEALED_CSV_DIR / f"{ticker}.csv").exists() for ticker in REAL_MARKET_TICKERS)


class RealMarketHarnessTests(unittest.TestCase):
    def test_sealed_real_market_universe_loads(self):
        if not sealed_csv_available():
            self.skipTest("full sealed ETF CSV artifacts are local/private and not redistributed")
        universe, manifest = load_sealed_real_market_universe()
        self.assertEqual(manifest["schema"], "real_market_data_manifest_v0_3")
        self.assertEqual(manifest["tickers"], REAL_MARKET_TICKERS)
        self.assertGreaterEqual(manifest["common_date_count"], 2000)
        self.assertEqual(sorted(universe), ["DEFENSIVE_SYN", "QUALITY_SYN", "SPY_SYN", "TREND_SYN", "WHIPSAW_SYN"])
        self.assertEqual(universe["SPY_SYN"][0].date, manifest["common_first_date"])
        self.assertEqual(universe["SPY_SYN"][-1].date, manifest["common_last_date"])

    def test_manifest_hashes_rebuild_from_sealed_csv(self):
        if not sealed_csv_available():
            self.skipTest("full sealed ETF CSV artifacts are local/private and not redistributed")
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            data_dir = tmp / "sealed_csv"
            data_dir.mkdir()
            source_dir = ROOT / "benchmarks" / "real_market_data_v1" / "sealed_csv"
            for ticker in REAL_MARKET_TICKERS:
                shutil.copyfile(str(source_dir / f"{ticker}.csv"), str(data_dir / f"{ticker}.csv"))
            manifest = build_real_market_data_manifest(
                data_dir,
                tmp / "REAL_MARKET_DATA_MANIFEST.json",
                provider="test_fixture",
                start=REAL_MARKET_START,
                end=REAL_MARKET_END,
            )
        self.assertEqual(manifest["common_date_count"], 2514)
        self.assertEqual(manifest["common_first_date"], "2016-01-04")
        self.assertEqual(manifest["common_last_date"], "2025-12-31")

    def test_public_manifest_declares_lineage_without_requiring_csv_redistribution(self):
        manifest_path = REAL_MARKET_DIR / "REAL_MARKET_DATA_MANIFEST.json"
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema"], "real_market_data_manifest_v0_3")
        self.assertEqual(payload["tickers"], REAL_MARKET_TICKERS)
        self.assertEqual(
            payload["distribution_policy"],
            "public_repo_manifest_and_sample_only_full_csv_local_or_private_artifact",
        )

    def test_public_sample_csv_documents_schema(self):
        with SAMPLE_CSV.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            self.assertEqual(reader.fieldnames, ["Date", "Open", "High", "Low", "Close", "Volume"])
            rows = list(reader)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["Date"], "2020-01-02")

    def test_real_market_strategy_registry_has_candidate(self):
        strategies = real_market_strategy_registry()
        candidate = [strategy for strategy in strategies if strategy.strategy_id == "agentic_candidate_v1"][0]
        self.assertTrue(candidate.is_candidate)
        self.assertIn("real ETF", candidate.label)

    def test_invalid_downloader_provider_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(ValueError):
                download_real_market_csvs(Path(tmpdir), provider="not_a_provider")

    def test_ralph_helper_help_does_not_require_dependencies_or_api_key(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed")
        script = ROOT / "tools" / "ralph" / "v0_3_real_market_agent.mjs"
        completed = subprocess.run(
            [node, str(script), "--help"],
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0)
        self.assertIn("advisory only", completed.stdout)

    def test_ralph_helper_missing_api_key_message_is_clean(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed")
        script = ROOT / "tools" / "ralph" / "v0_3_real_market_agent.mjs"
        env = dict(os.environ)
        env.pop("OPENAI_API_KEY", None)
        completed = subprocess.run(
            [node, str(script), "."],
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("Official gates do not require Ralph", completed.stderr)


if __name__ == "__main__":
    unittest.main()
