"""Tests for the three concrete income-verification agents."""

from __future__ import annotations

import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agents.income_verification import (  # noqa: E402
    CaseContext,
    ComponentStatus,
    IncomeAnalysisAgent,
    IncomeVerificationOrchestrator,
    MarkdownDocumentAgent,
    PolicyAgent,
    WorkflowDependencies,
    WorkflowState,
)
from app.services.namespace_rag import NamespaceHit, RagNamespace  # noqa: E402


DOCUMENT_FIXTURE = (
    PROJECT_ROOT
    / "dataset"
    / "document_extraction_agent"
    / "synthetic_income_verification_documents_case_001.md"
)
CORPUS_FIXTURE = BACKEND_ROOT / "data" / "rag" / "three_rag_fpt_corpus.json"


class FilePolicyRetriever:
    """Read already-embedded fixture metadata without making a network call."""

    async def retrieve(self, _query):
        corpus = json.loads(CORPUS_FIXTURE.read_text(encoding="utf-8"))
        hits = []
        for chunk in corpus["namespaces"]["POLICY"]["chunks"]:
            metadata = chunk["metadata"]
            if metadata["chunk_type"] != "POLICY_RULE":
                continue
            hits.append(
                NamespaceHit(
                    chunk_id=chunk["chunk_id"],
                    namespace=RagNamespace.POLICY,
                    score=1.0,
                    content=chunk["content_chunk"],
                    document_name=metadata["document_name"],
                    page_number=metadata["page_number"],
                    section_id=metadata["section_id"],
                    source_path=metadata["source_path"],
                    chunk_type=metadata["chunk_type"],
                    indexing_scope=metadata["indexing_scope"],
                    effective_date=metadata.get("effective_date"),
                    approval_status=metadata.get("approval_status"),
                )
            )
        return hits


def make_context() -> CaseContext:
    return CaseContext(
        case_id="SYN-IV-001",
        application_id="SYN-SHB-2026-0001",
    )


class ConcreteAgentTests(unittest.IsolatedAsyncioTestCase):
    async def _extracted_context(self) -> tuple[CaseContext, MarkdownDocumentAgent]:
        context = make_context()
        agent = MarkdownDocumentAgent(DOCUMENT_FIXTURE)
        context.documents = await agent.fetch_documents(context)
        result = await agent(context)
        self.assertEqual(result.status, ComponentStatus.SUCCESS)
        context.extracted_fields = result.extracted_fields
        context.evidence = result.evidence
        return context, agent

    async def test_document_agent_extracts_case_scoped_evidence(self):
        context, _ = await self._extracted_context()

        self.assertEqual(len(context.documents), 4)
        self.assertEqual(len(context.evidence), 13)
        self.assertEqual(len(context.extracted_fields.salary_transactions), 8)
        self.assertEqual(context.extracted_fields.contract_salary, Decimal("22000000"))
        self.assertIn(
            "SALARY_ADJUSTMENT_APPENDIX",
            context.extracted_fields.missing_documents,
        )

    async def test_income_agent_excludes_non_salary_and_detects_anomaly(self):
        context, _ = await self._extracted_context()

        result = await IncomeAnalysisAgent()(context)

        self.assertEqual(result.status, ComponentStatus.SUCCESS)
        self.assertEqual(result.average_income, Decimal("23833000"))
        self.assertEqual(result.period_count, 6)
        self.assertEqual(len(result.recognized_evidence_ids), 6)
        self.assertEqual(len(result.excluded_evidence_reasons), 2)
        self.assertEqual(result.anomalies[0].month, "2026-05")
        self.assertEqual(result.anomalies[0].deviation_ratio, Decimal("-0.2786"))

    async def test_policy_agent_returns_complete_exact_citations(self):
        context, _ = await self._extracted_context()

        result = await PolicyAgent(FilePolicyRetriever())(context)

        self.assertEqual(result.status, ComponentStatus.SUCCESS)
        self.assertEqual(result.eligible_income, Decimal("22000000"))
        self.assertEqual(result.required_statement_months, 6)
        self.assertEqual(len(result.citations), 6)
        self.assertEqual(
            {citation.section_id for citation in result.citations},
            {f"IVP-{number}" for number in range(1, 7)},
        )
        self.assertTrue(all("<!--" not in item.quote for item in result.citations))

    async def test_three_agents_run_through_orchestrator(self):
        document_agent = MarkdownDocumentAgent(DOCUMENT_FIXTURE)
        dependencies = WorkflowDependencies(
            fetch_documents=document_agent.fetch_documents,
            extract_documents=document_agent,
            analyze_income=IncomeAnalysisAgent(),
            retrieve_policy=PolicyAgent(FilePolicyRetriever()),
        )

        result = await IncomeVerificationOrchestrator(dependencies).run(make_context())

        self.assertEqual(result.workflow_state, WorkflowState.HUMAN_REVIEW)
        self.assertEqual(result.income_analysis.average_income, Decimal("23833000"))
        self.assertEqual(result.policy_result.eligible_income, Decimal("22000000"))
        self.assertEqual(len(result.recommendation.policy_citations), 6)
        self.assertEqual(result.execution_results, [])


if __name__ == "__main__":
    unittest.main()
