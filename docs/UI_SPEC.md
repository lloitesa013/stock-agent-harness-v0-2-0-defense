# UI Spec

The first UI is a Streamlit evidence viewer. It reads the existing `release_evidence/v0.2.0-defense-final` packet and does not run backtests, mutate files, or regenerate claims.

## Main Dashboard

Purpose: give an executive-level answer to "is this claim defensible?"

Cards:

- Claim Status: PASS / FAIL / PENDING.
- Strategy Freeze: Verified / Pending.
- Data Integrity: Passed / Pending.
- Overfitting Risk: Low / Medium / High / Pending.
- Cost Stress: Passed / Pending.
- Forward Validation: Started / Pending.

## Claim Registry

Purpose: show what is being claimed and what is explicitly not claimed.

Fields:

- claim_id
- benchmark_suite
- claim_limit
- performance_type
- required evidence
- non-claims

## Strategy Freeze

Purpose: show whether the candidate was fixed before evaluation.

Fields:

- strategy_id
- freeze statement
- candidate_config_fingerprint
- strategy_registry_fingerprint
- train / validation / test partitions
- rejected or adversarial controls

## Performance & Risk

Purpose: show metrics without implying live performance.

Fields:

- total return
- CAGR
- max drawdown
- Sharpe
- Sortino
- Calmar
- volatility
- worst month
- worst year
- turnover

## Overfitting Audit

Purpose: show whether the result survived adversarial checks.

Fields:

- walk-forward status
- bootstrap confidence interval status
- parameter sensitivity status
- negative controls
- random baseline status
- data-bias defense status
- baseline fairness status

## Evidence Packet Export

Purpose: show what artifacts are sealed and where to find them.

Artifacts:

- PDF paper
- JSON evidence
- Markdown summaries
- public snapshot
- release manifest
- official claim packet

The UI may link to local files when run locally, but it must not rewrite those files.

