#!/usr/bin/env python3
"""Run the v0.3 sealed real-market data defense gate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from angelos_os.real_market_harness import (  # noqa: E402
    RealMarketRunConfig,
    run_real_market_data_defense,
    write_real_market_evidence_packet,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--evidence-dir", type=Path, default=ROOT / "dist" / "real_market_data_v1_evidence")
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--clean", action="store_true")
    return parser


def main(argv: Optional[Any] = None) -> int:
    args = build_parser().parse_args(argv)
    cfg_kwargs = {"evidence_dir": args.evidence_dir}
    if args.data_dir is not None:
        cfg_kwargs["data_dir"] = args.data_dir
    if args.manifest is not None:
        cfg_kwargs["manifest_path"] = args.manifest
    config = RealMarketRunConfig(**cfg_kwargs)
    report = run_real_market_data_defense(config)
    evidence_dir = config.evidence_dir if config.evidence_dir.is_absolute() else ROOT / config.evidence_dir
    manifest = write_real_market_evidence_packet(report, evidence_dir, clean=args.clean)
    payload = {
        "schema": "real_market_data_defense_claim_gate_v0_3",
        "status": "passed" if report["real_market_gate"]["real_market_claim_ready"] else "failed",
        "real_market_claim_ready": report["real_market_gate"]["real_market_claim_ready"],
        "claim_scope": report["claim_scope"],
        "assertions": [
            {"id": key, "passed": bool(value)}
            for key, value in sorted(report["real_market_gate"]["checks"].items())
        ],
        "report": report,
        "evidence_manifest": manifest,
        "root": str(ROOT),
    }
    if args.output:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(payload, indent=2 if args.pretty else None, sort_keys=args.pretty))
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
