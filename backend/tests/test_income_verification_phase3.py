"""Phase 3 tests with injected fakes; no external model or document service is used."""

from __future__ import annotations

import asyncio
import sys
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agents.income_verification import (  # noqa: E402
    ActionPermission,
    CaseContext,
    ComponentStatus,
    ConcurrentStateError,
    DocumentExtractionResult,
    DocumentRecord,
    EvidenceCitation,
    ExtractedFields,
    IncomeAnalysisResult,
    IncomeVerificationOrchestrator,
    InMemoryCheckpointStore,
    PolicyCitation,
    PolicyResult,
    SalaryTransaction,
    WorkflowConfig,
    WorkflowDependencies,
    WorkflowState,
)
from app.agents.income_verification.state import InvalidStateTransition  # noqa: E402


def make_context(case_id: str = "case-001") -> CaseContext:
    return CaseContext(case_id=case_id, application_id="application-001")


def make_documents() -> list[DocumentRecord]:
    return [
        DocumentRecord(
            document_id="document-001",
            document_name="bank-statement.pdf",
            document_type="BANK_STATEMENT",
            checksum="sha256:statement",
        ),
        DocumentRecord(
            document_id="document-002",
            document_name="employment-contract.pdf",
            document_type="EMPLOYMENT_CONTRACT",
            checksum="sha256:contract",
        ),
    ]


def make_extraction() -> DocumentExtractionResult:
    evidence = [
        EvidenceCitation(
            evidence_id=f"salary-{month}",
            document_id="document-001",
            document_name="bank-statement.pdf",
            page_number=month,
            quote="Salary credit from ACME VIETNAM",
            source_checksum="sha256:statement",
        )
        for month in range(1, 4)
    ]
    transactions = [
        SalaryTransaction(
            month=f"2026-0{month}",
            amount=Decimal("10000000"),
            currency="VND",
            source="ACME VIETNAM",
            evidence_id=f"salary-{month}",
        )
        for month in range(1, 4)
    ]
    return DocumentExtractionResult(
        status=ComponentStatus.SUCCESS,
        extracted_fields=ExtractedFields(
            customer_name="Nguyen Van A",
            declared_income=Decimal("10000000"),
            contract_salary=Decimal("10000000"),
            currency="VND",
            employer="ACME VIETNAM",
            salary_transactions=transactions,
            extraction_confidence=0.98,
        ),
        evidence=evidence,
    )


def make_income(average: str = "10000000") -> IncomeAnalysisResult:
    return IncomeAnalysisResult(
        status=ComponentStatus.SUCCESS,
        average_income=Decimal(average),
        variation_ratio=Decimal("0"),
        period_count=3,
        currency="VND",
        recognized_evidence_ids=["salary-1", "salary-2", "salary-3"],
        calculation_version="income-calculator-v1",
        input_fact_ids=["salary-1", "salary-2", "salary-3"],
    )


def make_policy(
    *, status: ComponentStatus = ComponentStatus.SUCCESS
) -> PolicyResult:
    citations = []
    eligible_income = None
    currency = None
    if status is ComponentStatus.SUCCESS:
        citations = [
            PolicyCitation(
                document_name="unsecured-income-policy.pdf",
                page_number=12,
                section_id="4.2",
                effective_date=date(2026, 1, 1),
                quote="Use recognized salary credits from at least three months.",
                chunk_id="policy-chunk-4.2",
            )
        ]
        eligible_income = Decimal("9500000")
        currency = "VND"
    return PolicyResult(
        status=status,
        eligible_income=eligible_income,
        currency=currency,
        required_documents=["BANK_STATEMENT", "EMPLOYMENT_CONTRACT"],
        required_statement_months=3,
        applied_rule_ids=["income-rule-4.2"] if citations else [],
        citations=citations,
        reason_code="POLICY_NOT_FOUND" if status is ComponentStatus.NOT_FOUND else None,
    )


def make_dependencies(
    *,
    fetch=None,
    extract=None,
    income=None,
    policy=None,
) -> WorkflowDependencies:
    async def default_fetch(_context):
        return make_documents()

    async def default_extract(_context):
        return make_extraction()

    async def default_income(_context):
        return make_income()

    async def default_policy(_context):
        return make_policy()

    return WorkflowDependencies(
        fetch_documents=fetch or default_fetch,
        extract_documents=extract or default_extract,
        analyze_income=income or default_income,
        retrieve_policy=policy or default_policy,
    )


