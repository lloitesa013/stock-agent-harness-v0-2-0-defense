#!/usr/bin/env python3
"""Run the deterministic-first Stock Agent Harness."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from angelos_os.agent_harness import (  # noqa: E402
    AgentHarnessConfig,
    LLMAgentProvider,
    DeterministicAgentProvider,
    load_agent_harness_bars_csv,
    render_agent_harness_markdown,
    run_stock_agent_harness,
)


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=None, help="Optional OHLCV CSV input.")
    parser.add_argument(
        "--provider",
        choices=["deterministic", "llm"],
        default="deterministic",
        help="Agent provider. Official gates use deterministic only.",
    )
    parser.add_argument("--max-rounds", type=int, default=2)
    parser.add_argument("--consensus-threshold", type=float, default=0.70)
    parser.add_argument("--max-allowed-drawdown", type=float, default=0.20)
    parser.add_argument("--include-global-comparison", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON output path.")
    parser.add_argument("--markdown-output", type=Path, default=None, help="Optional Markdown output path.")
    return parser


def main(argv: Optional[Any] = None) -> int:
    args = build_parser().parse_args(argv)
    bars = load_agent_harness_bars_csv(args.csv) if args.csv else None
    config = AgentHarnessConfig(
        provider=args.provider,
        max_rounds=args.max_rounds,
        consensus_threshold=args.consensus_threshold,
        max_allowed_drawdown=args.max_allowed_drawdown,
        include_global_comparison=args.include_global_comparison,
    )
    provider = DeterministicAgentProvider() if args.provider == "deterministic" else LLMAgentProvider()
    try:
        report = run_stock_agent_harness(bars=bars, config=config, provider=provider)
    except Exception as exc:
        payload = {
            "schema": "stock_agent_harness_cli_error_v1",
            "status": "failed",
            "error": str(exc),
        }
        print(json.dumps(payload, indent=2 if args.pretty else None, sort_keys=args.pretty))
        return 1

    payload = report.to_dict()
    if args.output:
        _write_json(args.output, payload)
    if args.markdown_output:
        _write_text(args.markdown_output, render_agent_harness_markdown(report))
    print(json.dumps(payload, indent=2 if args.pretty else None, sort_keys=args.pretty))
    return 0 if payload.get("final_verdict", {}).get("verdict") in {"KEEP", "ITERATE", "REJECT"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
