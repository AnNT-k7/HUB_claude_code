# RAG & policy corpus

> See also `docs/RAG-ARCHITECTURE.md` (pre-existing) for the original target
> design. This file describes what's actually indexed and queried today.

## Corpus triage (per the "phân loại tài liệu" requirement)

`dataset/` contains two categories of material:

1. **Directly relevant, actually used**: `dataset/Policy_agent/synthetic_income_verification_policy_v1.md`
   — the only file the live `PolicyAgent` can ever cite. Front-matter marks
   it `issuer: SYNTHETIC_SHB_DEMO`, `approval_status: APPROVED_FOR_DEMO`,
   `production_use: prohibited` — it is a project-authored synthetic policy
   for demo/dev use, **not real SHB policy**, and the corpus/UI must not
   imply otherwise.
2. **Indirectly relevant, ingested but excluded from retrieval by design**:
   `dataset/Policy_agent/policy_agent_shb_web_government_sources_notes.md`
   and `dataset/Income_analysis_agent/shb_government_web_sources_income_analysis_notes.md`
   — real research notes citing actual Vietnamese banking law, tagged
   `approval_status: PENDING_REVIEW`. `PolicyAgent.config.accepted_approval_statuses = ("APPROVED", "APPROVED_FOR_DEMO")`
   excludes `PENDING_REVIEW` by construction — this content sits in the
   corpus JSON (for future domain-owner review) but is never returned to a
   query.
3. **Not relevant to this task / not ingested**: every real SHB PDF under
   `dataset/Policy_agent/`, `dataset/document_extraction_agent/`,
   `dataset/Income_analysis_agent/` (terms & conditions, fee schedules,
   collateral seizure notices, etc.) — `backend/scripts/ingest_three_rag_namespaces.py`
   only globs `*.md`, so these are structurally excluded, not filtered out
   after the fact. This is intentional: using real bank collateral/terms
   documents as filler to make the corpus "look bigger" would misrepresent
   what the system's policy grounding actually is.
4. **Duplicates**: none currently in the ingested set (each `.md` source
   maps to exactly one corpus entry per namespace).
5. **Scanned/unextracted**: none of the ingested `.md` sources are scans;
   the excluded real PDFs were never OCR'd for this purpose (out of scope,
   see `README.md`'s limitations table).

## The policy corpus: 15 rule groups (IVP-1…IVP-15)

All in one file, `dataset/Policy_agent/synthetic_income_verification_policy_v1.md`,
each a `## IVP-N — <title>` section with `Section ID`, `Chunk type`
(`POLICY_RULE` or `VERIFICATION_PROCEDURE`), condition/threshold/exception/
action, and a `**Trích dẫn thử nghiệm:**` (test citation) quote used as the
`PolicyCitation.quote`:

| Rule | Covers |
| --- | --- |
| IVP-1 | Required statement months (6 consecutive) |
| IVP-2 | Salary-transaction identification criteria |
| IVP-3 | Eligible-income formula (min of average salary vs. contract+capped variable income) |
| IVP-4 | Anomalous-month detection threshold (>20% drop) |
| IVP-5 | Minimum remaining contract term (**not yet code-enforced**, see below) |
| IVP-6 | Declared-vs-contract-salary mismatch documentation requirement |
| IVP-7 | Minimum employment duration (3 months at current employer) |
| IVP-8 | Declared-vs-statement-average mismatch (**this one is enforced** — `DECLARED_VS_AVERAGE_MISMATCH`) |
| IVP-9 | Employer-name verification / token-overlap acceptance criteria |
| IVP-10 | Multiple income sources — primary only counts toward eligible income (**not yet code-enforced**) |
| IVP-11 | Cash salary — requires an income confirmation letter |
| IVP-12 | Foreign-currency salary — no auto-conversion, forces manual review |
| IVP-13 | Required document set per product |
| IVP-14 | Extraction-confidence threshold (<0.90 → manual review; **threshold exists as policy text, gate not wired in**) |
| IVP-15 | Consolidated manual-review trigger list (procedure, references IVP-4/9/12/13/14) |

`PolicyAgent.config.required_rule_ids` (the hard-gated set — missing any of
these returns `POLICY_NOT_FOUND`) is still just `IVP-1..IVP-6`, matching the
original scope. IVP-7 through IVP-15 exist in the corpus for retrieval and
citation richness but are not required for a case to reach `SUCCESS`
— expanding `required_rule_ids` further was deliberately not done in this
pass, since several of the newer rules (IVP-5, IVP-10, IVP-14) don't have a
corresponding enforcement check in `consistency_rules.py` yet (see
`docs/data-model.md`), and hard-requiring citation of a rule the code can't
actually act on would be misleading, not more correct.

## Retrieval: real, with an explicit degraded fallback

`app/services/namespace_rag.py::search_namespace()` embeds the query text
via the configured provider (FPT `Vietnamese_Embedding`, 512-dim — same
provider/model as indexing, required to match: see
`REQUIRED_DIMENSIONS = 512` and the `EMBEDDING_DIMENSIONS` check) and ranks
corpus chunks by cosine similarity, filtered first by
`domain`/`product`/`chunk_type`/`indexing_scope`/`approval_status`/
`effective_date` (query never bypasses these filters — `NamespaceQuery` has
no "search everything" mode).

`top_k` was raised from the original `10` (hard Pydantic `le=10`) to `30`
(`le=30`) and `PolicyAgent`'s query now asks for `top_k=20`, specifically
because expanding the corpus to 13 `POLICY_RULE`-typed chunks (IVP-1..12,
14) made it possible for cosine-similarity ranking noise to push one of the
6 *required* rules out of a `top_k=10` result set — this was caught by a
real regression (`POLICY_RULES_NOT_FOUND:IVP-5` appearing after the corpus
expansion) and fixed by widening the retrieval window, not by hand-picking
which rules would rank well.

If no embedding provider key is configured, both runtimes fall back to
`EmbeddedDemoPolicyRetriever` — pure in-memory metadata filtering with a
hardcoded `score=1.0` — and label the case's `rag_mode` as
`DEGRADED_KEYWORD_MATCH` (visible via `GET /cases/system/status` and the
frontend's mode badge), never silently.

## Rebuilding the corpus

```bash
cd backend
python3 scripts/ingest_three_rag_namespaces.py --embed --provider fpt \
  --output data/rag/three_rag_fpt_corpus.json
```

Requires `FPT_API_KEY` and `EMBEDDING_DIMENSIONS=512` in `.env` (the
committed corpus already has this run's output baked in — re-run only after
editing the source policy markdown).
