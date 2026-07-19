"""General multi-format dossier loading, extraction and evidence location."""

from __future__ import annotations

import csv
import io
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from app.agents.income_verification.state import (
    CaseContext,
    ComponentStatus,
    DocumentExtractionResult,
    DocumentRecord,
    DocumentStatus,
    EvidenceCitation,
    ExtractedFields,
    SalaryTransaction,
    VariableIncomeRecord,
)
from app.services.case_repository import CaseRepository
from app.services.llm import LLMProvider, LLMProviderError


REQUIRED_DOCUMENT_TYPES = (
    "LOAN_APPLICATION",
    "EMPLOYMENT_CONTRACT",
    "PAYSLIP_BUNDLE",
    "BANK_STATEMENT",
)


class LoadedPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    document_name: str
    document_type: str
    checksum: str
    page_number: int
    text: str
    extraction_method: str


class LLMTransaction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    month: str
    amount: Decimal = Field(ge=0)
    currency: str = "VND"
    source: str
    document_id: str
    page_number: int = Field(ge=1)
    quote: str
    confidence: float = Field(ge=0, le=1)


class LLMExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_name: str | None = None
    declared_income: Decimal | None = Field(default=None, ge=0)
    contract_salary: Decimal | None = Field(default=None, ge=0)
    currency: str = "VND"
    employer: str | None = None
    contract_expiry: date | None = None
    salary_transactions: list[LLMTransaction] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def _amount(value: str | None) -> Decimal | None:
    if not value:
        return None
    normalized = re.sub(r"[^0-9,.-]", "", value).replace(".", "").replace(",", "")
    try:
        return Decimal(normalized)
    except Exception:
        return None


def _first(patterns: list[str], text: str) -> tuple[str, str] | tuple[None, None]:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).strip(), match.group(0).strip()
    return None, None


