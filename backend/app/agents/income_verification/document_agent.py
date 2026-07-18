"""Case-scoped document extraction adapter for income-verification evidence."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from .state import (
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


_DOCUMENT_PATTERN = re.compile(
    r"## Tài liệu \d+[^\n]*\n.*?\*\*Document ID:\*\* `(?P<id>[^`]+)`"
    r"\s+\*\*Document type:\*\* `(?P<type>[^`]+)`",
    re.DOTALL,
)
_TRANSACTION_PATTERN = re.compile(
    r"^\| `(?P<evidence_id>[^`]+)` \| (?P<date>\d{2}/\d{2}/\d{4}) "
    r"\| (?P<description>[^|]+?) \| (?P<source>[^|]+?) \| (?P<amount>[\d.]+) \|$",
    re.MULTILINE,
)
_PAYSLIP_PATTERN = re.compile(
    r"^\| (?P<month>\d{4}-\d{2}) \| (?P<base>[\d.]+) \| "
    r"(?P<variable>[\d.]+) \| (?P<deduction>[\d.]+) \| (?P<net>[\d.]+) \|$",
    re.MULTILINE,
)


class DocumentExtractionError(ValueError):
    """Raised when a source document cannot be parsed without guessing."""


@dataclass(frozen=True, slots=True)
class DocumentAgentConfig:
    required_document_types: tuple[str, ...] = (
        "LOAN_APPLICATION",
        "EMPLOYMENT_CONTRACT",
        "PAYSLIP_BUNDLE",
        "BANK_STATEMENT",
    )
    optional_document_types: tuple[str, ...] = ("SALARY_ADJUSTMENT_APPENDIX",)


def _first_match(pattern: str, text: str, *, flags: int = 0) -> str | None:
    match = re.search(pattern, text, flags)
    return match.group(1).strip() if match else None


def _parse_vnd(value: str | None) -> Decimal | None:
    if value is None:
        return None
    digits = re.sub(r"[^0-9]", "", value)
    return Decimal(digits) if digits else None


def _source_checksum(content: str) -> str:
    return "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()


class MarkdownDocumentAgent:
    """Extract the normalized synthetic Markdown fixture without using ground truth.

    This adapter is intentionally file-backed for development and testing. Production
    OCR/document services can implement the same async callable contract while keeping
    source bytes and evidence case-scoped.
    """

    def __init__(
        self,
        source_path: Path,
        *,
        config: DocumentAgentConfig | None = None,
    ) -> None:
        self.source_path = source_path.resolve()
        self.config = config or DocumentAgentConfig()

    def _read_source(self) -> str:
        if not self.source_path.is_file():
            raise DocumentExtractionError("The configured case document is unavailable.")
        if self.source_path.suffix.lower() not in {".md", ".txt"}:
            raise DocumentExtractionError("UNSUPPORTED_TEXT_FIXTURE_FORMAT")
        return self.source_path.read_text(encoding="utf-8")

    async def fetch_documents(self, context: CaseContext) -> list[DocumentRecord]:
        """Return normalized document inventory for the configured case fixture."""

        content = self._read_source()
        self._validate_case_scope(content, context)
        checksum = _source_checksum(content)
        records = []
        for match in _DOCUMENT_PATTERN.finditer(content):
            document_type = match.group("type")
            records.append(
                DocumentRecord(
                    document_id=match.group("id"),
                    document_name=f"{document_type.lower()}.md",
                    document_type=document_type,
                    checksum=checksum,
                    status=DocumentStatus.AVAILABLE,
                )
            )
        return records

    async def __call__(self, context: CaseContext) -> DocumentExtractionResult:
        """Extract typed facts and evidence; return incomplete instead of inferring."""

        try:
            content = self._read_source()
            self._validate_case_scope(content, context)
            return self._extract(content, context)
        except DocumentExtractionError as exc:
            return DocumentExtractionResult(
                status=ComponentStatus.MISSING_DATA,
                reason_code=str(exc),
            )

    @staticmethod
    def _validate_case_scope(content: str, context: CaseContext) -> None:
        header = content.split("---", 2)[1] if content.startswith("---") else ""
        case_id = _first_match(r"^case_id:\s*(.+)$", header, flags=re.MULTILINE)
        application_id = _first_match(
            r"^application_id:\s*(.+)$", header, flags=re.MULTILINE
        )
        if case_id and case_id != context.case_id:
            raise DocumentExtractionError("CASE_SCOPE_MISMATCH")
        if application_id and application_id != context.application_id:
            raise DocumentExtractionError("APPLICATION_SCOPE_MISMATCH")

    def _extract(
        self,
        content: str,
        context: CaseContext,
    ) -> DocumentExtractionResult:
        # Evaluation labels are never inputs to the extractor.
        customer_content = content.split("## Nhãn chuẩn dùng để đánh giá extraction", 1)[0]
        records = {
            record.document_type: record
            for record in self._records_from_content(customer_content)
        }
        available_context_types = {
            item.document_type
            for item in context.documents
            if item.status is DocumentStatus.AVAILABLE
        }
        required = set(self.config.required_document_types)
        missing_required = sorted(required - set(records))
        if context.documents:
            missing_required = sorted(
                set(missing_required).union(required - available_context_types)
            )
        if missing_required:
            return DocumentExtractionResult(
                status=ComponentStatus.MISSING_DATA,
                reason_code="MISSING_REQUIRED_DOCUMENTS:" + ",".join(missing_required),
            )

        customer_name = _first_match(r"- Họ và tên:\s*([^\n]+)", customer_content)
        declared_text = _first_match(
            r"- Thu nhập khai báo:\s*([^\n]+)", customer_content
        )
        employer = _first_match(
            r"- Đơn vị công tác:\s*([^\n]+)", customer_content
        )
        contract_text = _first_match(
            r"- Lương cơ bản theo hợp đồng:\s*([^\n]+)", customer_content
        )
        expiry_text = _first_match(r"- Ngày hết hạn:\s*(\d{2}/\d{2}/\d{4})", customer_content)
        currency = _first_match(
            r"\*\*Đơn vị tiền tệ:\*\*\s*([A-Z]{3})", customer_content
        ) or "VND"
        declared_income = _parse_vnd(declared_text)
        contract_salary = _parse_vnd(contract_text)
        if not all((customer_name, employer, declared_income, contract_salary, expiry_text)):
            raise DocumentExtractionError("CORE_INCOME_FIELDS_INCOMPLETE")
        contract_expiry = datetime.strptime(expiry_text, "%d/%m/%Y").date()

        checksum = _source_checksum(content)
        application = records["LOAN_APPLICATION"]
        contract = records["EMPLOYMENT_CONTRACT"]
        payslip = records["PAYSLIP_BUNDLE"]
        statement = records["BANK_STATEMENT"]
        evidence = [
            EvidenceCitation(
                evidence_id="application_customer_name",
                document_id=application.document_id,
                document_name=application.document_name,
                page_number=1,
                quote=f"Họ và tên: {customer_name}",
                source_checksum=checksum,
                location="Thông tin khách hàng",
            ),
            EvidenceCitation(
                evidence_id="application_declared_income",
                document_id=application.document_id,
                document_name=application.document_name,
                page_number=1,
                quote=f"Thu nhập khai báo: {declared_text}",
                source_checksum=checksum,
                location="Thông tin công việc và khoản vay",
            ),
            EvidenceCitation(
                evidence_id="application_employer",
                document_id=application.document_id,
                document_name=application.document_name,
                page_number=1,
                quote=f"Đơn vị công tác: {employer}",
                source_checksum=checksum,
                location="Thông tin công việc và khoản vay",
            ),
            EvidenceCitation(
                evidence_id="contract_salary",
                document_id=contract.document_id,
                document_name=contract.document_name,
                page_number=2,
                quote=f"Lương cơ bản theo hợp đồng: {contract_text}",
                source_checksum=checksum,
                location="Điều khoản công việc và tiền lương",
            ),
            EvidenceCitation(
                evidence_id="contract_expiry",
                document_id=contract.document_id,
                document_name=contract.document_name,
                page_number=2,
                quote=f"Ngày hết hạn: {expiry_text}",
                source_checksum=checksum,
                location="Điều khoản công việc và tiền lương",
            ),
        ]
        transactions: list[SalaryTransaction] = []
        for match in _TRANSACTION_PATTERN.finditer(customer_content):
            transaction_date = datetime.strptime(match.group("date"), "%d/%m/%Y")
            evidence_id = match.group("evidence_id")
            amount = _parse_vnd(match.group("amount"))
            if amount is None:
                continue
            quote = " | ".join(
                (
                    match.group("date"),
                    match.group("description").strip(),
                    match.group("source").strip(),
                    match.group("amount"),
                )
            )
            evidence.append(
                EvidenceCitation(
                    evidence_id=evidence_id,
                    document_id=statement.document_id,
                    document_name=statement.document_name,
                    page_number=4,
                    quote=quote,
                    source_checksum=checksum,
                    location=evidence_id,
                )
            )
            transactions.append(
                SalaryTransaction(
                    month=transaction_date.strftime("%Y-%m"),
                    amount=amount,
                    currency=currency,
                    source=match.group("source").strip(),
                    evidence_id=evidence_id,
                )
            )
        if not transactions:
            raise DocumentExtractionError("BANK_TRANSACTIONS_NOT_EXTRACTED")

        variable_income_records: list[VariableIncomeRecord] = []
        for match in _PAYSLIP_PATTERN.finditer(customer_content):
            month = match.group("month")
            amount = _parse_vnd(match.group("variable"))
            if amount is None:
                continue
            evidence_id = f"payslip_{month.replace('-', '_')}_variable"
            evidence.append(
                EvidenceCitation(
                    evidence_id=evidence_id,
                    document_id=payslip.document_id,
                    document_name=payslip.document_name,
                    page_number=3,
                    quote=(
                        f"{month} | base={match.group('base')} | "
                        f"variable={match.group('variable')} | net={match.group('net')}"
                    ),
                    source_checksum=checksum,
                    location=f"payroll-row:{month}",
                )
            )
            variable_income_records.append(
                VariableIncomeRecord(
                    month=month,
                    amount=amount,
                    currency=currency,
                    evidence_id=evidence_id,
                )
            )
        if not variable_income_records:
            raise DocumentExtractionError("PAYSLIP_COMPONENTS_NOT_EXTRACTED")

        optional_missing = sorted(set(self.config.optional_document_types) - set(records))
        return DocumentExtractionResult(
            status=ComponentStatus.SUCCESS,
            extracted_fields=ExtractedFields(
                customer_name=customer_name,
                declared_income=declared_income,
                contract_salary=contract_salary,
                currency=currency,
                employer=employer,
                contract_expiry=contract_expiry,
                salary_transactions=transactions,
                variable_income_records=variable_income_records,
                missing_documents=optional_missing,
                extraction_confidence=0.98,
            ),
            evidence=evidence,
        )

    @staticmethod
    def _records_from_content(content: str) -> list[DocumentRecord]:
        checksum = _source_checksum(content)
        return [
            DocumentRecord(
                document_id=match.group("id"),
                document_name=f"{match.group('type').lower()}.md",
                document_type=match.group("type"),
                checksum=checksum,
            )
            for match in _DOCUMENT_PATTERN.finditer(content)
        ]


class PdfTextDocumentAgent(MarkdownDocumentAgent):
    """Text-PDF adapter for digitally generated dossiers.

    Scanned PDFs deliberately return ``UNREADABLE`` until an approved OCR adapter
    supplies text and page coordinates; this prevents silently inventing facts.
    """

    def _read_source(self) -> str:
        if not self.source_path.is_file() or self.source_path.suffix.lower() != ".pdf":
            raise DocumentExtractionError("PDF_SOURCE_REQUIRED")
        try:
            import fitz

            with fitz.open(self.source_path) as document:
                pages = []
                for page_number, page in enumerate(document, 1):
                    text = page.get_text("text").strip()
                    if not text:
                        raise DocumentExtractionError("OCR_REQUIRED_FOR_SCANNED_PAGE")
                    pages.append(f"<!-- Trang {page_number} -->\n{text}")
                return "\n\n".join(pages)
        except DocumentExtractionError:
            raise
        except Exception as exc:
            raise DocumentExtractionError("PDF_TEXT_EXTRACTION_FAILED") from exc
