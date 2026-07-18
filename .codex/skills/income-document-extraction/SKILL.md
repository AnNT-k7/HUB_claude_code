---
name: income-document-extraction
description: Implement or review document classification, OCR/parsing, normalized income facts, missing-document detection, and source evidence for unsecured-loan income verification. Use for application forms, employment contracts and appendices, payslips, salary confirmations, bank statements, document schemas, extraction prompts, parsers, and evidence viewers.
---

# Income Document Extraction

Extract case-scoped facts with reproducible evidence. Do not determine eligible income or make a credit conclusion.

## Required context

Read:

1. `docs/PRD.md` sections 4–6.
2. `docs/PROJECT-RULES.md` sections 3, 5, and 7.
3. `docs/ARCHITECTURE.md` sections 3.4 and 6.
4. `docs/WORKFLOW.md` sections 4.2 and 4.3.

## Contract

Support only approved MVP document types:

- loan application/income declaration;
- employment contract and salary appendix;
- payslip or salary confirmation;
- bank statement.

For every extracted fact, retain:

- `case_id` and source document ID;
- fact type and normalized value;
- period and currency when applicable;
- page plus row/bounding box/section;
- `evidence_id` and source checksum;
- parse/extraction status and technical confidence.

Technical confidence measures extraction quality only; never treat it as credit risk or approval probability.

## Rules

- Validate file type, size, checksum, readability, and case ownership before extraction.
- Separate raw evidence spans from normalized structured facts.
- Preserve original text/value alongside normalization when needed for review.
- Never invent an employer, period, amount, currency, transaction source, or missing page.
- Return `MISSING_DOCUMENTS`, unreadable, or manual-review status with a specific reason.
- Do not embed customer documents or PII in the global policy index.
- Do not conclude whether income is eligible; hand facts to Income and Policy components.

## Testing

Cover:

- each supported document type;
- Vietnamese names, dates, amounts, and currency formats;
- multi-page and scanned documents;
- duplicate files/checksums;
- missing pages, unreadable text, low confidence, and unsupported formats;
- evidence pointers opening the correct source location;
- strict `case_id` isolation;
- schema validation without live LLM calls.
