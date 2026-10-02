---
name: nse-system-operations
description: Classify and safely execute one-time, per-source, per-import, scheduled, and event-driven NSE system work, including verification and deployment records.
---

# NSE System Operations

Use this skill when changing system operations, scheduling refreshes, integrating
sources, running reconciliations, reviewing readiness, or deciding whether work
is one-time or recurring.

## Classify the work before acting

- **One-time setup per environment:** schema migrations, service installation,
  initial universe load, first source-adapter wiring, and baseline strategy
  configuration. Make migrations idempotent and verify both local and deployed
  environments. Do not repeat setup commands as a substitute for incremental
  updates.
- **One-time per source integration:** document the source's authority, terms,
  fields, date semantics, mapping method, rate limits, failure modes, and
  promotion rules. A new source does not authorize wholesale replacement of
  existing data.
- **Repeat for every new artifact/snapshot:** follow
  `.github/skills/nse-data-research/SKILL.md`; it is the authoritative
  checklist for provenance, preview, mapping, idempotence, backup, promotion,
  and post-apply verification. Do not duplicate or weaken those gates here.
- **Per newly published filing or corporate event:** ingest only when relevant,
  preserve publication time and financial-period/event date separately, and
  update only fields supported by that filing. Do not treat retrieval time as
  point-in-time availability.
- **Scheduled work:** follow the cadence already configured and logged in the
  repository. Price/universe refreshes and weekly model retraining are separate
  jobs with separate freshness and model-quality checks; never assume one
  succeeded because another did.
- **Periodic readiness review:** repeat paper-league and real-money readiness
  checks only after their documented sample-size gates are met. A failed gate
  remains visible; do not relax thresholds to obtain a pass.
- **After every behavior-changing code or data operation:** run the narrowest
  relevant tests, verify health and data invariants, append an execution-log
  entry, and follow the owner's current Git/deployment instruction. A database
  row update does not by itself require an application restart; schema or
  runtime-code changes may.

## Apply the correct procedure

- For imports, source comparisons, and data promotion, follow
  `.github/skills/nse-data-research/SKILL.md` without creating a parallel
  checklist.
- For code changes, run the narrowest relevant tests, inspect the diff, record
  the outcome in `EXECUTION_LOG.md`, and follow the owner's current
  Git/deployment instruction. A database-only update does not automatically
  require an application restart; schema or runtime-code changes may.
- For scheduled jobs, inspect the actual configured schedule and last result
  before diagnosing freshness. Do not infer that one job succeeded because
  another did.
- For readiness reviews, retain the documented sample-size and pass/fail
  thresholds. A failed gate remains visible; do not relax it to obtain a pass.

## Guardrails

- A successful command is not evidence that the data is authoritative, fresh,
  point-in-time safe, or ready for live decisions.
- Keep snapshots and hypotheses separate from live system outputs until an
  explicit acceptance rule is satisfied.
- Do not repeat a completed destructive or additive operation without first
  proving its idempotence and scope.
- Do not clear or physically remove legacy fields until the documented
  replacement-data and downstream-compatibility gates pass.
- Never state that work was pushed, deployed, or verified unless each action
  was completed and its resulting state was checked.
