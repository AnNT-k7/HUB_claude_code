---
name: income-policy-rag
description: Implement or review policy ingestion, chunking, embeddings, scoped pgvector retrieval, effective-date filtering, and exact citations for income verification. Use for RAG services, policy metadata, POLICY_RULE or VERIFICATION_PROCEDURE chunks, Policy Agent prompts/contracts, corpus quality, retrieval benchmarks, and policy-not-found or conflict handling.
---

# Income Policy RAG

Retrieve approved income-verification policy with exact citations. Never use RAG as a customer-data store or a substitute for deterministic calculations.

## Required context

Read `docs/RAG-ARCHITECTURE.md` completely, then the relevant sections of `docs/PROJECT-RULES.md` and `docs/ARCHITECTURE.md`.

## Indexing contract

The global policy index may contain only approved:

- `POLICY_RULE` chunks;
- `VERIFICATION_PROCEDURE` chunks.

Require metadata for domain, product, chunk type, document/version, page, section, effective/expiry date, approval status, checksum, and source path. Quarantine incomplete, conflicting, external-unapproved, or unknown-source content.

Use the configured FPT `Vietnamese_Embedding` model with 1024 dimensions for both indexing and runtime retrieval. Mock embeddings are test-only.

## Query contract

Every runtime query must filter:

- `domain=INCOME_VERIFICATION`;
- `product=UNSECURED_PERSONAL_LOAN`;
- allowed chunk types;
- `approval_status=APPROVED`;
- effective/expiry date for the case time.

Do not relax filters when retrieval is empty. Return `POLICY_NOT_FOUND`. Return manual review with all citations when applicable policies conflict.

## Citation contract

Require document name, page number, section ID, effective date, exact quote, and chunk ID. Ensure the UI can resolve the citation to the authorized source.

## Data isolation

- Keep loan applications, contracts, payslips, statements, PII, and agent outputs out of `policy_embeddings`.
- Store customer evidence case-scoped and require `case_id` authorization for retrieval.
- Do not embed derived income metrics as source facts.

## Policy Agent rules

- Use only retrieved, in-scope, effective policy evidence.
- Never invent a threshold, exception, required document, or consequence.
- Never perform arithmetic or modify case facts.
- Never conclude loan approval/rejection.
- Emit structured policy results, citations, and explicit not-found/conflict statuses.

## Testing

Cover metadata validation, quarantine, idempotent checksum upsert, mandatory filters, expired policies, empty retrieval, conflicts, citation completeness, embedding dimension mismatch, case isolation, and retrieval benchmarks.
