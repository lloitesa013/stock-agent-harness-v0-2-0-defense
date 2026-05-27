#!/usr/bin/env python3
"""Build the v0.2 defense packet for downside_performance_v1."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from angelos_os.performance_defense import (  # noqa: E402
    build_performance_defense_packet,
    write_defense_packet,
)


DEFAULT_CLAIM_GATE_JSON = Path("reports/downside_performance_claim_gate_latest.json")
DEFAULT_OUTPUT_DIR = Path("dist/downside_performance_v1_defense_packet")


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("expected JSON object: " + str(path))
    return payload


def build_defense_packet_from_claim_gate(
    claim_gate_json: Path = DEFAULT_CLAIM_GATE_JSON,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    clean: bool = False,
    bootstrap_samples: int = 250,
    bootstrap_block_size: int = 21,
    forward_start_date: Optional[str] = None,
) -> Dict[str, Any]:
    claim_gate_path = claim_gate_json if claim_gate_json.is_absolute() else ROOT / claim_gate_json
    output_root = output_dir if output_dir.is_absolute() else ROOT / output_dir
    claim_gate = _load_json(claim_gate_path)
    if claim_gate.get("status") != "passed" or claim_gate.get("performance_claim_publishable") is not True:
        raise ValueError("performance claim gate must be passed and publishable before defense packet build")
    report = claim_gate.get("report", {})
    packet = build_performance_defense_packet(
        report,
        bootstrap_samples=bootstrap_samples,
        bootstrap_block_size=bootstrap_block_size,
        forward_start_date=forward_start_date,
    )
    manifest = write_defense_packet(packet, output_root, clean=clean)
    return {
        "schema": "downside_performance_defense_packet_build_v0_2",
        "status": manifest.get("status", "failed"),
        "defense_claim_defensible": packet["defense_gate"]["defense_claim_defensible"],
        "claim_gate_json": str(claim_gate_path),
        "output_dir": str(output_root),
        "manifest": manifest,
        "defense_gate": packet["defense_gate"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claim-gate-json", type=Path, default=DEFAULT_CLAIM_GATE_JSON)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--bootstrap-samples", type=int, default=250)
    parser.add_argument("--bootstrap-block-size", type=int, default=21)
    parser.add_argument("--forward-start-date", default=None)
    parser.add_argument("--pretty", action="store_true")
    return parser


def main(argv: Optional[Any] = None) -> int:
    args = build_parser().parse_args(argv)
    payload = build_defense_packet_from_claim_gate(
        args.claim_gate_json,
        args.output_dir,
        clean=args.clean,
        bootstrap_samples=args.bootstrap_samples,
        bootstrap_block_size=args.bootstrap_block_size,
        forward_start_date=args.forward_start_date,
    )
    print(json.dumps(payload, indent=2 if args.pretty else None, sort_keys=args.pretty))
    return 0 if payload.get("status") == "passed" and payload.get("defense_claim_defensible") else 1


if __name__ == "__main__":
    raise SystemExit(main())
