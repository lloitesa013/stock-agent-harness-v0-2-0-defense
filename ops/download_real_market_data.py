#!/usr/bin/env python3
"""Download optional candidate ETF CSV data for v0.3 real-market evidence."""

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
    REAL_MARKET_END,
    REAL_MARKET_SEALED_CSV_DIR,
    REAL_MARKET_START,
    download_real_market_csvs,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=["stooq", "yahoo_chart", "yfinance"], default="yahoo_chart")
    parser.add_argument("--output-dir", type=Path, default=REAL_MARKET_SEALED_CSV_DIR)
    parser.add_argument("--start", default=REAL_MARKET_START)
    parser.add_argument("--end", default=REAL_MARKET_END)
    parser.add_argument("--pretty", action="store_true")
    return parser


def main(argv: Optional[Any] = None) -> int:
    args = build_parser().parse_args(argv)
    manifest = download_real_market_csvs(
        args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir,
        provider=args.provider,
        start=args.start,
        end=args.end,
    )
    print(json.dumps(manifest, indent=2 if args.pretty else None, sort_keys=args.pretty))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
