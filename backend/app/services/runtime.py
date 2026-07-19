"""Persistent multi-case runtime for the Income Verification Expert MVP."""

from __future__ import annotations

import asyncio
import json
from functools import lru_cache
from pathlib import Path

from app.agents.income_verification import (
    CaseContext,
    IncomeAnalysisAgent,
    IncomeVerificationOrchestrator,
    PolicyAgent,
    WorkflowDependencies,
)
from app.agents.income_verification.human_review import HumanReviewCommand, apply_human_review
from app.agents.income_verification.orchestrator import CheckpointStore, ConcurrentStateError
from app.agents.income_verification.policy_agent import NamespacePolicyRetriever
from app.agents.income_verification.state import WorkflowState
from app.config import Settings, get_settings
from app.services.action_executor import ActionExecutor
from app.services.case_repository import CaseNotFound, CaseRepository
from app.services.document_processing import DocumentProcessor
from app.services.llm import LLMProvider, build_llm_provider
from app.services.namespace_rag import NamespaceHit, NamespaceQuery, RagNamespace
from app.services.report_synthesis import enrich_report_with_fpt


BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY_CORPUS = BACKEND_ROOT / "data" / "rag" / "three_rag_fpt_corpus.json"


class RuntimeCaseNotFound(LookupError):
    pass


class UnsupportedDemoApplication(ValueError):
    """Kept for backward-compatible imports from older clients."""


class EmbeddedDemoPolicyRetriever:
    """Offline fallback over the same chunked corpus used by vector RAG."""

    def __init__(self, corpus_path: Path = DEFAULT_POLICY_CORPUS) -> None:
        self.corpus_path = corpus_path

    async def retrieve(self, query: NamespaceQuery) -> list[NamespaceHit]:
        document = json.loads(self.corpus_path.read_text(encoding="utf-8"))
        namespace = document["namespaces"].get(query.namespace.value, {"chunks": []})
        hits: list[NamespaceHit] = []
        for chunk in namespace["chunks"]:
            metadata = chunk["metadata"]
            if metadata.get("rag_namespace") != RagNamespace.POLICY.value:
                continue
            if metadata.get("domain") != query.domain or metadata.get("product") != query.product:
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
                    expiry_date=metadata.get("expiry_date") or metadata.get("effective_to"),
                    approval_status=metadata.get("approval_status"),
                )
            )
        return hits[: query.top_k]


class RepositoryCheckpointStore(CheckpointStore):
    def __init__(self, repository: CaseRepository) -> None:
        self.repository = repository
        self._lock = asyncio.Lock()

    async def load(self, case_id: str) -> CaseContext | None:
        try:
            return await asyncio.to_thread(self.repository.load_context, case_id)
        except CaseNotFound:
            return None

    async def save(self, context: CaseContext, *, expected_version: int) -> None:
        async with self._lock:
            existing = await self.load(context.case_id)
            current_version = existing.state_version if existing is not None else 0
            if current_version != expected_version:
                raise ConcurrentStateError(f"Case {context.case_id} checkpoint version changed")
            await asyncio.to_thread(self.repository.save_context, context)


