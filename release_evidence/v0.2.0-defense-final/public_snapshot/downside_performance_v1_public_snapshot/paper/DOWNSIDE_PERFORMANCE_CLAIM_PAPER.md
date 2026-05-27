# Downside Performance Harness v0.1

## Scoped Claim

> SOTA-grade downside-adjusted hypothetical backtested performance under the included deterministic `downside_performance_v1` benchmark suite.

This paper documents a scoped, deterministic, hypothetical backtest result. It does not claim live trading readiness, future returns, realized investor performance, broker integration, or universal market dominance.

## Headline Result

| Metric | agentic_candidate_v1 |
| --- | ---: |
| Return multiple | 1.872x |
| Total return | 87.25% |
| CAGR | 23.29% |
| Max drawdown | 0.79% |
| Calmar ratio | 29.49 |
| Sharpe ratio | 14.44 |
| Claim gate | `passed`, `performance_claim_publishable=True` |

## Baseline Comparison

| Rank | Strategy | Total Return | CAGR | Max DD | Calmar | Sharpe |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | `agentic_candidate_v1` | 87.25% | 23.29% | 0.79% | 29.49 | 14.44 |
| 2 | `simple_momentum` | 78.09% | 21.24% | 1.81% | 11.72 | 13.69 |
| 3 | `stock_harness_ma_cash` | 60.78% | 17.17% | 0.65% | 26.42 | 14.53 |
| 4 | `volatility_targeting` | 27.79% | 8.53% | 12.83% | 0.66 | 2.80 |
| 5 | `equal_weight` | 9.90% | 3.20% | 16.40% | 0.20 | 1.10 |
| 6 | `mean_reversion` | 6.27% | 2.05% | 10.88% | 0.19 | 0.69 |
| 7 | `cash` | 0.00% | 0.00% | 0.00% | 0.00 | 0.00 |
| 8 | `buy_and_hold_spy` | -6.87% | -2.35% | 30.69% | -0.08 | -0.42 |
| 9 | `sma_crossover` | -12.11% | -4.22% | 22.75% | -0.19 | -0.83 |

![Equity curve](C:\CARLA demo\reports\downside_performance_visuals\equity_curve_comparison.png)

![Drawdown curve](C:\CARLA demo\reports\downside_performance_visuals\drawdown_curve_comparison.png)

![Baseline total return](C:\CARLA demo\reports\downside_performance_visuals\baseline_total_return.png)

![Risk-adjusted ranking](C:\CARLA demo\reports\downside_performance_visuals\risk_adjusted_ranking.png)

![Cost stress](C:\CARLA demo\reports\downside_performance_visuals\cost_slippage_stress.png)

## Robustness and Claim Boundary

The benchmark includes data-quality gates, lookahead audit, walk-forward validation, cost/slippage stress, parameter sensitivity, and negative controls for lookahead leakage and overfit traps.

## Defense Layer v0.2

The public snapshot also includes a defense packet for reviewer-facing attack surfaces: strategy freeze, data lineage and bias disclosure, baseline fairness, deterministic bootstrap confidence intervals, and a forward paper-trading protocol. This defense layer does not expand the claim beyond hypothetical backtested performance under the included benchmark.

| Defense check | Passed |
| --- | ---: |
| Strategy freeze | `True` |
| Data lineage / bias | `True` |
| Baseline fairness | `True` |
| Bootstrap confidence | `True` |
| Forward paper-trading protocol | `True` |
| Claim boundary preserved | `True` |
| Defense gate | `passed`, `defense_claim_defensible=True` |

| Bootstrap metric | p05 / median / p95 |
| --- | ---: |
| CAGR | 16.85% / 23.34% / 29.61% |
| Max drawdown | 0.45% / 0.76% / 0.93% |
| Calmar ratio | 20.54 / 32.11 / 57.13 |
| Sharpe ratio | 11.49 / 14.60 / 18.64 |

Forward paper-trading protocol starts on `2026-05-27` with checkpoints `2026-06-26`, `2026-08-25`, `2026-11-23`. These checkpoints are for future evidence collection only and are not live-performance claims.

Non-claims preserved by the claim contract:

- No financial advice.
- No live trading readiness claim.
- No return guarantee or future performance claim.
- No realized investor return claim.
- No broker integration, order routing, or execution-readiness claim.
- No universal market, strategy, or external-framework dominance claim.
- No claim outside the included downside_performance_v1 benchmark suite.

Evidence files are generated under `dist/downside_performance_v1_evidence` and the public snapshot under `dist/downside_performance_v1_public_snapshot`.
