#!/usr/bin/env python3
"""Run the deterministic downside_performance_v1 benchmark."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from angelos_os.performance_harness import (  # noqa: E402
    PerformanceRunConfig,
    run_downside_performance_benchmark,
    write_performance_evidence_packet,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON report output.")
    parser.add_argument(
        "--evidence-dir",
        type=Path,
        default=None,
        help="Optional directory for metrics, curves, trades, gate, and manifest artifacts.",
    )
    parser.add_argument("--clean-evidence", action="store_true")
    parser.add_argument("--cost-bps", type=float, default=10.0)
    parser.add_argument("--slippage-bps", type=float, default=5.0)
    return parser


def main(argv: Optional[Any] = None) -> int:
    args = build_parser().parse_args(argv)
    config = PerformanceRunConfig(cost_bps=args.cost_bps, slippage_bps=args.slippage_bps)
    report = run_downside_performance_benchmark(config=config)
    payload = report.to_dict()

    if args.evidence_dir:
        evidence_dir = args.evidence_dir if args.evidence_dir.is_absolute() else ROOT / args.evidence_dir
        payload["evidence_packet"] = write_performance_evidence_packet(
            report,
            evidence_dir,
            clean=args.clean_evidence,
        )

    if args.output:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    print(json.dumps(payload, indent=2 if args.pretty else None, sort_keys=args.pretty))
    return 0 if payload["performance_gate"]["performance_claim_publishable"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
