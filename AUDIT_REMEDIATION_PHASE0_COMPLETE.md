# Audit Remediation — Implementation and Validation

The audit remediation changes are integrated on `main`. They cover:

- Non-destructive, per-field fundamentals merges with source timestamps,
  import metadata, and explicit unknown-date quality flags.
- Separate ROE, ROCE, and ROIC mappings; legacy proxy rows are reported for
  review and are not rewritten automatically.
- Fixed-risk sizing with validated entry/stop inputs and hard allocation/risk
  limits; uncalibrated win probability is not used for sizing.
- Price-derived ML feature parity, version checks, and purged time splits.
- Backtest cache fingerprinting, historical-field guards, gap/stop handling,
  and explicit right-censored outcomes.

## Verification

`python -m unittest discover -p 'test_*.py' -v` passed **30 tests** after
integrating the fundamentals provenance enhancements. Tests cover data
integrity, sizing safety, ML split/features, backtest behavior, and existing
KITE/ScanX reconciliation. Python compilation checks also passed.

No live database import or legacy-row remediation was run as part of this
implementation. Schema additions are idempotent migrations. The local
historical NIFTY CSV has unknown provenance and was intentionally not staged,
promoted, or deployed.

## Deferred policy decision

`fundamentals_store.integrity_report()` identifies legacy values that may
contain FCF-derived CFO flags or TradingView ROIC stored as ROCE. These remain
untouched until the owner chooses whether to retain-and-attest, clear affected
values, or review them manually.

## Deployment state

This document records implementation and local tests only. Remote publication,
VM deployment, and service-health checks must be recorded separately after
they are verified.
