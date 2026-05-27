# Benchmark

The public benchmark target is `downside_verification_v1`.

It is a deterministic local benchmark suite for downside-aware stock research verification. It uses synthetic in-memory CSV fixtures and local temp directories, so it does not require network access, market-data vendors, or third-party Python packages.

## Official Release Gate

```bash
python3 ops/run_stock_harness_official_claim_gate.py --pretty --output reports/stock_harness_official_claim_gate_latest.json
```

The official publication gate runs the Python evidence layer below, builds the clean release bundle, builds and verifies the reviewer-facing evidence packet with an embedded official release-gate JSON, builds, verifies, and replays the release candidate artifacts, and requires Rust validation. The final official claim packet under `dist/stock_harness_official_claim_packet` is the publication artifact that binds those JSON outputs and manifests with hash verification. The individual commands below remain useful for fast local debugging.

## Required Commands

```bash
python3 -m unittest tests/test_stock_harness.py
python3 ops/benchmark_stock_harness.py --pretty
python3 ops/compare_stock_harness_baselines.py --pretty
python3 ops/run_stock_harness_release_gate.py --pretty --output reports/stock_harness_release_gate_latest.json
python3 ops/build_stock_harness_evidence_packet.py --clean --pretty --release-gate-json reports/stock_harness_release_gate_latest.json
python3 ops/verify_stock_harness_evidence_packet.py --pretty --require-release-gate-json --require-official-claim-ready
python3 ops/build_stock_harness_release_candidate.py --clean --pretty
python3 ops/verify_stock_harness_release_candidate.py --pretty --require-release-gate-json --require-official-claim-ready
python3 ops/replay_stock_harness_release_candidate.py --clean --pretty --require-release-gate-json --require-official-claim-ready
python3 ops/build_stock_harness_official_claim_packet.py --clean --pretty --official-claim-gate-json reports/stock_harness_official_claim_gate_latest.json --official-release-gate-json reports/stock_harness_release_gate_official.json --official-replay-json reports/stock_harness_release_candidate_replay_official.json
python3 ops/verify_stock_harness_official_claim_packet.py --pretty
```

Set `STOCK_HARNESS_TMPDIR` if the runner needs temporary files under a specific writable directory.

## Required Pass Criteria

The benchmark must show:

- Oracle benchmark passes all included no-dependency cases.
- Lookahead audit detects mutated lookahead execution.
- External-engine style parity has zero equity/trade/fill/order-intent diffs.
- Data-quality gates reject invalid OHLCV and adjusted-price failures.
- Market-calendar profile checks expected sessions.
- Multi-asset benchmark reports grouped metrics and writes per-case artifacts.
- Stress matrix runs delay, gap, cash-yield, liquidity, and market-impact cases.
- Experiment manifests include deterministic hashes and configuration.
- Baseline comparison reports full coverage for `angelos_stock_harness` on the benchmark capability matrix.
- Evidence packet manifest records the benchmark, claim comparison, release bundle manifest, release audit, claim contract, and expected summary.
- Evidence packet verifier confirms manifest hashes, required files, scoped claim schemas, and release-gate readiness.
- Release candidate verifier confirms the clean release and evidence packet archives are hashed and contain passing manifests.
- Release candidate replay extracts the packaged source zip and reruns the scoped verification commands from that extracted tree.
- Official claim packet verification confirms the final publication packet hashes and requires official gate, release gate, replay, manifest, and claim-contract readiness.

## What The Baseline Comparison Means

`ops/compare_stock_harness_baselines.py` is a coverage comparison, not a runtime shootout against installed third-party libraries. It compares the included harness against simple local baseline profiles:

- A minimal moving-average backtest baseline.
- A generic external-engine-with-custom-hooks profile.
- The full `angelos_stock_harness` profile.

The comparison supports a scoped claim that this harness packages the benchmarked verification layers together locally. It does not claim every external engine lacks those features, because many engines can be extended with custom code.