class DocumentProcessor:
    """DocumentLoader + TextExtractor + FieldExtractor + EvidenceLocator."""

    def __init__(self, repository: CaseRepository, llm: LLMProvider) -> None:
        self.repository = repository
        self.llm = llm

    async def fetch_documents(self, context: CaseContext) -> list[DocumentRecord]:
        rows = self.repository.list_documents(context.case_id)
        records = [
            DocumentRecord(
                document_id=row.id,
                document_name=row.file_name,
                document_type=row.document_type,
                checksum=row.checksum,
                status=(
                    DocumentStatus.UNREADABLE
                    if row.processing_status == "UNREADABLE"
                    else DocumentStatus.AVAILABLE
                ),
                content_type=row.content_type,
                page_count=row.page_count,
                processing_status=row.processing_status,
                size_bytes=row.size_bytes,
            )
            for row in rows
        ]
        present = {record.document_type for record in records}
        for missing in sorted(set(REQUIRED_DOCUMENT_TYPES) - present):
            records.append(
                DocumentRecord(
                    document_id=f"MISSING-{missing}",
                    document_name=missing,
                    document_type=missing,
                    checksum="missing",
                    status=DocumentStatus.MISSING,
                    processing_status="MISSING",
                )
            )
        return records

    async def __call__(self, context: CaseContext) -> DocumentExtractionResult:
        available = [item for item in context.documents if item.status is DocumentStatus.AVAILABLE]
        missing = [item.document_type for item in context.documents if item.status is DocumentStatus.MISSING]
        if missing:
            return DocumentExtractionResult(
                status=ComponentStatus.MISSING_DATA,
                reason_code="MISSING_DOCUMENTS:" + ",".join(sorted(missing)),
            )
        pages: list[LoadedPage] = []
        try:
            for record in available:
                pages.extend(self._load(record, context.case_id))
        except (OSError, ValueError) as exc:
            return DocumentExtractionResult(
                status=ComponentStatus.MANUAL_REVIEW,
                reason_code=str(exc),
            )

        deterministic, evidence, variable_records = self._extract_deterministic(pages)
        llm_result: LLMExtraction | None = None
        if self.llm.available:
            try:
                llm_result = await self.llm.generate_structured(
                    LLMExtraction,
                    system_prompt=(
                        "Bạn là Document Agent cho xác minh thu nhập vay tín chấp. "
                        "Chỉ trích xuất dữ kiện xuất hiện nguyên văn; không suy diễn, "
                        "không quyết định khoản vay. Mỗi giao dịch phải trỏ đúng tài liệu, "
                        "trang và quote."
                    ),
                    user_prompt=self._llm_prompt(pages),
                    operation="document_extraction",
                )
            except LLMProviderError:
                llm_result = None

        merged, llm_evidence = self._merge_llm(deterministic, llm_result, pages)
        evidence.extend(llm_evidence)
        missing_fields = [
            name
            for name in ("customer_name", "declared_income", "contract_salary", "employer")
            if merged.get(name) is None
        ]
        transactions = merged.get("salary_transactions") or []
        if not transactions:
            missing_fields.append("salary_transactions")
        if missing_fields:
            return DocumentExtractionResult(
                status=ComponentStatus.MANUAL_REVIEW,
                evidence=evidence,
                reason_code="FIELDS_NOT_EXTRACTED:" + ",".join(missing_fields),
            )
        confidence_values = [item.confidence for item in evidence] or [0.5]
        result = DocumentExtractionResult(
            status=ComponentStatus.SUCCESS,
            extracted_fields=ExtractedFields(
                customer_name=merged["customer_name"],
                declared_income=merged["declared_income"],
                contract_salary=merged["contract_salary"],
                currency=str(merged.get("currency") or "VND").upper(),
                employer=merged["employer"],
                contract_expiry=merged.get("contract_expiry"),
                salary_transactions=transactions,
                variable_income_records=variable_records,
                missing_documents=[],
                extraction_confidence=sum(confidence_values) / len(confidence_values),
            ),
            evidence=evidence,
        )
        self.repository.record_agent_result(
            case_id=context.case_id,
            agent_name="DocumentAgent",
            status=result.status.value,
            result_payload=result.model_dump(mode="json"),
            llm_provider=self.llm.provider_name if llm_result else "deterministic_fallback",
            model_name=self.llm.model_name if llm_result else None,
            confidence=result.extracted_fields.extraction_confidence,
            warnings=llm_result.warnings if llm_result else [],
        )
        return result

    def _load(self, record: DocumentRecord, case_id: str) -> list[LoadedPage]:
        row = self.repository.get_document(case_id, record.document_id)
        path = Path(row.storage_path)
        suffix = path.suffix.lower()
        pages: list[LoadedPage] = []
        if suffix in {".txt", ".md"}:
            text = path.read_text(encoding="utf-8-sig")
            pages = [self._page(record, 1, text, "text")]
        elif suffix == ".csv":
            text = path.read_text(encoding="utf-8-sig")
            reader = csv.DictReader(io.StringIO(text))
            rows = [" | ".join(f"{key}={value}" for key, value in row.items()) for row in reader]
            pages = [self._page(record, 1, "\n".join(rows), "structured")]
        elif suffix == ".pdf":
            try:
                import fitz

                with fitz.open(path) as pdf:
                    for index, page in enumerate(pdf, 1):
                        text = page.get_text("text").strip()
                        if not text:
                            raise ValueError("OCR_REQUIRED_FOR_SCANNED_PDF")
                        pages.append(self._page(record, index, text, "pdf_text"))
            except ValueError:
                raise
            except Exception as exc:
                raise ValueError("PDF_TEXT_EXTRACTION_FAILED") from exc
        elif suffix in {".png", ".jpg", ".jpeg"}:
            try:
                import pytesseract
                from PIL import Image

                text = pytesseract.image_to_string(Image.open(path), lang="vie+eng").strip()
            except Exception as exc:
                raise ValueError("OCR_ADAPTER_UNAVAILABLE") from exc
            if not text:
                raise ValueError("OCR_RETURNED_NO_TEXT")
            pages = [self._page(record, 1, text, "ocr")]
        else:
            raise ValueError("UNSUPPORTED_DOCUMENT_FORMAT")
        self.repository.update_document_processing(
            record.document_id,
            status="PROCESSED",
            page_count=len(pages),
        )
        return pages

    @staticmethod
    def _page(record: DocumentRecord, number: int, text: str, method: str) -> LoadedPage:
        return LoadedPage(
            document_id=record.document_id,
            document_name=record.document_name,
            document_type=record.document_type,
            checksum=record.checksum,
            page_number=number,
            text=text,
            extraction_method=method,
        )

    def _extract_deterministic(
        self, pages: list[LoadedPage]
    ) -> tuple[dict[str, object], list[EvidenceCitation], list[VariableIncomeRecord]]:
        values: dict[str, object] = {"currency": "VND", "salary_transactions": []}
        evidence: list[EvidenceCitation] = []
        variables: list[VariableIncomeRecord] = []
        patterns = {
            "customer_name": [r"(?:họ và tên|khách hàng|customer(?: name)?)\s*[:=]\s*([^\n|]+)"],
            "declared_income": [r"(?:thu nhập khai báo|declared income)\s*[:=]\s*([^\n|]+)"],
            "contract_salary": [r"(?:lương hợp đồng|contract salary|mức lương)\s*[:=]\s*([^\n|]+)"],
            "employer": [r"(?:công ty|đơn vị công tác|employer)\s*[:=]\s*([^\n|]+)"],
            "contract_expiry": [r"(?:ngày hết hạn|contract expiry|hợp đồng đến)\s*[:=]\s*(\d{4}-\d{2}-\d{2})"],
            "currency": [r"(?:tiền tệ|currency)\s*[:=]\s*([A-Z]{3})"],
        }
        for field_name, field_patterns in patterns.items():
            for page in pages:
                raw, quote = _first(field_patterns, page.text)
                if raw is None:
                    continue
                if field_name in {"declared_income", "contract_salary"}:
                    value: object = _amount(raw)
                elif field_name == "contract_expiry":
                    try:
                        value = date.fromisoformat(raw)
                    except ValueError:
                        continue
                else:
                    value = raw.strip()
                if value is None:
                    continue
                values[field_name] = value
                evidence.append(self._evidence(page, field_name, quote or raw, 0.92, "regex"))
                break

        transaction_patterns = [
            re.compile(
                r"(?P<month>20\d{2}-(?:0[1-9]|1[0-2])).{0,80}?(?P<amount>\d[\d.,]{4,}).{0,80}?(?:source|nguồn|bên chuyển)\s*[:=]\s*(?P<source>[^\n|]+)",
                re.IGNORECASE,
            ),
            re.compile(
                r"month=(?P<month>20\d{2}-(?:0[1-9]|1[0-2]))\s*\|\s*amount=(?P<amount>\d[\d.,]*)\s*\|\s*(?:source|description)=(?P<source>[^\n|]+)",
                re.IGNORECASE,
            ),
        ]
        transactions: list[SalaryTransaction] = []
        for page in pages:
            for pattern in transaction_patterns:
                for index, match in enumerate(pattern.finditer(page.text), 1):
                    amount = _amount(match.group("amount"))
                    if amount is None:
                        continue
                    evidence_id = f"{page.document_id}:salary:{match.group('month')}:{index}"
                    if any(item.month == match.group("month") for item in transactions):
                        continue
                    evidence.append(
                        self._evidence(
                            page,
                            "salary_transaction",
                            match.group(0),
                            0.95 if page.extraction_method == "structured" else 0.88,
                            page.extraction_method,
                            evidence_id=evidence_id,
                        )
                    )
                    transactions.append(
                        SalaryTransaction(
                            month=match.group("month"),
                            amount=amount,
                            currency=str(values.get("currency") or "VND"),
                            source=match.group("source").strip(),
                            evidence_id=evidence_id,
                        )
                    )
        values["salary_transactions"] = sorted(transactions, key=lambda item: item.month)

        variable_pattern = re.compile(
            r"(?P<month>20\d{2}-(?:0[1-9]|1[0-2])).{0,60}?(?:bonus|thưởng|variable)\s*[:=]\s*(?P<amount>\d[\d.,]*)",
            re.IGNORECASE,
        )
        for page in pages:
            for index, match in enumerate(variable_pattern.finditer(page.text), 1):
                amount = _amount(match.group("amount"))
                if amount is None:
                    continue
                evidence_id = f"{page.document_id}:variable:{match.group('month')}:{index}"
                evidence.append(
                    self._evidence(page, "variable_income", match.group(0), 0.88, "regex", evidence_id=evidence_id)
                )
                variables.append(
                    VariableIncomeRecord(
                        month=match.group("month"),
                        amount=amount,
                        currency=str(values.get("currency") or "VND"),
                        evidence_id=evidence_id,
                    )
                )
        return values, evidence, variables

    def _merge_llm(
        self,
        deterministic: dict[str, object],
        llm_result: LLMExtraction | None,
        pages: list[LoadedPage],
    ) -> tuple[dict[str, object], list[EvidenceCitation]]:
        if llm_result is None:
            return deterministic, []
        merged = dict(deterministic)
        for field in ("customer_name", "declared_income", "contract_salary", "employer", "contract_expiry"):
            if merged.get(field) is None and getattr(llm_result, field) is not None:
                merged[field] = getattr(llm_result, field)
        merged["currency"] = merged.get("currency") or llm_result.currency
        page_map = {(page.document_id, page.page_number): page for page in pages}
        evidence: list[EvidenceCitation] = []
        existing_months = {item.month for item in merged.get("salary_transactions", [])}
        transactions = list(merged.get("salary_transactions", []))
        for index, item in enumerate(llm_result.salary_transactions, 1):
            page = page_map.get((item.document_id, item.page_number))
            if page is None or item.quote not in page.text or item.month in existing_months:
                continue
            evidence_id = f"{item.document_id}:llm-salary:{item.month}:{index}"
            evidence.append(
                self._evidence(page, "salary_transaction", item.quote, item.confidence, "llm", evidence_id=evidence_id)
            )
            transactions.append(
                SalaryTransaction(
                    month=item.month,
                    amount=item.amount,
                    currency=item.currency,
                    source=item.source,
                    evidence_id=evidence_id,
                )
            )
            existing_months.add(item.month)
        merged["salary_transactions"] = sorted(transactions, key=lambda value: value.month)
        return merged, evidence

    @staticmethod
    def _evidence(
        page: LoadedPage,
        field_name: str,
        quote: str,
        confidence: float,
        method: str,
        *,
        evidence_id: str | None = None,
    ) -> EvidenceCitation:
        return EvidenceCitation(
            evidence_id=evidence_id or f"{page.document_id}:{field_name}:{page.page_number}",
            document_id=page.document_id,
            document_name=page.document_name,
            page_number=page.page_number,
            quote=re.sub(r"\s+", " ", quote).strip()[:800],
            source_checksum=page.checksum,
            location=f"page:{page.page_number}",
            field_name=field_name,
            confidence=confidence,
            extraction_method=method,
        )

    @staticmethod
    def _llm_prompt(pages: list[LoadedPage]) -> str:
        dossier = []
        for page in pages:
            dossier.append(
                f"DOCUMENT_ID={page.document_id}\nDOCUMENT_TYPE={page.document_type}\n"
                f"PAGE={page.page_number}\n{page.text[:12000]}"
            )
        return "\n\n---\n\n".join(dossier)[:40000]
