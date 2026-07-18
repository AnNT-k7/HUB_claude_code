"""MVP runtime wiring for the income-verification API."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app.agents.income_verification import (
    CaseContext,
    IncomeAnalysisAgent,
    IncomeVerificationOrchestrator,
    InMemoryCheckpointStore,
    MarkdownDocumentAgent,
    PolicyAgent,
    WorkflowDependencies,
)
from app.agents.income_verification.orchestrator import CheckpointStore
from app.agents.income_verification.human_review import (
    HumanReviewCommand,
    apply_human_review,
)
from app.services.action_executor import ActionExecutor
from app.services.namespace_rag import NamespaceHit, NamespaceQuery, RagNamespace


BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent
DEFAULT_DOCUMENT_FIXTURE = (
    PROJECT_ROOT
    / "dataset"
    / "document_extraction_agent"
    / "synthetic_income_verification_documents_case_001.md"
)
DEFAULT_POLICY_CORPUS = BACKEND_ROOT / "data" / "rag" / "three_rag_fpt_corpus.json"
DEMO_CASE_ID = "SYN-IV-001"
DEMO_APPLICATION_ID = "SYN-SHB-2026-0001"


class RuntimeCaseNotFound(LookupError):
    pass


class UnsupportedDemoApplication(ValueError):
    pass


class EmbeddedDemoPolicyRetriever:
    """Offline demo retriever over the already built, isolated 512-D corpus."""

    def __init__(self, corpus_path: Path = DEFAULT_POLICY_CORPUS) -> None:
        self.corpus_path = corpus_path

    async def retrieve(self, query: NamespaceQuery) -> list[NamespaceHit]:
        document = json.loads(self.corpus_path.read_text(encoding="utf-8"))
        namespace = document["namespaces"].get(query.namespace.value, {"chunks": []})
        hits = []
        for chunk in namespace["chunks"]:
            metadata = chunk["metadata"]
            if metadata.get("rag_namespace") != RagNamespace.POLICY.value:
                continue
            if metadata.get("domain") != query.domain:
                continue
            if metadata.get("product") != query.product:
                continue
            if query.chunk_types and metadata.get("chunk_type") not in query.chunk_types:
                continue
            if metadata.get("indexing_scope") not in query.allowed_scopes:
                continue
            if metadata.get("approval_status") not in query.approval_statuses:
                continue
            hits.append(
                NamespaceHit(
                    chunk_id=chunk["chunk_id"],
                    namespace=RagNamespace.POLICY,
                    score=1.0,
                    content=chunk["content_chunk"],
                    document_name=metadata["document_name"],
                    page_number=int(metadata.get("page_number") or 1),
                    section_id=metadata["section_id"],
                    source_path=metadata["source_path"],
                    chunk_type=metadata["chunk_type"],
                    indexing_scope=metadata["indexing_scope"],
                    domain=metadata.get("domain", ""),
                    product=metadata.get("product", ""),
                    effective_date=metadata.get("effective_date"),
                    expiry_date=metadata.get("expiry_date")
                    or metadata.get("effective_to"),
                    approval_status=metadata.get("approval_status"),
                )
            )
        return hits[: query.top_k]


class IncomeVerificationRuntime:
    """Own demo case state, workflow wiring, review and safe action execution."""

    def __init__(self, *, checkpoints: CheckpointStore | None = None) -> None:
        self.checkpoints = checkpoints or InMemoryCheckpointStore()
        self.document_agent = MarkdownDocumentAgent(DEFAULT_DOCUMENT_FIXTURE)
        self.orchestrator = IncomeVerificationOrchestrator(
            WorkflowDependencies(
                fetch_documents=self.document_agent.fetch_documents,
                extract_documents=self.document_agent,
                analyze_income=IncomeAnalysisAgent(),
                retrieve_policy=PolicyAgent(EmbeddedDemoPolicyRetriever()),
            ),
            checkpoint_store=self.checkpoints,
        )
        self.action_executor = ActionExecutor()
        self._application_cases: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def start(self, application_id: str) -> CaseContext:
        if application_id != DEMO_APPLICATION_ID:
            raise UnsupportedDemoApplication(
                "MVP demo currently accepts only the normalized synthetic application."
            )
        async with self._lock:
            existing_case_id = self._application_cases.get(application_id)
            if existing_case_id:
                existing = await self.checkpoints.load(existing_case_id)
                if existing is not None:
                    return existing
            context = CaseContext(
                case_id=DEMO_CASE_ID,
                application_id=application_id,
            )
            result = await self.orchestrator.run(context)
            self._application_cases[application_id] = result.case_id
            return result

    async def get(self, case_id: str) -> CaseContext:
        context = await self.checkpoints.load(case_id)
        if context is None:
            raise RuntimeCaseNotFound(case_id)
        return context

    async def review(
        self,
        case_id: str,
        command: HumanReviewCommand,
        *,
        reviewer_id: str,
    ) -> CaseContext:
        async with self._lock:
            previous = await self.get(case_id)
            reviewed = apply_human_review(previous, command, reviewer_id=reviewer_id)
            await self.checkpoints.save(reviewed, expected_version=previous.state_version)
            if command.outcome.value == "EDIT_AND_RERUN":
                return await self.orchestrator.run(reviewed)
            if command.outcome.value != "ACCEPT_ACTIONS":
                return reviewed
            executed = await self.action_executor.execute(reviewed)
            await self.checkpoints.save(executed, expected_version=reviewed.state_version)
            return executed

    async def retry_actions(self, case_id: str) -> CaseContext:
        async with self._lock:
            previous = await self.get(case_id)
            executed = await self.action_executor.execute(previous)
            await self.checkpoints.save(executed, expected_version=previous.state_version)
            return executed


_runtime = IncomeVerificationRuntime()


def get_runtime() -> IncomeVerificationRuntime:
    return _runtime
