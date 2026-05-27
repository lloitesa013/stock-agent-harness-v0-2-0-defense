#!/usr/bin/env python3
"""Seal the v0.2.0-defense release evidence into a frozen backup bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple


ROOT = Path(__file__).resolve().parents[1]
RELEASE_ID = "v0.2.0-defense"
DEFAULT_OUTPUT_DIR = Path("dist/v0.2.0-defense-final")

SOURCE_ITEMS: List[Tuple[str, str, bool]] = [
    ("dist/downside_performance_v1_evidence", "evidence/downside_performance_v1_evidence", False),
    ("dist/downside_performance_v1_defense_packet", "evidence/downside_performance_v1_defense_packet", False),
    ("dist/downside_performance_v1_public_snapshot", "public_snapshot/downside_performance_v1_public_snapshot", False),
    ("dist/stock_harness_official_claim_packet", "official/stock_harness_official_claim_packet", False),
    ("dist/stock_harness_release_candidate", "official/stock_harness_release_candidate", False),
    ("reports/downside_performance_claim_gate_latest.json", "reports/downside_performance_claim_gate_latest.json", False),
    ("reports/stock_harness_official_claim_gate_defense_latest.json", "reports/stock_harness_official_claim_gate_defense_latest.json", False),
    ("reports/stock_harness_official_claim_gate_performance_latest.json", "reports/stock_harness_official_claim_gate_performance_latest.json", True),
    ("reports/stock_harness_release_gate_official.json", "reports/stock_harness_release_gate_official.json", False),
    ("reports/stock_harness_release_candidate_replay_official.json", "reports/stock_harness_release_candidate_replay_official.json", False),
    ("reports/v0_2_0_defense_clean_replay.json", "reports/v0_2_0_defense_clean_replay.json", True),
    ("paper/DOWNSIDE_PERFORMANCE_CLAIM_PAPER.md", "paper/DOWNSIDE_PERFORMANCE_CLAIM_PAPER.md", False),
    ("paper/DOWNSIDE_PERFORMANCE_CLAIM_PAPER.pdf", "paper/DOWNSIDE_PERFORMANCE_CLAIM_PAPER.pdf", False),
]


def _repo_path(path: str) -> Path:
    return ROOT / path


def _safe_rmtree(path: Path, allowed_parent: Path) -> None:
    path = path.resolve()
    allowed_parent = allowed_parent.resolve()
    if allowed_parent not in path.parents:
        raise ValueError("refusing to delete outside allowed parent: %s" % path)
    if path.is_dir():
        shutil.rmtree(str(path))


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Mapping[str, Any], pretty: bool = True) -> None:
    _ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as handle:
        if pretty:
            json.dump(payload, handle, indent=2, sort_keys=True)
        else:
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
        handle.write("\n")


def _write_text(path: Path, text: str) -> None:
    _ensure_dir(path.parent)
    path.write_text(text, encoding="utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hash_files(root: Path) -> List[Dict[str, Any]]:
    files: List[Dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel == "RELEASE_SEAL_MANIFEST.json":
            continue
        files.append({
            "path": rel,
            "bytes": path.stat().st_size,
            "sha256": _sha256_file(path),
        })
    return files


def _copy_sources(output_dir: Path) -> List[Dict[str, Any]]:
    copied: List[Dict[str, Any]] = []
    for source_rel, dest_rel, optional in SOURCE_ITEMS:
        source = _repo_path(source_rel)
        dest = output_dir / dest_rel
        if not source.exists():
            if optional:
                copied.append({"source": source_rel, "dest": dest_rel, "copied": False, "optional": True})
                continue
            raise FileNotFoundError(source)
        if source.is_dir():
            if dest.exists():
                shutil.rmtree(str(dest))
            _ensure_dir(dest.parent)
            shutil.copytree(str(source), str(dest))
        else:
            _ensure_dir(dest.parent)
            shutil.copy2(str(source), str(dest))
        copied.append({"source": source_rel, "dest": dest_rel, "copied": True, "optional": optional})
    return copied


def _candidate_metrics(performance_gate: Mapping[str, Any]) -> Mapping[str, Any]:
    report = performance_gate.get("report", {})
    metrics = report.get("metrics_by_strategy", {})
    return metrics.get("agentic_candidate_v1", {})


def _format_pct(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    return "%.2f%%" % (float(value) * 100.0)


def _format_ratio(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    return "%.2f" % float(value)


def _build_forward_start(output_dir: Path, defense_dir: Path) -> Dict[str, Any]:
    protocol = _load_json(defense_dir / "forward_paper_trading_protocol.json")
    payload = {
        "schema": "stock_harness_forward_paper_trading_start_v0_3",
        "status": "started",
        "release_id": RELEASE_ID,
        "next_release_target": "v0.3.0-forward",
        "forward_paper_trading_started": True,
        "mode": protocol.get("mode"),
        "frequency": protocol.get("frequency"),
        "forward_start_date": protocol.get("forward_start_date"),
        "checkpoints": protocol.get("checkpoints", []),
        "candidate_strategy_id": protocol.get("candidate_strategy_id"),
        "frozen_strategy_config_hash": protocol.get("candidate_config_fingerprint"),
        "no_live_claims_preserved": True,
        "non_claims": protocol.get("non_claims", []),
        "recordkeeping": protocol.get("recordkeeping", []),
    }
    _write_json(output_dir / "forward" / "FORWARD_PAPER_TRADING_START.json", payload)
    _write_text(output_dir / "forward" / "FORWARD_PAPER_TRADING_START.md", _render_forward_start(payload))
    return payload


def _render_forward_start(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Forward Paper-Trading Start",
        "",
        "- Release sealed: `%s`" % payload["release_id"],
        "- Next release target: `%s`" % payload["next_release_target"],
        "- Status: `%s`" % payload["status"],
        "- Mode: `%s`" % payload["mode"],
        "- Start date: `%s`" % payload["forward_start_date"],
        "- Candidate: `%s`" % payload["candidate_strategy_id"],
        "- Frozen config hash: `%s`" % payload["frozen_strategy_config_hash"],
        "- Checkpoints: `%s`" % "`, `".join(payload.get("checkpoints", [])),
        "",
        "This starts paper-signal logging only. It is not a live-performance claim, not financial advice, and not broker execution evidence.",
        "",
    ]
    return "\n".join(lines)


def _render_one_page_summary(
    performance_gate: Mapping[str, Any],
    defense_gate: Mapping[str, Any],
    official_gate: Mapping[str, Any],
) -> str:
    candidate = _candidate_metrics(performance_gate)
    claim = performance_gate.get("claim_scope", {})
    report_claim = performance_gate.get("report", {}).get("claim", {})
    non_claims = report_claim.get("non_claims", [])
    lines = [
        "# Downside Performance Harness v0.2.0-defense",
        "",
        "A claim-governed trading research harness with verification gates, deterministic agentic workflow, performance benchmark, and defense packet.",
        "",
        "## Claim",
        "",
        "> SOTA-grade downside-adjusted hypothetical backtested performance under the included deterministic `downside_performance_v1` benchmark suite.",
        "",
        "Scope: `%s`; performance type: `%s`." % (
            claim.get("claim_limit"),
            claim.get("performance_type"),
        ),
        "",
        "## Key Results",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        "| Return multiple | %.3fx |" % float(candidate.get("return_multiple", 0.0)),
        "| Total return | %s |" % _format_pct(candidate.get("total_return")),
        "| CAGR | %s |" % _format_pct(candidate.get("cagr")),
        "| Max drawdown | %s |" % _format_pct(candidate.get("max_drawdown")),
        "| Calmar | %s |" % _format_ratio(candidate.get("calmar_ratio")),
        "| Sharpe | %s |" % _format_ratio(candidate.get("sharpe_ratio")),
        "| performance_claim_publishable | `%s` |" % performance_gate.get("performance_claim_publishable"),
        "| defense_claim_defensible | `%s` |" % defense_gate.get("defense_claim_defensible"),
        "| official_claim_publishable | `%s` |" % official_gate.get("official_claim_publishable"),
        "",
        "## Non-Claims",
        "",
    ]
    for item in non_claims:
        lines.append("- %s" % item)
    lines.extend([
        "",
        "## Evidence",
        "",
        "- Performance evidence: `evidence/downside_performance_v1_evidence`",
        "- Defense packet: `evidence/downside_performance_v1_defense_packet`",
        "- Public snapshot: `public_snapshot/downside_performance_v1_public_snapshot`",
        "- Official claim packet: `official/stock_harness_official_claim_packet`",
        "- Release candidate: `official/stock_harness_release_candidate`",
        "",
    ])
    return "\n".join(lines)


def _render_release_seal(
    manifest: Mapping[str, Any],
    performance_gate: Mapping[str, Any],
    defense_gate: Mapping[str, Any],
    official_gate: Mapping[str, Any],
    forward_start: Mapping[str, Any],
) -> str:
    lines = [
        "# v0.2.0-defense Release Seal",
        "",
        "This folder freezes the v0.2.0-defense evidence set. No additional v0.2.0-defense feature work should be added after this seal; forward evidence belongs to `v0.3.0-forward`.",
        "",
        "## Status",
        "",
        "- performance_claim_publishable: `%s`" % performance_gate.get("performance_claim_publishable"),
        "- defense_claim_defensible: `%s`" % defense_gate.get("defense_claim_defensible"),
        "- official_claim_publishable: `%s`" % official_gate.get("official_claim_publishable"),
        "- forward_paper_trading_started: `%s`" % forward_start.get("forward_paper_trading_started"),
        "- file_count: `%s`" % manifest.get("file_count"),
        "",
        "## Boundary",
        "",
        "The sealed performance claim remains hypothetical, backtested, deterministic, and limited to the included `downside_performance_v1` benchmark suite.",
        "",
    ]
    return "\n".join(lines)


def seal_release(output_dir: Path, clean: bool = False) -> Dict[str, Any]:
    output_dir = (ROOT / output_dir).resolve() if not output_dir.is_absolute() else output_dir.resolve()
    if clean:
        _safe_rmtree(output_dir, ROOT / "dist")
    _ensure_dir(output_dir)

    copied = _copy_sources(output_dir)

    performance_gate = _load_json(output_dir / "reports" / "downside_performance_claim_gate_latest.json")
    defense_gate = _load_json(output_dir / "evidence" / "downside_performance_v1_defense_packet" / "defense_gate.json")
    official_gate = _load_json(output_dir / "reports" / "stock_harness_official_claim_gate_defense_latest.json")
    forward_start = _build_forward_start(output_dir, output_dir / "evidence" / "downside_performance_v1_defense_packet")

    _write_text(
        output_dir / "ONE_PAGE_SUMMARY.md",
        _render_one_page_summary(performance_gate, defense_gate, official_gate),
    )

    manifest_without_hashes = {
        "schema": "stock_harness_v0_2_0_defense_release_seal_v1",
        "release_id": RELEASE_ID,
        "status": "passed",
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "claim_scope": {
            "performance_claim": "SOTA-grade downside-adjusted hypothetical backtested performance under the included downside_performance_v1 benchmark only",
            "verification_claim": "SOTA-grade deterministic verification coverage only",
            "next_release_target": "v0.3.0-forward",
        },
        "checks": {
            "performance_claim_publishable": performance_gate.get("performance_claim_publishable") is True,
            "defense_claim_defensible": defense_gate.get("defense_claim_defensible") is True,
            "official_claim_publishable": official_gate.get("official_claim_publishable") is True,
            "forward_paper_trading_started": forward_start.get("forward_paper_trading_started") is True,
            "no_live_claims_preserved": forward_start.get("no_live_claims_preserved") is True,
        },
        "copied_sources": copied,
    }
    files = _hash_files(output_dir)
    manifest = dict(manifest_without_hashes)
    manifest["file_count"] = len(files)
    manifest["files"] = files
    manifest["status"] = "passed" if all(manifest["checks"].values()) else "failed"
    _write_json(output_dir / "RELEASE_SEAL_MANIFEST.json", manifest)
    _write_text(output_dir / "RELEASE_SEAL.md", _render_release_seal(
        manifest,
        performance_gate,
        defense_gate,
        official_gate,
        forward_start,
    ))
    files = _hash_files(output_dir)
    manifest["file_count"] = len(files)
    manifest["files"] = files
    _write_json(output_dir / "RELEASE_SEAL_MANIFEST.json", manifest)
    return manifest


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)
    manifest = seal_release(Path(args.output_dir), clean=args.clean)
    if args.pretty:
        print(json.dumps(manifest, indent=2, sort_keys=True))
    else:
        print(json.dumps(manifest, sort_keys=True, separators=(",", ":")))
    return 0 if manifest.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
