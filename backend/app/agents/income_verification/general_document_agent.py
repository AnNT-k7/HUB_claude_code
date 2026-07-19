"""Document Agent implementation for uploaded (non-fixture) cases.

Implements the same async-callable contract as ``MarkdownDocumentAgent``
(``fetch_documents(context) -> list[DocumentRecord]`` and
``__call__(context) -> DocumentExtractionResult``) so it drops into
``WorkflowDependencies`` unchanged — the orchestrator has no idea whether a
case is running against the fixed demo fixture or freshly uploaded PDFs.

Pulls raw bytes via a small ``DocumentIndex`` protocol (implemented by
``app.services.case_service`` against the SQLite-backed document table),
runs them through ``app.services.document_processing``'s Loader ->
TextExtractor -> Classifier -> FieldExtractor -> EvidenceLocator pipeline,
and returns typed, evidence-backed facts — or an explicit MISSING_DATA
status if too little could be verified, never a guess.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.services.document_processing import (
    DocumentProcessingError,
    ProcessedDocument,
    build_extraction_result,
    classify_document,
    extract_fields_with_llm,
    extract_fields_with_regex,
    extract_text,
    load_document,
    merge_extractions,
)
from app.services.llm_provider import LLMProvider, MockLLMProvider

from .state import (
    CaseContext,
    ComponentStatus,
    DocumentExtractionResult,
    DocumentRecord,
    DocumentStatus,
)


@dataclass(frozen=True, slots=True)
class IndexedDocument:
    document_id: str
    file_name: str
    content_type: str
    raw_bytes: bytes


class DocumentIndex(Protocol):
    """Port onto wherever a case's uploaded files actually live."""

    def list_documents(self, case_id: str) -> list[IndexedDocument]: ...


class GeneralDocumentAgent:
    def __init__(self, document_index: DocumentIndex, *, llm: LLMProvider | None = None) -> None:
        self.document_index = document_index
        self.llm = llm or MockLLMProvider()

    async def fetch_documents(self, context: CaseContext) -> list[DocumentRecord]:
        indexed = self.document_index.list_documents(context.case_id)
        if not indexed:
            return []
        records: list[DocumentRecord] = []
        for item in indexed:
            try:
                loaded = load_document(
                    document_id=item.document_id,
                    file_name=item.file_name,
                    content_type=item.content_type,
                    raw_bytes=item.raw_bytes,
                )
            except DocumentProcessingError:
                continue
            text = extract_text(loaded)
            document_type, _ = await classify_document(text.full_text, llm=self.llm)
            status = DocumentStatus.AVAILABLE if text.ocr_available else DocumentStatus.UNREADABLE
            records.append(
                DocumentRecord(
                    document_id=item.document_id,
                    document_name=item.file_name,
                    document_type=document_type,
                    checksum=loaded.checksum,
                    status=status,
                )
            )
        return records

    async def __call__(self, context: CaseContext) -> DocumentExtractionResult:
        indexed = self.document_index.list_documents(context.case_id)
        if not indexed:
            return DocumentExtractionResult(
                status=ComponentStatus.MISSING_DATA,
                reason_code="NO_DOCUMENTS_UPLOADED",
            )

        processed: list[ProcessedDocument] = []
        documents_text: dict[str, str] = {}
        for item in indexed:
            try:
                loaded = load_document(
                    document_id=item.document_id,
                    file_name=item.file_name,
                    content_type=item.content_type,
                    raw_bytes=item.raw_bytes,
                )
                text = extract_text(loaded)
            except DocumentProcessingError:
                continue
            if not text.ocr_available:
                continue
            document_type, method = await classify_document(text.full_text, llm=self.llm)
            record = DocumentRecord(
                document_id=item.document_id,
                document_name=item.file_name,
                document_type=document_type,
                checksum=loaded.checksum,
                status=DocumentStatus.AVAILABLE,
            )
            processed.append(
                ProcessedDocument(
                    record=record,
                    document_type=document_type,
                    classification_method=method,
                    extracted_text=text,
                    checksum=loaded.checksum,
                )
            )
            documents_text[item.document_id] = text.full_text

        if not processed:
            return DocumentExtractionResult(
                status=ComponentStatus.MISSING_DATA,
                reason_code="NO_READABLE_DOCUMENTS",
            )

        llm_extraction, _ = await extract_fields_with_llm(documents_text, llm=self.llm)
        regex_extraction = extract_fields_with_regex("\n".join(documents_text.values()))
        merged, field_methods = merge_extractions(llm_extraction, regex_extraction)

        return build_extraction_result(processed, merged=merged, field_methods=field_methods)
