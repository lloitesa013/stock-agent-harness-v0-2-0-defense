# global_verification_v1

This benchmark suite is the upgrade path from the scoped `downside_verification_v1` claim to a defensible global verification-coverage claim.

It is intentionally stricter than the scoped benchmark:

- Named external frameworks must be directly executed by adapters.
- Package or engine versions must be fingerprinted.
- Profile-only or missing frameworks cannot support the global claim.
- The Stock Harness must retain full verification coverage and rank first by coverage score.
- The claim remains limited to deterministic verification coverage, not profitability, live trading, broker integration, speed, or universal performance.

A successful global claim requires every framework listed in `claim_contract.json` to have direct adapter evidence for the same benchmark suite.