class IncomeVerificationPhase3Tests(unittest.IsolatedAsyncioTestCase):
    async def test_happy_path_stops_at_human_review(self):
        orchestrator = IncomeVerificationOrchestrator(make_dependencies())

        result = await orchestrator.run(make_context())

        self.assertEqual(result.workflow_state, WorkflowState.HUMAN_REVIEW)
        self.assertIsNotNone(result.recommendation)
        self.assertEqual(result.recommendation.status.value, "READY_FOR_REVIEW")
        self.assertEqual(result.recommendation.eligible_income, Decimal("9500000"))
        self.assertTrue(result.recommendation.policy_citations)
        self.assertTrue(result.proposed_actions)
        self.assertNotIn(
            ActionPermission.PROHIBITED,
            {action.permission for action in result.proposed_actions},
        )
        self.assertEqual(result.execution_results, [])

    async def test_income_and_policy_branches_run_concurrently(self):
        income_started = asyncio.Event()
        policy_started = asyncio.Event()

        async def income(_context):
            income_started.set()
            await asyncio.wait_for(policy_started.wait(), timeout=0.5)
            return make_income()

        async def policy(_context):
            policy_started.set()
            await asyncio.wait_for(income_started.wait(), timeout=0.5)
            return make_policy()

        orchestrator = IncomeVerificationOrchestrator(
            make_dependencies(income=income, policy=policy),
            config=WorkflowConfig(component_timeout_seconds=1),
        )

        result = await orchestrator.run(make_context("case-parallel"))

        self.assertEqual(result.workflow_state, WorkflowState.HUMAN_REVIEW)
        self.assertTrue(income_started.is_set())
        self.assertTrue(policy_started.is_set())

    async def test_missing_documents_routes_to_awaiting_documents(self):
        async def fetch(_context):
            return []

        orchestrator = IncomeVerificationOrchestrator(make_dependencies(fetch=fetch))

        result = await orchestrator.run(make_context("case-missing"))

        self.assertEqual(result.workflow_state, WorkflowState.AWAITING_DOCUMENTS)
        self.assertIsNone(result.extracted_fields)

    async def test_policy_not_found_routes_to_manual_review(self):
        async def policy(_context):
            return make_policy(status=ComponentStatus.NOT_FOUND)

        orchestrator = IncomeVerificationOrchestrator(make_dependencies(policy=policy))

        result = await orchestrator.run(make_context("case-policy-missing"))

        self.assertEqual(result.workflow_state, WorkflowState.MANUAL_REVIEW_REQUIRED)
        self.assertEqual(result.policy_result.status, ComponentStatus.NOT_FOUND)

    async def test_policy_without_citation_routes_to_manual_review(self):
        async def policy(_context):
            result = make_policy()
            result.citations = []
            return result

        orchestrator = IncomeVerificationOrchestrator(make_dependencies(policy=policy))

        result = await orchestrator.run(make_context("case-policy-no-citation"))

        self.assertEqual(result.workflow_state, WorkflowState.MANUAL_REVIEW_REQUIRED)
        self.assertIn("POLICY_CITATION_MISSING", {item.code for item in result.findings})

    async def test_critical_income_mismatch_routes_to_manual_review(self):
        async def income(_context):
            return make_income(average="4000000")

        orchestrator = IncomeVerificationOrchestrator(make_dependencies(income=income))

        result = await orchestrator.run(make_context("case-mismatch"))

        self.assertEqual(result.workflow_state, WorkflowState.MANUAL_REVIEW_REQUIRED)
        self.assertTrue(any(item.severity.value == "CRITICAL" for item in result.findings))
        self.assertIsNone(result.recommendation)

    async def test_dangling_evidence_reference_routes_to_manual_review(self):
        async def income(_context):
            result = make_income()
            result.recognized_evidence_ids.append("salary-not-in-case")
            return result

        orchestrator = IncomeVerificationOrchestrator(make_dependencies(income=income))

        result = await orchestrator.run(make_context("case-dangling-evidence"))

        self.assertEqual(result.workflow_state, WorkflowState.MANUAL_REVIEW_REQUIRED)
        self.assertIn(
            "UNRESOLVED_EVIDENCE_REFERENCE",
            {item.code for item in result.findings},
        )

    async def test_retryable_component_recovers_without_losing_audit(self):
        attempts = 0

        async def fetch(_context):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise RuntimeError("temporary upstream detail must not be logged")
            return make_documents()

        orchestrator = IncomeVerificationOrchestrator(
            make_dependencies(fetch=fetch),
            config=WorkflowConfig(max_attempts=2, retry_backoff_seconds=0),
        )

        result = await orchestrator.run(make_context("case-retry"))

        self.assertEqual(result.workflow_state, WorkflowState.HUMAN_REVIEW)
        self.assertEqual(result.retry_counts["document_fetch"], 1)
        self.assertEqual(len(result.errors), 1)
        self.assertNotIn("upstream detail", result.errors[0].message)

    async def test_exhausted_component_routes_to_manual_review(self):
        async def fetch(_context):
            raise RuntimeError("unavailable")

        orchestrator = IncomeVerificationOrchestrator(
            make_dependencies(fetch=fetch),
            config=WorkflowConfig(max_attempts=2, retry_backoff_seconds=0),
        )

        result = await orchestrator.run(make_context("case-failure"))

        self.assertEqual(result.workflow_state, WorkflowState.MANUAL_REVIEW_REQUIRED)
        self.assertEqual(len(result.errors), 2)

    async def test_checkpoint_store_rejects_stale_write(self):
        store = InMemoryCheckpointStore()
        original = make_context("case-concurrent")
        await store.save(original, expected_version=0)
        current = original.model_copy(deep=True)
        current.add_event("CURRENT_WRITE")
        await store.save(current, expected_version=0)
        stale = original.model_copy(deep=True)
        stale.add_event("STALE_WRITE")

        with self.assertRaises(ConcurrentStateError):
            await store.save(stale, expected_version=0)

    def test_invalid_state_transition_is_rejected(self):
        context = make_context("case-invalid-transition")

        with self.assertRaises(InvalidStateTransition):
            context.transition_to(WorkflowState.HUMAN_REVIEW)


if __name__ == "__main__":
    unittest.main()
