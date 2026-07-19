# Data model

SQLite/PostgreSQL-compatible tables:

- `income_cases`: case/application/customer metadata, pipeline status và serialized typed checkpoint.
- `income_documents`: case-scoped file metadata, checksum, page count và processing error.
- `extracted_fields`: normalized fact, method, confidence và evidence link.
- `agent_runs`, `agent_results`: structured execution trace và result payload.
- `evidence`: document/page/quote/location/checksum/method/confidence.
- `income_policies`: structured policy metadata (policy data only, no PII).
- `final_reports`: latest reviewable report.
- `income_audit_logs`: append-only workflow/tool/review/action events.

Source bytes live under `backend/data/case_documents/{case_id}` in local mode. Global policy embeddings never contain customer documents or PII.
