# 처음 보는 사람을 위한 안내서

이 문서는 Downside-Aware Stock Harness를 처음 보는 사람이 빠르게 맥락을 잡기 위한 한국어 안내서입니다.

## 한 문장 요약

이 프로젝트는 주식 매매 프로그램이 아닙니다. 주식 백테스트가 스스로를 속이고 있지 않은지 검증하는 로컬 연구 인프라입니다.

조금 더 정확히 말하면:

> 포함된 `downside_verification_v1` benchmark suite 기준에서, 로컬/no-dependency/downside-aware 주식 백테스트 검증 coverage에 대해 SOTA-grade로 벤치마크된 인프라입니다.

## 무엇을 검증하나

일반적인 백테스트는 수익률이 좋아 보이면 그럴듯해 보입니다. 하지만 실제로는 다음 문제 때문에 결과가 쉽게 망가질 수 있습니다.

- 미래 데이터를 몰래 보는 lookahead leakage
- 비어 있는 날짜, 중복 날짜, 이상한 OHLCV 값, 잘못된 거래량
- 조정주가와 원시 가격의 불일치
- 수수료, 슬리피지, 갭, 체결 지연을 무시한 결과
- 특정 파라미터에서만 좋아 보이는 overfit
- 상승장에서는 좋아 보이지만 하락장에서 무너지는 전략
- 외부 엔진과 연결했을 때 equity, trade, fill, order intent가 미묘하게 달라지는 parity drift

이 harness는 이런 실패 지점을 먼저 검사합니다. 목적은 돈을 버는 전략 추천이 아니라, 믿기 어려운 백테스트를 걸러내는 것입니다.

## 무엇이 아닌가

이 프로젝트는 다음을 하지 않습니다.

- 금융 조언
- 투자 추천
- 미래 수익률 예측
- 알파 생성 claim
- 실거래 주문 라우팅
- 브로커 연동
- 세금, 법률, 투자 적합성 판단
- 모든 외부 백테스팅 프레임워크에 대한 보편적 우월성 주장

따라서 이 프로젝트의 SOTA claim은 투자 성과 SOTA가 아닙니다.

## 현재 공식 claim

현재 방어 가능한 claim은 아래처럼 좁게 정의되어 있습니다.

> SOTA-grade deterministic verification coverage for local, no-dependency, downside-aware stock backtest research on the included `downside_verification_v1` benchmark suite.

한국어로 쓰면:

> 포함된 `downside_verification_v1` benchmark suite 기준에서, 로컬/no-dependency/downside-aware 주식 백테스트 검증 coverage에 대해 SOTA-grade로 벤치마크된 인프라입니다.

이 claim은 다음 근거로 지지됩니다.

- Python reference core 테스트 통과
- deterministic benchmark 통과
- claim evidence CLI 통과
- clean release bundle manifest 생성 및 scope assertion 통과
- Rust v0 core 테스트 통과
- README, CLAIMS, BENCHMARK, LIMITATIONS, THREAT_MODEL, RELEASE_GATE, technical report 정리

## 빠르게 검증하는 방법

공식 release gate:

```bash
cd "<repo-root>"
python3 ops/run_stock_harness_release_gate.py --pretty --output reports/stock_harness_release_gate_latest.json
```

로컬에 Cargo가 없는 개발 환경에서는 Python-only gate를 먼저 돌릴 수 있습니다.

```bash
cd "<repo-root>"
python3 ops/run_stock_harness_release_gate.py --pretty --skip-rust --output reports/stock_harness_release_gate_python_only.json
```

개별 Python evidence layer를 따로 확인하려면 아래 명령을 사용할 수 있습니다.

```bash
cd "<repo-root>"
python3 -m unittest tests/test_stock_harness.py
python3 ops/benchmark_stock_harness.py --pretty
python3 ops/compare_stock_harness_baselines.py --pretty
```

Rust v0 gate:

```bash
cd "<repo-root>"
cargo test --manifest-path rust_stock_harness/Cargo.toml
cargo run --manifest-path rust_stock_harness/Cargo.toml --bin stock-harness-benchmark -- --pretty
```

기대 결과:

- official publication gate: `official_claim_publishable: true` on a Python + Cargo host
- official claim packet: `dist/stock_harness_official_claim_packet` verifier `status: passed`
- release gate: `official_claim_ready: true` on a Python + Cargo host
- Python-only local gate: `python_gate_passed: true`, `official_claim_ready: false`
- benchmark: `all_passed: true`
- claim evidence: `supported_for_included_benchmark_suite`
- release bundle assertions: `release_bundle_passed: true`, `release_bundle_scope_enforced: true`
- Rust tests: OK
- Rust benchmark: `all_passed: true`

## 파일을 읽는 순서

1. `docs/FIRST_TIME_READER_GUIDE_KO.md`
2. `README.md`
3. `docs/CLAIMS.md`
4. `docs/BENCHMARK.md`
5. `docs/RELEASE_GATE.md`
6. `docs/LIMITATIONS.md`
7. `paper/SOTA_CLAIM_TECHNICAL_REPORT.md`
8. `angelos_os/stock_harness.py`
9. `tests/test_stock_harness.py`

## 가장 중요한 주의점

이 프로젝트는 peer-reviewed novelty, 투자 성과, 실거래 가능성, 외부 프레임워크 전체에 대한 우월성을 주장하지 않습니다. 강한 표현은 반드시 포함된 `downside_verification_v1` benchmark suite와 검증 coverage 범위 안에서만 사용해야 합니다.
