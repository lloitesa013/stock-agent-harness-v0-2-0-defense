# Downside-Aware Stock Backtest Verification Harness

## A SOTA-Grade Local Benchmarking Infrastructure For Deterministic Drawdown-First Research

Status: technical report draft for private review  
Claim ID: `downside_verification_sota_grade_v0_1`  
Benchmark suite: `downside_verification_v1`  
Runtime scope: local CSV, no network, no external Python or Rust dependencies  
Public-disclosure note: review patent and licensing strategy before publication

## Abstract

Most retail and research backtesting workflows emphasize return summaries while leaving downside failure modes, data defects, lookahead leakage, execution drift, and reproducibility gaps as optional checks. This report presents a deterministic, local, no-dependency verification harness for downside-aware stock-strategy research. The system is not a trading bot, broker integration, investment adviser, or live execution engine. It is a research-only verification core designed to reject fragile backtests before they are mistaken for robust strategies.

The harness combines strict OHLCV data-quality gates, lagged no-lookahead moving-average-to-cash execution, maximum-drawdown-first verdicts, independent oracle parity, lookahead mutation audit, external-engine style parity, multi-asset benchmark packs, walk-forward validation, regime stress, parameter overfit sweeps, cost/slippage stress, expanded execution stress, and deterministic experiment manifests. On the included `downside_verification_v1` benchmark suite, the harness covers all 18 defined verification capabilities and passes the expected benchmark summary with no diffs.

The supported claim is narrow: SOTA-grade deterministic verification coverage for local, no-dependency, downside-aware stock backtest research on the included benchmark suite. The report does not claim superior investment performance, alpha generation, live-trading readiness, broker-grade execution realism, or universal dominance over all external backtesting frameworks.

## 1. Problem Statement

Backtests can look compelling while still being invalid or fragile. Common failure modes include lookahead leakage, missing sessions, duplicate dates, unhandled split-like jumps, inconsistent adjusted prices, hidden execution assumptions, overfit parameters, weak performance under costs, and unreproducible experiment state.

The core research problem addressed here is:

> Can a stock-research harness make downside failure, data defects, leakage, parity drift, and stress fragility first-class deterministic verification targets while remaining local, cheap, reproducible, and dependency-free?

The objective is not to predict future prices. The objective is to make it harder for a weak research result to survive verification.

## 2. Claim Boundary

### 2.1 Supported Claim

The supported public claim is:

> SOTA-grade deterministic verification coverage for local, no-dependency, downside-aware stock backtest research on the included `downside_verification_v1` benchmark suite.

This is a verification-coverage claim. It is scoped to the included benchmark and to the local deterministic feature matrix in this repository.

### 2.2 Non-Claims

This work does not claim:

- Financial advice.
- Future returns.
- Alpha generation.
- Live trading readiness.
- Order routing.
- Broker integration.
- Tax, legal, or suitability analysis.
- Industry certification.
- Peer-reviewed external SOTA status.
- Universal superiority over every external backtesting engine.

## 3. Contributions

The harness contributes a compact no-dependency verification stack with the following benchmarked layers:

1. Local CSV OHLCV loading with explicit structural validation.
2. Data-quality gate covering invalid OHLCV bars, duplicate/nonmonotonic dates, missing sessions, zero volume, open gaps, split-like jumps, adjusted-close consistency, adjusted-OHLC consistency, and optional local market-calendar profiles.
3. Lagged moving-average-to-cash backtest behavior designed to avoid same-bar lookahead trading.
4. MDD-first verdicts that require drawdown to remain inside a configured limit and improve on benchmark drawdown.
5. Independent no-dependency oracle parity across synthetic regimes.
6. Lookahead mutation audit that verifies historical decisions are invariant to future price perturbations.
7. External-engine style parity for equity curves, trades, fills, and order intents.
8. Walk-forward downside validation.
9. Regime stress validation.
10. Parameter overfit sweep.
11. Cost and slippage stress.
12. Expanded execution stress for delayed execution, adverse gaps, cash yield, liquidity participation, and market impact.
13. Multi-asset benchmark packs with grouped metrics.
14. Per-case artifact bundles for local inspection.
15. Deterministic experiment manifests with reproducibility fingerprints.
16. A claim evidence CLI that maps benchmark results to a public claim boundary.
17. A reviewer-facing evidence packet builder that materializes benchmark, claim, audit, contract, release-gate, and release-manifest outputs into one hashed directory.
18. A packet verifier that checks required files, SHA-256 hashes, scoped JSON schemas, and official release-gate readiness before publication.
19. A release candidate builder and verifier that package the clean release bundle and evidence packet into hashed zip artifacts.

## 4. System Design

### 4.1 Research-Only Core

The harness is intentionally local. It does not connect to brokers, download data, route orders, or require third-party Python packages. Inputs are local CSV files or synthetic fixtures. Outputs are JSON and CSV artifacts.

