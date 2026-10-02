# Audit Remediation — Implementation and Validation

The audit remediation changes are integrated on `main`. They cover:

- Non-destructive, per-field fundamentals merges with source timestamps,
  import metadata, and explicit unknown-date quality flags.
- Separate ROE, ROCE, and ROIC mappings; ambiguous legacy `cfo_positive` and
  `roce` values are preserved and tagged `legacy_deprecated`.
- Fixed-risk sizing with validated entry/stop inputs and hard allocation/risk
  limits; uncalibrated win probability is not used for sizing.
- Price-derived ML feature parity, version checks, and purged time splits.
- Backtest cache fingerprinting, historical-field guards, gap/stop handling,
  and explicit right-censored outcomes.

## Verification

`python -m unittest discover -p 'test_*.py' -v` passed **31 tests** after
integrating the fundamentals provenance enhancements. Tests cover data
integrity, the legacy deprecation preview/apply path, sizing safety, ML
split/features, backtest behavior, and existing KITE/ScanX reconciliation.
The full suite passed locally and on the VM.

Schema additions are idempotent migrations. The local historical NIFTY CSV
has unknown provenance and was intentionally not staged, promoted, or deployed.
On the VM, 887 rows were tagged `legacy_deprecated` (860 candidate
`cfo_positive` fields and 878 candidate `roce` fields). The numeric values
were verified unchanged against a pre-tag backup.

## Legacy-value retirement gate

The owner chose to retain legacy values temporarily to avoid production
breakage, mark affected rows `legacy_deprecated`, and clear only the flagged
values after the DR-01 v2 dated-fundamentals backfill passes the financial
period/public-availability acceptance criteria. Keep the physical columns
until downstream compatibility is separately reviewed.

## Deployment state

The verified code was published to `main` and deployed to the VM. The API is
active and `/api/health` returned HTTP 200. The deployment check has one
separate data freshness failure: `universe_broad` is 34 days old. See
`EXECUTION_LOG.md` for the exact backup and deployment verification record.
