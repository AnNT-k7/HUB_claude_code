# Agent contracts

- Document Agent → `DocumentExtractionResult`: status, `ExtractedFields`, evidence, reason code.
- Income Agent → `IncomeAnalysisResult`: recognized/excluded evidence, periods, currency, average/variation, anomalies, formula version.
- Policy Agent → `PolicyResult`: status, eligible income calculated by tool, required docs/months, retrieved chunk IDs, exact citations, optional FPT explanation.
- Consistency Agent → `Finding[]`: stable code/severity/source values/evidence/rule version.
- Recommendation Builder → `Recommendation`: review status, metrics, findings, missing docs, citations, unresolved issues.
- Verification Critic → Pydantic `CriticOutput`; narrative only.

Mọi component trả structured schema. Technical retry có giới hạn; missing evidence/policy là business path, không retry để ép kết quả.
