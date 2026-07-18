---
name: income-analysis
description: Implement or review salary-transaction classification, deterministic income calculations, stability and anomaly metrics, and cross-document consistency for Income Verification Expert. Use for income tools, calculation schemas, transaction rules, period/currency handling, consistency findings, and tests of average, variation, deviation, and rounding.
---

# Income Analysis

Produce reproducible income metrics from validated structured facts. Keep arithmetic and numeric routing out of LLM prompts.

## Required context

Read:

1. `docs/PRD.md` sections 5.3, 5.5, 6, and 10.
2. `docs/PROJECT-RULES.md` sections 3–5.
3. `docs/ARCHITECTURE.md` sections 3.5 and 3.7.
4. `docs/WORKFLOW.md` sections 4.4 and 4.5.

## Deterministic contract

Accept only validated facts with evidence IDs. For each derived metric, record:

- input fact IDs;
- included/excluded transactions and reason codes;
- period coverage and currency;
- formula and rounding rule;
- calculation/rule version;
- output value and status.

Use tested code for average income, variation, deviation, period coverage, and threshold comparisons.

## Rules

- Do not let an LLM add, divide, round, convert currency, or fill a missing period.
- Do not classify a transfer as salary without the approved evidence/rule inputs.
- Exclude internal transfers and unsupported income with explicit reason codes.
- Do not hard-code policy thresholds in prompts or agent modules; consume a cited policy/rule result.
- Reject mixed currencies or incompatible periods unless an approved deterministic conversion rule exists.
- Route missing inputs, empty periods, conflicts, and invalid denominators to incomplete/manual review.
- Keep findings traceable to facts, calculations, rule versions, and evidence.
- Do not calculate DSCR, D/E, LTV, credit score, or loan eligibility.

## Consistency checks

Compare only structured values:

- declared income versus recognized salary transactions;
- employer versus transaction source;
- contract salary versus actual receipts;
- identity, period, and currency across documents;
- required documents versus policy results.

LLMs may explain an already-computed finding but may not choose its numeric severity.

## Testing

Cover happy path and edge cases for:

- missing/duplicate months;
- zero or empty inputs;
- currency/period mismatch;
- irregular bonus and internal transfers;
- rounding boundaries and threshold equality;
- anomalous high/low periods;
- reproducibility from the same fact set;
- evidence and calculation-version traceability.
