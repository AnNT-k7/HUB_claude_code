# RAG policy

Live retrieval dùng `NamespacePolicyRetriever` trên `three_rag_fpt_corpus.json`:

- namespace `POLICY`;
- domain `INCOME_VERIFICATION`;
- product `UNSECURED_PERSONAL_LOAN`;
- chunk type `POLICY_RULE`;
- approval/effective/expiry filter;
- query embedding `FPT Vietnamese_Embedding`, đúng 512 dimensions như corpus.

Không có key thì runtime ghi `LEXICAL_RAG_FALLBACK`; đây là mock-mode rõ ràng, không được trình bày như vector retrieval. Policy synthetic demo gồm IVP-1..IVP-6 và citation document/page/section/effective date/quote/chunk ID. Nó không phải policy ngân hàng thật.