class IncomeVerificationRuntime:
    """Wire uploaded evidence, deterministic agents, policy RAG and human-gated actions."""

    def __init__(
        self,
        *,
        repository: CaseRepository | None = None,
        llm: LLMProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or (repository.settings if repository is not None else get_settings())
        self.repository = repository or CaseRepository(settings=self.settings)
        self.llm = llm or build_llm_provider(self.settings)
        self.document_processor = DocumentProcessor(self.repository, self.llm)
        # Tests and disconnected development still use the exact chunked corpus,
        # while configured demo mode performs a real embedding query over it.
        policy_retriever = (
            NamespacePolicyRetriever()
            if self.llm.available and self.settings.embedding_provider.lower() == "fpt"
            else EmbeddedDemoPolicyRetriever()
        )
        self.checkpoints = RepositoryCheckpointStore(self.repository)
        self.orchestrator = IncomeVerificationOrchestrator(
            WorkflowDependencies(
                fetch_documents=self.document_processor.fetch_documents,
                extract_documents=self.document_processor,
                analyze_income=IncomeAnalysisAgent(),
                retrieve_policy=PolicyAgent(policy_retriever),
            ),
            checkpoint_store=self.checkpoints,
        )
        self.action_executor = ActionExecutor()
        self._lock = asyncio.Lock()

    def runtime_info(self) -> dict[str, object]:
        live_llm = self.llm.available
        live_vector = live_llm and self.settings.embedding_provider.lower() == "fpt"
        return {
            "llm_provider": self.llm.provider_name if live_llm else "deterministic_fallback",
            "llm_model": self.llm.model_name if live_llm else "",
            "llm_mode": "FPT_LLM" if live_llm else "DETERMINISTIC_FALLBACK",
            "rag_mode": "FPT_VECTOR_RAG" if live_vector else "EMBEDDED_POLICY_RAG",
            "embedding_provider": self.settings.embedding_provider,
            "embedding_model": self.settings.embedding_model,
            "embedding_dimensions": self.settings.embedding_dimensions,
            "policy_corpus": str(DEFAULT_POLICY_CORPUS),
            "synthetic_policy_notice": "Corpus chính sách tổng hợp chỉ dùng cho demo cuộc thi.",
        }

    async def start_case(self, case_id: str, *, rerun: bool = False) -> CaseContext:
        async with self._lock:
            try:
                case = self.repository.get_case(case_id)
            except CaseNotFound as exc:
                raise RuntimeCaseNotFound(case_id) from exc
            existing = self.repository.load_context(case_id)
            if rerun and existing is not None:
                self.repository.reset_context(case_id)
                existing = None
            context = existing or CaseContext(
                case_id=case.id,
                application_id=case.application_id,
                runtime_mode=("FPT_LLM" if self.llm.available else "DETERMINISTIC_FALLBACK"),
            )
            result = await self.orchestrator.run(context)
            if result.workflow_state is WorkflowState.HUMAN_REVIEW:
                result = await enrich_report_with_fpt(
                    result,
                    llm=self.llm,
                    repository=self.repository,
                )
                self.repository.save_context(result)
            return result

    async def start(self, application_id: str) -> CaseContext:
        case = self.repository.get_by_application(application_id)
        if case is None:
            raise UnsupportedDemoApplication("Application does not exist.")
        return await self.start_case(case.id)

    async def get(self, case_id: str) -> CaseContext:
        try:
            context = self.repository.load_context(case_id)
        except CaseNotFound as exc:
            raise RuntimeCaseNotFound(case_id) from exc
        if context is None:
            raise RuntimeCaseNotFound(case_id)
        return context

    async def review(self, case_id: str, command: HumanReviewCommand, *, reviewer_id: str) -> CaseContext:
        async with self._lock:
            previous = await self.get(case_id)
            reviewed = apply_human_review(previous, command, reviewer_id=reviewer_id)
            self.repository.save_context(reviewed)
            if command.outcome.value == "EDIT_AND_RERUN":
                result = await self.orchestrator.run(reviewed)
                self.repository.save_context(result)
                return result
            if command.outcome.value != "ACCEPT_ACTIONS":
                return reviewed
            executed = await self.action_executor.execute(reviewed)
            self.repository.save_context(executed)
            return executed

    async def retry_actions(self, case_id: str) -> CaseContext:
        async with self._lock:
            previous = await self.get(case_id)
            executed = await self.action_executor.execute(previous)
            self.repository.save_context(executed)
            return executed

    async def reset(self, application_id: str) -> None:
        case = self.repository.get_by_application(application_id)
        if case is None:
            raise UnsupportedDemoApplication("Application does not exist.")
        self.repository.reset_context(case.id)


@lru_cache
def get_runtime() -> IncomeVerificationRuntime:
    return IncomeVerificationRuntime()
