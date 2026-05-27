# Claims

This document defines the strongest claim this repository is prepared to make publicly.

## Supported Claim

The supported claim is:

> SOTA-grade deterministic verification coverage for local, no-dependency, downside-aware stock backtest research on the included `downside_verification_v1` benchmark suite.

This is a benchmarked infrastructure claim. It means the harness combines, in one local no-dependency verification core, the benchmarked coverage listed in [BENCHMARK.md](BENCHMARK.md): data-quality gates, no-lookahead execution, oracle parity, external-engine style parity, multi-asset artifacts, walk-forward validation, and stress matrices with downside-first verdicts.

## Why This Is Not A Trading Claim

The harness does not make or support claims about:

- Future returns.
- Alpha generation.
- Investment recommendations.
- Live trading readiness.
- Order routing.
- Broker integration.
- Tax, legal, or suitability advice.
- Dominance over every possible external research stack.

## Non-Claim Contract

The machine-readable claim contract requires these exact public non-claims:

- No financial advice.
- No live trading readiness claim.
- No order routing or broker integration claim.
- No investment-performance or alpha-generation claim.
- No universal external-framework dominance claim.
## Evidence Standard

A public claim must be backed by:

- Passing `ops/run_stock_harness_official_claim_gate.py` on a Python + Cargo host with `official_claim_publishable: true`.
- Passing official claim packet verification: `ops/build_stock_harness_official_claim_packet.py --clean --pretty` followed by `ops/verify_stock_harness_official_claim_packet.py --pretty`, producing `dist/stock_harness_official_claim_packet/OFFICIAL_CLAIM_PACKET_MANIFEST.json`.
- Passing `ops/run_stock_harness_release_gate.py` on a Python + Cargo host with `official_claim_ready: true`.
- Passing the scoped stock harness unit suite: `python3 -m unittest tests/test_stock_harness.py`.
- Passing `ops/benchmark_stock_harness.py --pretty` with `all_passed: true`.
- Passing `ops/compare_stock_harness_baselines.py --pretty` with `claim.status: supported_for_included_benchmark_suite`.
- Passing clean release bundle assertions: `release_bundle_passed: true` and `release_bundle_scope_enforced: true`.
- Passing evidence packet assertion: `evidence_packet_passed: true`, with `dist/stock_harness_evidence_packet/EVIDENCE_MANIFEST.json` and the release-gate JSON copied into the packet for review.
- Passing evidence packet verification assertion: `evidence_packet_verified: true`, with packet file hashes and JSON schemas verified before publication.
- Passing release candidate assertions: `release_candidate_passed: true` and `release_candidate_verified: true`, with the clean release bundle and evidence packet packaged into hashed zip artifacts.
- Passing release candidate replay assertion: `release_candidate_replayed: true`, with the packaged source zip extracted and used to rerun the scoped verification commands.
- A stable benchmark description and machine-readable claim contract under `benchmarks/downside_verification_v1/`.
- A clear limitation, release-gate, and threat-model document.

## Claim Boundary

Acceptable wording:

> SOTA-grade verification coverage on the included deterministic downside-aware benchmark suite.

Avoid wording that implies:

- universal superiority as a trading system
- investment-performance or alpha proof
- broker or order-routing readiness
- guaranteed downside or return outcomes
- external certification across all backtesting frameworks

## Versioned Claim

Current claim target:

- Claim ID: `downside_verification_sota_grade_v0_1`
- Benchmark suite: `downside_verification_v1`
- Runtime mode: local CSV, no network, no external dependencies
- Output type: research verification evidence only

