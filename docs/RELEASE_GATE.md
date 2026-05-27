# Stock Harness Release Gate

This document defines the evidence gate for the scoped Stock Harness SOTA-grade verification claim.

The official claim remains narrow:

> SOTA-grade deterministic verification coverage for local, no-dependency, downside-aware stock backtest research on the included `downside_verification_v1` benchmark suite.

The gate does not claim alpha generation, investment performance, live trading readiness, order routing, broker integration, or universal dominance over external backtesting frameworks.

## Official Publication Gate

Run from the repository root on a host with Python and Rust/Cargo available:

```bash
python3 ops/run_stock_harness_official_claim_gate.py --pretty --output reports/stock_harness_official_claim_gate_latest.json
```

The resulting JSON must have:

- `schema: stock_harness_official_claim_gate_v1`
- `official_claim_publishable: true`
- `status: passed`
- `full_release_gate_official_ready: true`
- `evidence_packet_verified_for_publication: true`
- `release_candidate_verified_for_publication: true`
- `release_candidate_replayed_for_publication: true`

This is the final gate for public claim publication. It runs the full release gate, embeds the release-gate JSON into the evidence packet, verifies evidence and release candidate artifacts with `--require-official-claim-ready`, and replays the packaged source zip without `--skip-rust`.
## Official Claim Packet

After the official publication gate succeeds, build and verify the final packet that should be attached to a public release tag:

```bash
python3 ops/build_stock_harness_official_claim_packet.py --clean --pretty --official-claim-gate-json reports/stock_harness_official_claim_gate_latest.json --official-release-gate-json reports/stock_harness_release_gate_official.json --official-replay-json reports/stock_harness_release_candidate_replay_official.json
python3 ops/verify_stock_harness_official_claim_packet.py --pretty
```

The builder writes `dist/stock_harness_official_claim_packet/OFFICIAL_CLAIM_PACKET_MANIFEST.json`. The verifier checks packet hashes, the official publication gate JSON, the full release gate JSON, the release-candidate replay JSON, release/evidence/candidate manifests, and the claim contract. A public claim packet is valid only when this verifier reports `status: passed`.

## Full Release Gate

Run from the repository root on a host with Python and Rust/Cargo available:

```bash
python3 ops/run_stock_harness_release_gate.py --pretty --output reports/stock_harness_release_gate_latest.json
```

The resulting JSON must have:

- `schema: stock_harness_release_gate_v1`
- `official_claim_ready: true`
- `overall_status: passed`
- `claim.status: supported_for_included_benchmark_suite`
- `coverage_score: 1.0` for `angelos_stock_harness` inside the captured claim-comparison output
- `release_bundle_passed: true`
- `release_bundle_scope_enforced: true`
- `release_audit_passed: true`
- `evidence_packet_passed: true`
- `evidence_packet_verified: true`
- `release_candidate_passed: true`
- `release_candidate_verified: true`
- `release_candidate_replayed: true`
- `claim_contract_required_assertions_present: true`
- Rust unit tests and Rust benchmark CLI passing

The full gate also verifies the machine-readable claim contract, writes `dist/stock_harness_release/RELEASE_MANIFEST.json` through the clean bundle builder, writes `dist/stock_harness_evidence_packet/EVIDENCE_MANIFEST.json` for reviewer-facing evidence, verifies the packet hashes and JSON schemas, packages both into a release candidate artifact set, and replays the packaged source zip.

## Python-Only Local Gate

On local hosts without Cargo, use:

```bash
python3 ops/run_stock_harness_release_gate.py --pretty --skip-rust --output reports/stock_harness_release_gate_python_only.json
```

This is useful during development, but it is not the full official release gate. It may pass the Python evidence layer and clean bundle assertions while still reporting `official_claim_ready: false`.

## Why The Gate Is Scoped

The source workspace may contain other experiments. The stock harness release gate intentionally runs the stock-harness claim surface only:

- Python compile check for stock harness modules, release gate code, and bundle code
- `tests/test_stock_harness.py`
- `ops/benchmark_stock_harness.py --pretty`
- `ops/compare_stock_harness_baselines.py --pretty`
- `ops/build_stock_harness_release_bundle.py --clean --pretty`
- `ops/audit_stock_harness_release.py --pretty`
- `ops/build_stock_harness_evidence_packet.py --clean --pretty`
- `ops/verify_stock_harness_evidence_packet.py --pretty`
- `ops/build_stock_harness_release_candidate.py --clean --pretty`
- `ops/verify_stock_harness_release_candidate.py --pretty`
- `ops/replay_stock_harness_release_candidate.py --clean --pretty`
- Rust v0 unit tests and benchmark CLI

Repo-wide test discovery is not part of the Stock Harness public claim.

## Clean Release Bundle

The full gate builds a publication-ready bundle containing only the Stock Harness claim surface. To run only that bundle builder, use:

```bash
python3 ops/build_stock_harness_release_bundle.py --clean --pretty
```

The bundle writes `dist/stock_harness_release/RELEASE_MANIFEST.json` with SHA-256 hashes for every included source, doc, benchmark, test, CI, and Rust file. Build artifacts and unrelated workspace experiments are excluded.

The release audit also scans the release text surface for overbroad public-claim language around investment performance, alpha, return guarantees, and broker readiness. The only place for exact forbidden examples is the explicit "avoid wording" block in [CLAIMS.md](CLAIMS.md).

## Evidence Packet

To materialize the benchmark, claim comparison, release audit, claim contract, expected summary, and clean bundle manifest into one review directory, run:

```bash
python3 ops/build_stock_harness_evidence_packet.py --clean --pretty
```

After the release gate writes its JSON, include it in the packet:

```bash
python3 ops/build_stock_harness_evidence_packet.py --clean --pretty --release-gate-json reports/stock_harness_release_gate_latest.json
```

The packet writes `dist/stock_harness_evidence_packet/EVIDENCE_MANIFEST.json`. A public release should publish this packet next to the clean release bundle so reviewers can inspect the exact claim evidence without searching through unrelated workspace files.

Verify the packet:

```bash
python3 ops/verify_stock_harness_evidence_packet.py --pretty --require-release-gate-json --require-official-claim-ready
```

For local Python-only development without Cargo, omit `--require-official-claim-ready`. The official release path should keep it enabled so `release_gate.json` must report `official_claim_ready: true`.

## Release Candidate

To package the clean release bundle and evidence packet into distributable archives, run:

```bash
python3 ops/build_stock_harness_release_candidate.py --clean --pretty
python3 ops/verify_stock_harness_release_candidate.py --pretty --require-release-gate-json --require-official-claim-ready
```

The builder writes `dist/stock_harness_release_candidate/RELEASE_CANDIDATE_MANIFEST.json`, `stock_harness_release.zip`, and `stock_harness_evidence_packet.zip`. The verifier checks component hashes and confirms the zip payloads contain passing release and evidence manifests.

## Release Candidate Replay

To prove that the packaged release source can reproduce the scoped checks after extraction, run:

```bash
python3 ops/replay_stock_harness_release_candidate.py --clean --pretty --require-release-gate-json --require-official-claim-ready
```

The replay extracts `stock_harness_release.zip`, compiles the packaged Python claim surface, runs the packaged unit suite, benchmark, claim comparison, release audit, candidate verifier, and Rust checks when Cargo is available. Local Python-only development may add `--skip-rust`, but official release evidence should keep Rust and `--require-official-claim-ready` enabled.
