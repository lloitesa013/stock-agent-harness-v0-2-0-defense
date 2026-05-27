# agentic_verification_v1

This benchmark suite defines the scoped public claim for Stock Agent Harness.

The suite verifies deterministic multi-agent workflow coverage for downside-aware
stock backtest research. It does not evaluate live trading readiness, alpha,
investment performance, broker routing, or universal LLM trading dominance.

Official runs use `DeterministicAgentProvider` only. Optional LLM providers are
extension points and are excluded from the official claim gate.

The required workflow executes six roles:

- DataSentinel
- ResearchAnalyst
- StrategySynthesizer
- RiskSkeptic
- ExecutionAuditor
- VerificationChair

The final agentic verdict is subordinate to Stock Harness verification artifacts:
data quality, backtest, lookahead audit, walk-forward validation, regime stress,
parameter sweep, cost stress, and execution stress matrix.
