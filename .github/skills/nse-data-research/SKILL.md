---
name: nse-data-research
description: Use when researching or integrating market, company, or financial data for this NSE terminal; preserve source provenance, point-in-time correctness, and conservative promotion rules.
---

# NSE Data Research and Integration

Use this skill when evaluating a new data export, public web source, financial metric, or proposed research-agent integration for the NSE system.

## Operating rules

- Prefer official exchange filings and exchange-published data for authoritative, dated facts. Treat broker exports, screeners, Yahoo Finance, and other aggregators as secondary sources unless a specific, documented use case says otherwise.
- Keep each source's raw observation and provenance auditable: source name, original symbol/name, retrieval time, observation or snapshot date, source URL or file, and relevant quality flags. Preserve raw input when normalizing it.
- Distinguish the export/retrieval date from the underlying financial period end and the first public filing/availability time. A value without the required dates is not point-in-time historical data and must not enter historical replay or backtests as though it were.
- Resolve securities using authoritative identifiers such as exchange symbol and ISIN where available. Use curated aliases only when unambiguous; do not guess fuzzy name-to-symbol matches. Keep unresolved rows available for review.
- Normalize units, currencies, date/time zones, and field definitions explicitly before comparison. Check missing values, sentinels, impossible ranges, duplicates, and source-wide suspicious patterns. Retain suspect raw values but exclude them from structured use with a visible reason.
- Keep imported snapshots research-only by default. Do not silently overwrite live fundamentals, prices, universe membership, signals, or backtests.
- Promote data only through an explicit, documented rule appropriate to each field. Record both source values, the rule and result, the prior/current value, and the action. Accept corroborated fields individually; withhold disagreements instead of choosing a whole source or row. Do not reuse the KITE/ScanX 1% comparison rule for other fields or sources without validating that tolerance.
- Before applying an import or reconciliation, preview its coverage and proposed changes, check idempotence, and make a database backup. After applying, verify counts, attestations, unchanged out-of-scope tables, service health, and focused tests.
- Make errors, incomplete coverage, and blocked sources visible. Never turn missing or unavailable data into a success-shaped default.

## Web collection and agent-assisted analysis

- Before adding a crawler or browser automation, check for an existing adapter in `data_sources/` and prefer official APIs or downloadable exchange data.
- Use crawling only for publicly accessible content that the user is authorized to collect and whose terms permit the intended use. Do not bypass authentication, access controls, rate limits, or anti-bot protections. Preserve page URL, retrieval timestamp, and the extracted passage's context.
- Crawlbase and Firecrawl are optional collection tools, not financial-data authorities. Check current service terms, costs, data retention, and credential handling before proposing their use; do not add a paid dependency or expose credentials without explicit approval.
- Multi-agent frameworks such as TradingAgents may be considered only as an optional explanatory research layer. Keep its hypotheses and recommendations visibly separate from observed data and deterministic system outputs. Existing quality gates, risk controls, and backtest rules remain authoritative; agent output must not place orders or bypass those controls.
- Do not import third-party skill instructions or scoring thresholds wholesale. Extract general ideas, verify them against Indian-market definitions and this repository's data model, and write original, source-attributed guidance.

## Suggested workflow

1. State the decision the data is intended to support and whether it is for display, research, live screening, or historical replay.
2. Identify the source's authority, license/terms, schema, coverage, date semantics, and known failure modes. Compare it with existing adapters and database tables.
3. Build a preview that reports row counts, duplicate counts, identifier-mapping coverage, field coverage, units, quality flags, and unresolved conflicts.
4. Keep raw snapshots separate from live tables until the acceptance rule is explicit and testable.
5. Add focused tests for valid input, malformed or suspicious input, duplicate imports, ambiguous identifiers, source disagreement, and the rule that unapproved data cannot affect live decisions.
6. Apply only after preview and backup. Report exactly which fields and rows changed, which were withheld, and which data-quality or date limitations remain.

## Reviewed references

These links informed the scope of this skill; their implementation details and trading rules are not copied:

- [Hermes optional stock skill](https://github.com/NousResearch/hermes-agent/blob/main/optional-skills/finance/stocks/SKILL.md) — example of read-only market research; not an authoritative NSE feed.
- [TradingAgents](https://github.com/TauricResearch/TradingAgents) — multi-agent research roles; potentially an optional explanatory layer.
- [Superpowers](https://github.com/obra/superpowers) — general coding-agent workflow, outside this skill's finance-data scope.
- [DevOpsAIguru123/claude-skills](https://github.com/DevOpsAIguru123/claude-skills) — stock-analysis example; its signal rules are not validated for this system.
- [himself65/finance-skills](https://github.com/himself65/finance-skills) — valuation and liquidity report structures to adapt only after NSE-specific validation.
- [VoltAgent Crawlbase entries](https://github.com/VoltAgent/awesome-agent-skills#skills-by-crawlbase-team) and [Firecrawl entries](https://github.com/VoltAgent/awesome-agent-skills#skills-by-firecrawl-team) — optional web-collection integrations, subject to the rules above.

The supplied Reddit link could not be retrieved in a verifiable form, so no claims or guidance from that thread are included.