### 4.2 Downside-First Verdicts

The primary verdict is based on downside protection rather than raw return. A result is kept only when the strategy maximum drawdown is within the configured limit and improves on the buy-and-hold benchmark drawdown. This design reflects the thesis that bull-market upside is not enough; the hard verification problem is whether the system avoids riding bear markets down.

### 4.3 Deterministic Execution

The included moving-average-to-cash strategy uses lagged signals. Target exposure changes are decided from historical information and filled on a later open. The backtest records equity points, trades, fills, and order intents so parity checks can inspect both portfolio state and execution intent.

### 4.4 Verification Before Optimization

The harness does not optimize for the best parameter by default. Instead, it verifies whether a candidate survives adverse checks: data quality, oracle parity, leakage audit, walk-forward folds, regime cases, parameter stability, costs, slippage, delayed fills, gaps, liquidity caps, market impact, and multi-asset grouping.

## 5. Benchmark Suite

The benchmark suite is `downside_verification_v1`. It is stored under:

```text
benchmarks/downside_verification_v1/
```

The suite is deterministic and local:

- No network.
- No external dependencies.
- No vendor data.
- No broker connectivity.
- Synthetic fixtures only.

### 5.1 Required Commands

```bash
python3 -m py_compile angelos_os/stock_harness.py angelos_os/__init__.py angelos_os/engine.py angelos_os/profiles.py angelos_os/providers.py angelos_os/safety.py angelos_os/schemas.py angelos_os/score_core.py angelos_os/validation.py angelos_os/version.py ops/benchmark_stock_harness.py ops/compare_stock_harness_baselines.py ops/run_stock_harness_release_gate.py ops/run_stock_harness_official_claim_gate.py ops/build_stock_harness_release_bundle.py ops/build_stock_harness_evidence_packet.py ops/verify_stock_harness_evidence_packet.py ops/build_stock_harness_release_candidate.py ops/verify_stock_harness_release_candidate.py ops/replay_stock_harness_release_candidate.py ops/audit_stock_harness_release.py tests/test_stock_harness.py
python3 -m unittest tests/test_stock_harness.py
python3 ops/benchmark_stock_harness.py
python3 ops/compare_stock_harness_baselines.py --pretty
python3 ops/run_stock_harness_release_gate.py --pretty --output reports/stock_harness_release_gate_latest.json
python3 ops/build_stock_harness_evidence_packet.py --clean --pretty --release-gate-json reports/stock_harness_release_gate_latest.json
python3 ops/verify_stock_harness_evidence_packet.py --pretty --require-release-gate-json --require-official-claim-ready
python3 ops/build_stock_harness_release_candidate.py --clean --pretty
python3 ops/verify_stock_harness_release_candidate.py --pretty --require-release-gate-json --require-official-claim-ready
python3 ops/replay_stock_harness_release_candidate.py --clean --pretty --require-release-gate-json --require-official-claim-ready
python3 ops/run_stock_harness_official_claim_gate.py --pretty --output reports/stock_harness_official_claim_gate_latest.json
python3 ops/build_stock_harness_official_claim_packet.py --clean --pretty --official-claim-gate-json reports/stock_harness_official_claim_gate_latest.json --official-release-gate-json reports/stock_harness_release_gate_official.json --official-replay-json reports/stock_harness_release_candidate_replay_official.json
python3 ops/verify_stock_harness_official_claim_packet.py --pretty
```

### 5.2 Expected Summary

The expected benchmark subset is versioned in:

```text
benchmarks/downside_verification_v1/expected_summary.json
```

Current expected values:

| Field | Expected |
| --- | ---: |
| all_passed | true |
| oracle_case_count | 4 |
| engine_parity_diff_count | 0 |
| engine_parity_compared_order_intents | 2 |
| calendar_expected_sessions | 3 |
| adjusted_ohlc_checks_applied | true |
| multi_asset_case_artifact_count | 2 |
| stress_matrix_case_count | 5 |

## 6. Capability Matrix

`ops/compare_stock_harness_baselines.py` defines 18 benchmark capabilities. The comparison is a local coverage matrix, not a runtime benchmark against installed third-party engines.

| Capability | Included harness |
| --- | ---: |
| Local CSV, no-network, no-dependency benchmark execution | yes |
| Lagged signal execution with no same-bar lookahead trading | yes |
| MDD-first verdict and downside report fields | yes |
| Independent no-dependency oracle benchmark parity | yes |
| Lookahead mutation audit | yes |
| Data-quality structural gate | yes |
| Market-calendar expected-session profile checks | yes |
| Adjusted OHLC consistency checks | yes |
| External-engine style equity, trade, and fill parity | yes |
| Order-intent parity | yes |
| Walk-forward downside validation | yes |
| Regime stress validation | yes |
| Parameter overfit sweep | yes |
| Cost and slippage stress | yes |
| Expanded execution stress | yes |
| Multi-asset grouped downside metrics | yes |
| Per-case artifact bundle writer | yes |
| Deterministic experiment manifest | yes |

