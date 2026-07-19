"""Run all 20 synthetic ground-truth cases through the real multi-case
pipeline (CaseService), fully offline — LLM_PROVIDER=mock and a keyword-match
policy retriever — per docs/PROJECT-RULES.md §10 ("workflow tests pass mà
không gọi live LLM"). Each case bundle under
backend/data/synthetic_cases/case_NN_<slug>/ was produced by
scripts/generate_synthetic_cases.py and carries a ground_truth.json this
test checks the pipeline's outcome against.

This exercises case creation, document upload, disk storage, SQLite
persistence, the generalized document-processing pipeline (deterministic
regex path), income calculation, policy retrieval, consistency checking and
recommendation building — end to end, for 20 different real-world document
situations (missing docs, expired contract, currency mismatch, cash salary,
employer-name mismatch, volatile income, etc.).
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.services.case_document_store as case_document_store_module  # noqa: E402
import app.services.case_service as case_service_module  # noqa: E402
from app.db.case_models import CaseBase  # noqa: E402
from app.services.llm_provider import MockLLMProvider  # noqa: E402
from app.services.runtime import EmbeddedDemoPolicyRetriever  # noqa: E402

SYNTHETIC_CASES_ROOT = BACKEND_ROOT / "data" / "synthetic_cases"

# Ground-truth "verified/insufficient/inconsistent/manual_review" labels map
# onto this pipeline's actual WorkflowState/VerificationResultStatus values.
_STATUS_TO_WORKFLOW_STATES = {
    "verified": {"HUMAN_REVIEW"},
    "insufficient": {"AWAITING_DOCUMENTS", "MANUAL_REVIEW_REQUIRED"},
    "inconsistent": {"HUMAN_REVIEW", "MANUAL_REVIEW_REQUIRED"},
    "manual_review": {"MANUAL_REVIEW_REQUIRED"},
}


def _load_bundles() -> list[dict]:
    bundles = []
    for bundle_dir in sorted(SYNTHETIC_CASES_ROOT.glob("case_*")):
        ground_truth_path = bundle_dir / "ground_truth.json"
        if not ground_truth_path.is_file():
            continue
        ground_truth = json.loads(ground_truth_path.read_text(encoding="utf-8"))
        documents = {
            name: (bundle_dir / name).read_bytes()
            for name in ground_truth["documents"]
        }
        bundles.append({"dir": bundle_dir, "ground_truth": ground_truth, "documents": documents})
    return bundles


class SyntheticCasesTests(unittest.IsolatedAsyncioTestCase):
    """One test method per bundle would be nicer for reporting, but the
    bundle set is generated data, not literal code — a single parametrized
    loop keeps this file from having to be regenerated in lockstep with the
    scenario generator."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._bundles = _load_bundles()
        assert len(cls._bundles) == 20, f"expected 20 synthetic case bundles, found {len(cls._bundles)}"

        # Isolated in-memory SQLite for iv_cases/iv_documents/iv_audit_logs —
        # StaticPool keeps one shared connection alive across the asyncio.to_thread
        # calls CaseService makes, since a bare ":memory:" DB is per-connection.
        cls._test_engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        CaseBase.metadata.create_all(bind=cls._test_engine)
        cls._test_session_local = sessionmaker(bind=cls._test_engine, autoflush=False, autocommit=False)

        cls._real_session_local = case_service_module.CaseSessionLocal
        case_service_module.CaseSessionLocal = cls._test_session_local

        cls._tmp_storage_dir = Path(BACKEND_ROOT / "data" / "_test_case_documents")
        cls._tmp_storage_dir.mkdir(parents=True, exist_ok=True)
        cls._real_case_root = case_document_store_module._case_root
        case_document_store_module._case_root = lambda: cls._tmp_storage_dir

    @classmethod
    def tearDownClass(cls) -> None:
        case_service_module.CaseSessionLocal = cls._real_session_local
        case_document_store_module._case_root = cls._real_case_root
        import shutil

        shutil.rmtree(cls._tmp_storage_dir, ignore_errors=True)

    def _build_service(self) -> case_service_module.CaseService:
        return case_service_module.CaseService(
            llm=MockLLMProvider(), policy_retriever=EmbeddedDemoPolicyRetriever()
        )

    async def test_all_twenty_synthetic_cases_reach_expected_outcome(self) -> None:
        service = self._build_service()
        failures: list[str] = []

        for bundle in self._bundles:
            ground_truth = bundle["ground_truth"]
            slug = ground_truth["slug"]
            context = await service.create_case(
                customer_name=ground_truth["customer_name"],
                customer_code=None,
                employer=ground_truth["employer"],
                requested_amount=None,
                loan_term_months=None,
            )
            for file_name, content in bundle["documents"].items():
                await service.add_document(
                    context.case_id,
                    file_name=file_name,
                    content_type="text/plain",
                    raw_bytes=content,
                )
            result = await service.run_pipeline(context.case_id)

            expected_states = _STATUS_TO_WORKFLOW_STATES[ground_truth["expected_status"]]
            actual_state = result.workflow_state.value
            if actual_state not in expected_states:
                failures.append(
                    f"{slug}: expected workflow_state in {sorted(expected_states)} "
                    f"(status={ground_truth['expected_status']!r}), got {actual_state!r} "
                    f"(reason: {[e.reason_code for e in [result.policy_result, result.income_analysis] if e]})"
                )

        if failures:
            self.fail("Synthetic case mismatches:\n" + "\n".join(failures))

    async def test_missing_document_cases_report_the_expected_missing_type(self) -> None:
        service = self._build_service()
        for bundle in self._bundles:
            ground_truth = bundle["ground_truth"]
            if not ground_truth["expected_missing_documents"]:
                continue
            context = await service.create_case(
                customer_name=ground_truth["customer_name"],
                customer_code=None,
                employer=ground_truth["employer"],
                requested_amount=None,
                loan_term_months=None,
            )
            for file_name, content in bundle["documents"].items():
                await service.add_document(
                    context.case_id,
                    file_name=file_name,
                    content_type="text/plain",
                    raw_bytes=content,
                )
            result = await service.run_pipeline(context.case_id)
            with self.subTest(case=ground_truth["slug"]):
                self.assertIn(
                    result.workflow_state.value,
                    {"AWAITING_DOCUMENTS", "MANUAL_REVIEW_REQUIRED"},
                    f"{ground_truth['slug']} should not silently succeed while missing "
                    f"{ground_truth['expected_missing_documents']}",
                )


if __name__ == "__main__":
    unittest.main()
