#!/usr/bin/env python3
"""Verify a downside_performance_v1 v0.2 defense packet."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from angelos_os.performance_defense import verify_defense_packet  # noqa: E402


DEFAULT_PACKET_DIR = Path("dist/downside_performance_v1_defense_packet")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet-dir", type=Path, default=DEFAULT_PACKET_DIR)
    parser.add_argument("--pretty", action="store_true")
    return parser


def main(argv: Optional[Any] = None) -> int:
    args = build_parser().parse_args(argv)
    packet_dir = args.packet_dir if args.packet_dir.is_absolute() else ROOT / args.packet_dir
    payload = verify_defense_packet(packet_dir)
    print(json.dumps(payload, indent=2 if args.pretty else None, sort_keys=args.pretty))
    return 0 if payload.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