Current coverage result:

| Profile | Covered | Total | Score |
| --- | ---: | ---: | ---: |
| `angelos_stock_harness` | 18 | 18 | 1.000000 |
| `generic_backtesting_engine_with_custom_hooks` | 7 | 18 | 0.388889 |
| `minimal_ma_backtest_baseline` | 3 | 18 | 0.166667 |

The generic external-engine profile is deliberately unnamed. Many external engines can be extended with custom hooks, so the current claim is about the included local coverage package rather than a claim that named external projects cannot implement similar checks.

## 7. Results

Latest local validation status:

| Command | Result |
| --- | --- |
| `python3 -m py_compile ...` | pass |
| `python3 -m unittest tests/test_stock_harness.py` | stock harness unit suite OK |
| `python3 ops/run_stock_harness_release_gate.py --pretty --output reports/stock_harness_release_gate_latest.json` | scoped stock harness release gate |
| `python3 ops/build_stock_harness_evidence_packet.py --clean --pretty --release-gate-json reports/stock_harness_release_gate_latest.json` | writes `EVIDENCE_MANIFEST.json` |
| `python3 ops/verify_stock_harness_evidence_packet.py --pretty --require-release-gate-json --require-official-claim-ready` | verifies packet hashes and official gate readiness |
| `python3 ops/build_stock_harness_release_candidate.py --clean --pretty` | writes release candidate zip artifacts |
| `python3 ops/verify_stock_harness_release_candidate.py --pretty --require-release-gate-json --require-official-claim-ready` | verifies candidate component hashes and zip payloads |
| `python3 ops/replay_stock_harness_release_candidate.py --clean --pretty --require-release-gate-json --require-official-claim-ready` | extracts release zip and reruns scoped verification from packaged source |
| `python3 ops/run_stock_harness_official_claim_gate.py --pretty --output reports/stock_harness_official_claim_gate_latest.json` | final publication gate; must report `official_claim_publishable: true` |
| `python3 ops/build_stock_harness_official_claim_packet.py --clean --pretty --official-claim-gate-json reports/stock_harness_official_claim_gate_latest.json --official-release-gate-json reports/stock_harness_release_gate_official.json --official-replay-json reports/stock_harness_release_candidate_replay_official.json` | builds the final official claim packet |
| `python3 ops/verify_stock_harness_official_claim_packet.py --pretty` | verifies official claim packet hashes and payload readiness |
| `python3 ops/benchmark_stock_harness.py` | `all_passed: true` |
| `python3 ops/compare_stock_harness_baselines.py` | `supported_for_included_benchmark_suite` |
| `cargo test --manifest-path rust_stock_harness/Cargo.toml` | 7 Rust tests OK |
| `cargo run --manifest-path rust_stock_harness/Cargo.toml --bin stock-harness-benchmark -- --pretty` | `all_passed: true` |

Benchmark evidence:

- Oracle cases: 4.
- Oracle parity: all cases pass.
- External-engine style parity diffs: 0.
- Compared order intents: 2.
- Market-calendar expected sessions: 3.
- Adjusted OHLC checks applied: true.
- Multi-asset case artifacts: 2.
- Expanded stress cases: 5.
- Included harness coverage score: 1.0.
- Missing included-harness capabilities: none.

### 7.1 Rust v0 Validation

A std-only Rust v0 port is included under `rust_stock_harness/`. It implements the systems-language foundation for the verification core: OHLCV CSV loading, structural data-quality checks, lagged moving-average-to-cash execution, MDD-first verdicts, order/trade ledgers, deterministic benchmark cases, and a benchmark CLI.

The Rust port is not yet the full SOTA-grade evidence package. The Python implementation remains the complete reference for the 18-capability claim. The Rust result is nevertheless important because it validates that the core deterministic harness can be expressed without external crates in a strongly typed compiled implementation.

Current Rust validation:

- Toolchain: `rustc 1.95.0`, `cargo 1.95.0`.
- Unit tests: 7 passed.
- Benchmark CLI: `rust_stock_harness_v0`, `all_passed: true`.
- External crates: none declared.

## 8. Novelty Assessment

The novelty is not any single backtest metric. Moving averages, drawdown, costs, and walk-forward validation are well-known ideas. The novelty claim is the integrated verification package:

- Downside-first verdicts are the default judgment layer.
- Leakage, data quality, oracle parity, external trace parity, stress robustness, multi-asset grouping, and reproducibility are handled together.
- The benchmark is deterministic, local, no-network, and dependency-free.
- The claim boundary is machine-checkable through a dedicated evidence CLI.
- The harness produces artifacts suitable for inspection rather than only summary metrics.
- The official release flow emits a single evidence packet with hashed benchmark, comparison, audit, contract, expected-summary, and release-manifest files.
- The verifier independently checks packet integrity and refuses official publication evidence unless the embedded release gate reports `official_claim_ready: true`.
- The final release candidate packages the clean source bundle and evidence packet as hashed archives with a machine-readable candidate manifest.
- The release candidate replay extracts the packaged source zip and reruns the scoped verification flow from that extracted tree.
- The official publication gate requires that all of the above are rerun with `official_claim_ready: true` evidence embedded before it reports `official_claim_publishable: true`.
- The official claim packet binds the publication gate, official release gate, official replay JSON, release/evidence/candidate manifests, and claim contract into one hash-verified artifact directory.

The strongest defensible novelty statement is:

> The project packages a broad, deterministic, downside-first verification stack into a local no-dependency benchmark harness with explicit public claim evidence.

The current materials do not establish peer-reviewed novelty or patentability. Patentability requires separate legal analysis, prior-art search, and claim drafting.

## 9. Reproducibility

A reviewer can reproduce the current claim locally by running:

```bash
python3 ops/benchmark_stock_harness.py
python3 ops/compare_stock_harness_baselines.py --pretty
python3 ops/run_stock_harness_release_gate.py --pretty --output reports/stock_harness_release_gate_latest.json
python3 ops/build_stock_harness_evidence_packet.py --clean --pretty --release-gate-json reports/stock_harness_release_gate_latest.json
python3 ops/verify_stock_harness_evidence_packet.py --pretty --require-release-gate-json --require-official-claim-ready
python3 ops/build_stock_harness_release_candidate.py --clean --pretty
python3 ops/verify_stock_harness_release_candidate.py --pretty --require-release-gate-json --require-official-claim-ready
python3 ops/replay_stock_harness_release_candidate.py --clean --pretty --require-release-gate-json --require-official-claim-ready
python3 ops/run_stock_harness_official_claim_gate.py --pretty --output reports/stock_harness_official_claim_gate_latest.json
python3 ops/build_stock_harness_official_claim_packet.py --clean --pretty --official-claim-gate-json reports/stock_harness_official_claim_gate_latest.json --official-release-gate-json reports/stock_harness_release_gate_official.json --official-replay-json reports/stock_harness_release_candidate_replay_official.json
python3 ops/verify_stock_harness_official_claim_packet.py --pretty
```

The release reproduction packet under `dist/stock_harness_evidence_packet/` should be published with:

- Exact git commit or release tag.
- Full JSON from benchmark, comparison, release audit, and release gate commands.
- Unit-test output.
- Python version.
- Operating system details.
- MIT license file included in the repository.

## 10. Threats To Validity

The benchmark uses synthetic fixtures, which makes it deterministic but limits real-market representativeness. The data-quality gate can detect structural issues but cannot prove vendor correctness, survivorship-bias freedom, complete corporate-action handling, or dataset licensing. The execution model includes stress assumptions but is not broker-grade market simulation. The baseline comparison is a feature-coverage matrix, not a runtime competition against all available engines.

These threats do not invalidate the scoped claim, but they prevent broader claims about investment performance or universal external SOTA status.

## 11. Public Release Checklist

Before public release:

- Complete patent/public-disclosure review.
- MIT license is present; publish from the clean bundle boundary.
- CI runs py_compile, unit tests, benchmark CLI, claim evidence CLI, clean bundle manifest generation, evidence packet generation and verification, release candidate generation, verification, replay, release audit, Rust validation, the final official publication gate, and official claim packet build/verify.
- Publish release-gate evidence JSON, official publication-gate JSON, benchmark outputs, `dist/stock_harness_release/RELEASE_MANIFEST.json`, `dist/stock_harness_evidence_packet/EVIDENCE_MANIFEST.json`, `dist/stock_harness_release_candidate/RELEASE_CANDIDATE_MANIFEST.json`, release-candidate replay JSON, and `dist/stock_harness_official_claim_packet/OFFICIAL_CLAIM_PACKET_MANIFEST.json` for the release tag.
- Use `ops/run_stock_harness_official_claim_gate.py` as the final official gate; it invokes the full release gate, rebuilds official evidence, verifies official candidate artifacts, and replays the packaged source.
- Keep the README claim language aligned with `docs/CLAIMS.md`.

## 12. Conclusion

The Downside-Aware Stock Harness supports a narrow but meaningful SOTA-grade verification claim: on the included deterministic local benchmark suite, it provides complete coverage of the defined downside-aware verification capability matrix while preserving no-network, no-dependency reproducibility. The result is best understood as research infrastructure for rejecting fragile backtests, not as a trading system or investment-performance claim.
