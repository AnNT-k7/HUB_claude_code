"""General-purpose document processing: Loader -> TextExtractor -> Classifier ->
FieldExtractor -> EvidenceLocator.

This replaces the fixture-only ``MarkdownDocumentAgent`` code path for
uploaded cases: instead of regex-parsing one pre-known synthetic file, it
accepts whatever PDFs/images/text/CSV a case's documents actually are,
extracts text generically, classifies each document, and asks the LLM
provider (see ``app.services.llm_provider``) to pull out the same typed
fields the rest of the pipeline already expects
(``app.agents.income_verification.state.ExtractedFields``).

Every LLM-sourced fact is only accepted if a Python validator can find its
claimed quote verbatim in the actual extracted document text — this is the
"LLM proposes, deterministic code disposes" pattern used throughout this
codebase (see ``app/tools/income_calculator.py`` for the arithmetic
equivalent). If the LLM is unavailable or a field fails validation, a
regex-based deterministic fallback (reusing the label patterns from
``MarkdownDocumentAgent``) is tried before the field is simply omitted —
missing evidence must never become a guessed value.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, ConfigDict, Field as PydField

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
from app.services.llm_provider import LLMProvider

# ---------------------------------------------------------------------------
# Document type taxonomy (item B of the brief)
# ---------------------------------------------------------------------------

DOCUMENT_TYPES = (
    "LOAN_APPLICATION",
    "ID_DOCUMENT",
    "EMPLOYMENT_CONTRACT",
    "PAYSLIP_BUNDLE",
    "BANK_STATEMENT",
    "INCOME_CONFIRMATION",
    "OTHER",
)

_CLASSIFIER_KEYWORDS: dict[str, tuple[str, ...]] = {
    "LOAN_APPLICATION": ("đề nghị vay", "giấy đề nghị", "hồ sơ vay", "khoản vay đề nghị"),
    "ID_DOCUMENT": ("căn cước", "cccd", "chứng minh nhân dân", "cmnd", "hộ chiếu"),
    "EMPLOYMENT_CONTRACT": ("hợp đồng lao động", "phụ lục hợp đồng", "thời hạn hợp đồng"),
    "PAYSLIP_BUNDLE": ("bảng lương", "phiếu lương", "payroll", "lương cơ bản"),
    "BANK_STATEMENT": ("sao kê", "statement", "giao dịch tài khoản", "số dư"),
    "INCOME_CONFIRMATION": ("xác nhận thu nhập", "giấy xác nhận lương"),
}


class DocumentProcessingError(ValueError):
    """Raised when a document cannot be turned into text at all (unsupported
    format, empty upload, or scanned image with no OCR path available)."""


# ---------------------------------------------------------------------------
# 1. DocumentLoader — case-scoped raw bytes -> typed upload record
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class LoadedDocument:
    document_id: str
    file_name: str
    content_type: str
    raw_bytes: bytes
    checksum: str


def load_document(*, document_id: str, file_name: str, content_type: str, raw_bytes: bytes) -> LoadedDocument:
    if not raw_bytes:
        raise DocumentProcessingError("EMPTY_DOCUMENT")
    checksum = "sha256:" + hashlib.sha256(raw_bytes).hexdigest()
    return LoadedDocument(
        document_id=document_id,
        file_name=file_name,
        content_type=content_type,
        raw_bytes=raw_bytes,
        checksum=checksum,
    )


# ---------------------------------------------------------------------------
# 2. TextExtractor — bytes -> per-page plain text
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ExtractedText:
    pages: list[str]  # 1-indexed by position; pages[0] is page 1
    extraction_method: str  # "pdf_text" | "plain_text" | "csv" | "ocr" | "ocr_unavailable"
    ocr_available: bool = True

    @property
    def full_text(self) -> str:
        return "\n\n".join(
            f"===PAGE {index}===\n{text}" for index, text in enumerate(self.pages, start=1)
        )


def _suffix_of(file_name: str) -> str:
    return "." + file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""


def extract_text(doc: LoadedDocument) -> ExtractedText:
    suffix = _suffix_of(doc.file_name)

    if suffix in {".txt", ".md"}:
        text = doc.raw_bytes.decode("utf-8", errors="replace")
        return ExtractedText(pages=[text], extraction_method="plain_text")

    if suffix == ".csv":
        text_io = io.StringIO(doc.raw_bytes.decode("utf-8", errors="replace"))
        rows = list(csv.reader(text_io))
        rendered = "\n".join(" | ".join(cell.strip() for cell in row) for row in rows)
        return ExtractedText(pages=[rendered], extraction_method="csv")

    if suffix == ".pdf":
        try:
            import fitz  # PyMuPDF
        except ImportError as exc:  # pragma: no cover - environment guard
            raise DocumentProcessingError("PDF_LIBRARY_UNAVAILABLE") from exc
        pages: list[str] = []
        scanned_pages = 0
        with fitz.open(stream=doc.raw_bytes, filetype="pdf") as pdf:
            for page in pdf:
                text = page.get_text("text").strip()
                if not text:
                    scanned_pages += 1
                    text = _try_local_ocr_pdf_page(page)
                pages.append(text)
        if not pages:
            raise DocumentProcessingError("PDF_HAS_NO_PAGES")
        if scanned_pages and all(not p for p in pages):
            # No text layer anywhere and no local OCR engine installed.
            # Explicitly labelled degraded mode — never silently invent text.
            return ExtractedText(
                pages=["" for _ in pages],
                extraction_method="ocr_unavailable",
                ocr_available=False,
            )
        return ExtractedText(pages=pages, extraction_method="pdf_text" if scanned_pages == 0 else "ocr")

    if suffix in {".png", ".jpg", ".jpeg"}:
        text = _try_local_ocr_image(doc.raw_bytes)
        if text is None:
            return ExtractedText(pages=[""], extraction_method="ocr_unavailable", ocr_available=False)
        return ExtractedText(pages=[text], extraction_method="ocr")

    raise DocumentProcessingError("UNSUPPORTED_DOCUMENT_FORMAT")


def _try_local_ocr_image(raw_bytes: bytes) -> str | None:
    """Best-effort local OCR. Returns None (never raises) if pytesseract/PIL
    or the tesseract binary itself are not installed — the caller then marks
    the document ``ocr_unavailable`` instead of pretending OCR ran."""

    try:
        import pytesseract
        from PIL import Image

        image = Image.open(io.BytesIO(raw_bytes))
        text = pytesseract.image_to_string(image, lang="vie+eng")
        return text.strip() or None
    except Exception:  # pragma: no cover - depends on optional local binary
        return None


def _try_local_ocr_page(page) -> str:
    try:
        import pytesseract
        from PIL import Image

        pixmap = page.get_pixmap(dpi=200)
        image = Image.open(io.BytesIO(pixmap.tobytes("png")))
        return pytesseract.image_to_string(image, lang="vie+eng").strip()
    except Exception:  # pragma: no cover - depends on optional local binary
        return ""


_try_local_ocr_pdf_page = _try_local_ocr_page


# ---------------------------------------------------------------------------
# 3. DocumentClassifier — text -> DOCUMENT_TYPES member
# ---------------------------------------------------------------------------


class _ClassificationSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    document_type: str
    confidence: float = PydField(default=0.5, ge=0, le=1)


async def classify_document(text: str, *, llm: LLMProvider) -> tuple[str, str]:
    """Returns (document_type, method)."""

    lowered = text.lower()
    keyword_hit = _classify_by_keywords(lowered)

    result = await llm.complete_json(
        system=(
            "You classify Vietnamese bank loan-dossier documents. Reply with JSON "
            f"{{\"document_type\": one of {list(DOCUMENT_TYPES)}, \"confidence\": 0..1}}. "
            "Use OTHER if unsure. Never invent a type outside this list."
        ),
        user=text[:6000],
        schema=_ClassificationSchema,
    )
    if result is not None and result.document_type in DOCUMENT_TYPES:
        return result.document_type, "LLM"
    if keyword_hit is not None:
        return keyword_hit, "KEYWORD_FALLBACK"
    return "OTHER", "KEYWORD_FALLBACK"


def _classify_by_keywords(lowered_text: str) -> str | None:
    best_type: str | None = None
    best_score = 0
    for doc_type, keywords in _CLASSIFIER_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in lowered_text)
        if score > best_score:
            best_score = score
            best_type = doc_type
    return best_type


# ---------------------------------------------------------------------------
# 4. FieldExtractor — consolidated text -> candidate structured fields
# ---------------------------------------------------------------------------


def _normalize_month(raw: str | None) -> str | None:
    """Accept whatever date/month format the LLM copied verbatim from the
    source (DD/MM/YYYY, MM/YYYY, or already YYYY-MM) and normalize to
    YYYY-MM. Asking the LLM to only ever copy text (never reformat it) and
    doing the reformatting deterministically in Python avoids an entire
    class of "the model transformed the date wrong" failures."""

    if not raw:
        return None
    raw = raw.strip()
    if re.match(r"^\d{4}-(0[1-9]|1[0-2])$", raw):
        return raw
    match = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", raw)  # DD/MM/YYYY
    if match:
        _, month, year = match.groups()
        return f"{year}-{month}"
    match = re.match(r"^(\d{1,2})/(\d{4})$", raw)  # MM/YYYY
    if match:
        month, year = match.groups()
        return f"{year}-{int(month):02d}"
    return None


class _LLMTransaction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    month: str | None = None
    amount_digits: str | None = None
    source: str = ""
    quote: str | None = None

    def normalized_month(self) -> str | None:
        return _normalize_month(self.month)

    def is_usable(self) -> bool:
        return bool(self.normalized_month() and self.amount_digits and self.quote)


class _LLMVariableIncome(BaseModel):
    model_config = ConfigDict(extra="ignore")

    month: str | None = None
    amount_digits: str | None = None
    quote: str | None = None

    def normalized_month(self) -> str | None:
        return _normalize_month(self.month)

    def is_usable(self) -> bool:
        return bool(self.normalized_month() and self.amount_digits and self.quote)


class _LLMExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    customer_name: str | None = None
    customer_name_quote: str | None = None
    declared_income_digits: str | None = None
    declared_income_quote: str | None = None
    contract_salary_digits: str | None = None
    contract_salary_quote: str | None = None
    employer: str | None = None
    employer_quote: str | None = None
    contract_expiry_ddmmyyyy: str | None = None
    contract_expiry_quote: str | None = None
    currency: str = "VND"
    salary_transactions: list[_LLMTransaction] = PydField(default_factory=list)
    variable_income_records: list[_LLMVariableIncome] = PydField(default_factory=list)


_FIELD_EXTRACTION_SYSTEM_PROMPT = """\
You extract income-verification facts from Vietnamese bank loan documents
(loan application, employment contract, payslips, bank statement).

Rules (violating any of these makes your answer useless, so follow them exactly):
1. Every value you report MUST come with a `..._quote` field that is a
   VERBATIM substring of the provided text (same characters, you may trim
   surrounding whitespace but must not paraphrase, translate or reformat).
2. Amounts are reported as `..._digits`: the digits only, no currency
   symbol, no thousands separator (e.g. "24800000").
3. Dates are DD/MM/YYYY exactly as written in the source.
4. If a field is not explicitly present in the text, omit it (do not guess,
   do not compute, do not carry over a value from a different field).
5. Never invent salary_transactions or variable_income_records that are not
   backed by an explicit line/row in the text.
6. Use EXACTLY these JSON keys and no others: customer_name,
   customer_name_quote, declared_income_digits, declared_income_quote,
   contract_salary_digits, contract_salary_quote, employer, employer_quote,
   contract_expiry_ddmmyyyy, contract_expiry_quote, currency,
   salary_transactions (list of {month, amount_digits, source, quote}),
   variable_income_records (list of {month, amount_digits, quote}). Do not
   add a document_id, page, or any other key.
7. For "month" in salary_transactions/variable_income_records: COPY the
   date/month exactly as written next to that row (e.g. "05/01/2026" or
   "2026-01" or "01/2026") — do not convert or reformat it yourself, it
   will be parsed afterwards.
8. salary_transactions come from a BANK STATEMENT (money actually received
   into an account each month) — one entry per month/transaction row.
9. variable_income_records come from a PAYSLIP/payroll table and mean the
   non-fixed component of pay for that month — bonus, allowance ("phụ
   cấp"), performance pay, or similar — as distinct from the fixed base
   salary ("lương cơ bản"). If a payslip table has separate "lương cơ bản"
   and "phụ cấp"/variable columns, extract the phụ cấp/variable column
   value (with its own row as the quote), not the base salary and not the
   net-pay total.
Return JSON only, matching the given schema.
"""


def _normalize_for_match(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _quote_is_verbatim(quote: str | None, source_text: str) -> bool:
    if not quote:
        return False
    return _normalize_for_match(quote) in _normalize_for_match(source_text)


def _digits_appear_in_quote(digits: str | None, quote: str | None) -> bool:
    if not digits or not quote:
        return False
    quote_digits = re.sub(r"[^0-9]", "", quote)
    return digits in quote_digits


def _digits_appear_in_source_line(digits: str | None, quote: str | None, source_text: str) -> bool:
    """Looser anti-hallucination check for table rows: the model sometimes
    quotes only one cell of a row (e.g. the description) rather than the
    whole line. Accept the amount if it appears in a source line that also
    contains the (verbatim) quote — i.e. the same table row — rather than
    requiring both to be packed into a single quote string."""

    if not digits or not quote:
        return False
    if _digits_appear_in_quote(digits, quote):
        return True
    needle = _normalize_for_match(quote)
    for line in source_text.splitlines():
        normalized_line = _normalize_for_match(line)
        if needle and needle in normalized_line:
            line_digits = re.sub(r"[^0-9]", "", line)
            if digits in line_digits:
                return True
    return False


async def extract_fields_with_llm(
    documents_text: dict[str, str],
    *,
    llm: LLMProvider,
) -> tuple[_LLMExtraction | None, str]:
    """Returns (validated extraction or None, method label)."""

    combined = "\n\n".join(
        f"--- DOCUMENT {doc_id} ---\n{text}" for doc_id, text in documents_text.items()
    )
    raw = await llm.complete_json(
        system=_FIELD_EXTRACTION_SYSTEM_PROMPT,
        user=combined[:20000],
        schema=_LLMExtraction,
        max_tokens=4000,
    )
    if raw is None:
        return None, "LLM_UNAVAILABLE"

    full_text = "\n".join(documents_text.values())
    validated = _validate_llm_extraction(raw, full_text)
    return validated, "LLM_VALIDATED"


def _validate_llm_extraction(raw: _LLMExtraction, full_text: str) -> _LLMExtraction:
    """Drop any scalar field whose quote can't be found verbatim in the
    source text, and any amount whose digits don't appear in its own quote.
    This is the anti-hallucination gate — see module docstring."""

    def check_scalar(value: str | None, quote: str | None) -> tuple[str | None, str | None]:
        if value is not None and not _quote_is_verbatim(quote, full_text):
            return None, None
        return value, quote

    customer_name, customer_name_quote = check_scalar(raw.customer_name, raw.customer_name_quote)
    employer, employer_quote = check_scalar(raw.employer, raw.employer_quote)
    contract_expiry, contract_expiry_quote = check_scalar(
        raw.contract_expiry_ddmmyyyy, raw.contract_expiry_quote
    )

    declared_income_digits, declared_income_quote = raw.declared_income_digits, raw.declared_income_quote
    if declared_income_digits is not None and not (
        _quote_is_verbatim(declared_income_quote, full_text)
        and _digits_appear_in_quote(declared_income_digits, declared_income_quote)
    ):
        declared_income_digits, declared_income_quote = None, None

    contract_salary_digits, contract_salary_quote = raw.contract_salary_digits, raw.contract_salary_quote
    if contract_salary_digits is not None and not (
        _quote_is_verbatim(contract_salary_quote, full_text)
        and _digits_appear_in_quote(contract_salary_digits, contract_salary_quote)
    ):
        contract_salary_digits, contract_salary_quote = None, None

    valid_transactions = [
        tx
        for tx in raw.salary_transactions
        if tx.is_usable()
        and _quote_is_verbatim(tx.quote, full_text)
        and _digits_appear_in_source_line(tx.amount_digits, tx.quote, full_text)
    ]
    valid_variable = [
        rec
        for rec in raw.variable_income_records
        if rec.is_usable()
        and _quote_is_verbatim(rec.quote, full_text)
        and _digits_appear_in_source_line(rec.amount_digits, rec.quote, full_text)
    ]

    return _LLMExtraction(
        customer_name=customer_name,
        customer_name_quote=customer_name_quote,
        declared_income_digits=declared_income_digits,
        declared_income_quote=declared_income_quote,
        contract_salary_digits=contract_salary_digits,
        contract_salary_quote=contract_salary_quote,
        employer=employer,
        employer_quote=employer_quote,
        contract_expiry_ddmmyyyy=contract_expiry,
        contract_expiry_quote=contract_expiry_quote,
        currency=raw.currency or "VND",
        salary_transactions=valid_transactions,
        variable_income_records=valid_variable,
    )


# ---------------------------------------------------------------------------
# Deterministic regex fallback (best-effort; reuses MarkdownDocumentAgent's
# label patterns). Used when the LLM is unavailable or every field it
# proposed failed validation.
# ---------------------------------------------------------------------------

_LABEL_PATTERNS = {
    "customer_name": r"(?:Họ và tên|Họ tên|Tên khách hàng)\s*[:：]\s*([^\n]+)",
    "declared_income": r"(?:Thu nhập khai báo|Thu nhập hàng tháng)\s*[:：]\s*([^\n]+)",
    "employer": r"(?:Đơn vị công tác|Công ty|Nơi làm việc)\s*[:：]\s*([^\n]+)",
    "contract_salary": r"(?:Lương cơ bản(?: theo hợp đồng)?|Mức lương)\s*[:：]\s*([^\n]+)",
    "contract_expiry": r"(?:Ngày hết hạn|Hết hạn hợp đồng)\s*[:：]\s*(\d{2}/\d{2}/\d{4})",
}


def _regex_first_match(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return match.group(1).strip() if match else None


def _parse_vnd_digits(value: str | None) -> str | None:
    if value is None:
        return None
    digits = re.sub(r"[^0-9]", "", value)
    return digits or None


# Generic 4-column bank-statement row: | DD/MM/YYYY | description | source | amount |
_STATEMENT_ROW_PATTERN = re.compile(
    r"^\|\s*(?P<date>\d{2}/\d{2}/\d{4})\s*\|\s*(?P<description>[^|]+?)\s*\|"
    r"\s*(?P<source>[^|]+?)\s*\|\s*(?P<amount>[\d.,]+)\s*\|$",
    re.MULTILINE,
)
# Generic 5-column payslip row: | YYYY-MM | base | variable | deduction | net |
_PAYSLIP_ROW_PATTERN = re.compile(
    r"^\|\s*(?P<month>\d{4}-\d{2})\s*\|\s*(?P<base>[\d.,]+)\s*\|"
    r"\s*(?P<variable>[\d.,]+)\s*\|\s*(?P<deduction>[\d.,]+)\s*\|\s*(?P<net>[\d.,]+)\s*\|$",
    re.MULTILINE,
)


def extract_fields_with_regex(full_text: str) -> _LLMExtraction:
    """Deterministic fallback: same label patterns as MarkdownDocumentAgent,
    applied to arbitrary uploaded text. Quotes are the matched line itself,
    which is trivially verbatim, so this never fails validation. Also parses
    generic pipe-table rows for transactions/variable income so the pipeline
    can reach a real result with LLM_PROVIDER=mock (used by tests and by
    the 20 synthetic ground-truth cases), not just extract scalar fields."""

    def field(label: str) -> tuple[str | None, str | None]:
        match = re.search(rf"^.*{_LABEL_PATTERNS[label]}.*$", full_text, flags=re.IGNORECASE | re.MULTILINE)
        if not match:
            return None, None
        return match.group(1).strip(), match.group(0).strip()

    customer_name, customer_name_quote = field("customer_name")
    declared_raw, declared_income_quote = field("declared_income")
    employer, employer_quote = field("employer")
    contract_raw, contract_salary_quote = field("contract_salary")
    contract_expiry, contract_expiry_quote = field("contract_expiry")

    transactions = [
        _LLMTransaction(
            month=_normalize_month(match.group("date")),
            amount_digits=_parse_vnd_digits(match.group("amount")),
            source=match.group("source").strip(),
            quote=match.group(0).strip(),
        )
        for match in _STATEMENT_ROW_PATTERN.finditer(full_text)
    ]
    variable_records = [
        _LLMVariableIncome(
            month=match.group("month"),
            amount_digits=_parse_vnd_digits(match.group("variable")),
            quote=match.group(0).strip(),
        )
        for match in _PAYSLIP_ROW_PATTERN.finditer(full_text)
    ]

    return _LLMExtraction(
        customer_name=customer_name,
        customer_name_quote=customer_name_quote,
        declared_income_digits=_parse_vnd_digits(declared_raw),
        declared_income_quote=declared_income_quote,
        contract_salary_digits=_parse_vnd_digits(contract_raw),
        contract_salary_quote=contract_salary_quote,
        employer=employer,
        employer_quote=employer_quote,
        contract_expiry_ddmmyyyy=contract_expiry,
        contract_expiry_quote=contract_expiry_quote,
        currency="VND",
        salary_transactions=transactions,
        variable_income_records=variable_records,
    )


def merge_extractions(llm: _LLMExtraction | None, regex: _LLMExtraction) -> tuple[_LLMExtraction, dict[str, str]]:
    """Prefer LLM-validated values; fill gaps from the regex fallback.
    Returns the merged extraction plus a per-field method label for audit."""

    llm = llm or _LLMExtraction()
    methods: dict[str, str] = {}

    def pick(field_name: str, quote_field: str) -> tuple[str | None, str | None]:
        llm_value = getattr(llm, field_name)
        if llm_value is not None:
            methods[field_name] = "LLM_VALIDATED"
            return llm_value, getattr(llm, quote_field)
        regex_value = getattr(regex, field_name)
        if regex_value is not None:
            methods[field_name] = "REGEX_FALLBACK"
            return regex_value, getattr(regex, quote_field)
        methods[field_name] = "NOT_FOUND"
        return None, None

    customer_name, customer_name_quote = pick("customer_name", "customer_name_quote")
    declared, declared_quote = pick("declared_income_digits", "declared_income_quote")
    contract, contract_quote = pick("contract_salary_digits", "contract_salary_quote")
    employer, employer_quote = pick("employer", "employer_quote")
    expiry, expiry_quote = pick("contract_expiry_ddmmyyyy", "contract_expiry_quote")

    merged = _LLMExtraction(
        customer_name=customer_name,
        customer_name_quote=customer_name_quote,
        declared_income_digits=declared,
        declared_income_quote=declared_quote,
        contract_salary_digits=contract,
        contract_salary_quote=contract_quote,
        employer=employer,
        employer_quote=employer_quote,
        contract_expiry_ddmmyyyy=expiry,
        contract_expiry_quote=expiry_quote,
        currency=llm.currency or regex.currency,
        salary_transactions=llm.salary_transactions or regex.salary_transactions,
        variable_income_records=llm.variable_income_records or regex.variable_income_records,
    )
    if llm.salary_transactions:
        methods["salary_transactions"] = "LLM_VALIDATED"
    elif regex.salary_transactions:
        methods["salary_transactions"] = "REGEX_FALLBACK"
    else:
        methods["salary_transactions"] = "NOT_FOUND"
    if llm.variable_income_records:
        methods["variable_income_records"] = "LLM_VALIDATED"
    elif regex.variable_income_records:
        methods["variable_income_records"] = "REGEX_FALLBACK"
    else:
        methods["variable_income_records"] = "NOT_FOUND"
    return merged, methods


# ---------------------------------------------------------------------------
# 5. EvidenceLocator — merged extraction -> EvidenceCitation list + page numbers
# ---------------------------------------------------------------------------


def _page_number_for_quote(quote: str | None, pages: list[str]) -> int:
    if not quote:
        return 1
    needle = _normalize_for_match(quote)
    for index, page_text in enumerate(pages, start=1):
        if needle in _normalize_for_match(page_text):
            return index
    return 1


@dataclass(slots=True)
class ProcessedDocument:
    record: DocumentRecord
    document_type: str
    classification_method: str
    extracted_text: ExtractedText
    checksum: str


def build_extraction_result(
    processed_docs: list[ProcessedDocument],
    *,
    merged: _LLMExtraction,
    field_methods: dict[str, str],
) -> DocumentExtractionResult:
    """EvidenceLocator step: turn merged field values into typed
    ExtractedFields + EvidenceCitation, locating page numbers by scanning
    each document's pages for the field's verbatim quote."""

    docs_by_type = {doc.document_type: doc for doc in processed_docs}

    def locate(quote: str | None, prefer_types: tuple[str, ...]) -> ProcessedDocument | None:
        for doc_type in prefer_types:
            if doc_type in docs_by_type:
                return docs_by_type[doc_type]
        return processed_docs[0] if processed_docs else None

    evidence: list[EvidenceCitation] = []

    def add_evidence(evidence_id: str, quote: str | None, prefer_types: tuple[str, ...], location: str) -> str | None:
        if quote is None:
            return None
        doc = locate(quote, prefer_types)
        if doc is None:
            return None
        page = _page_number_for_quote(quote, doc.extracted_text.pages)
        evidence.append(
            EvidenceCitation(
                evidence_id=evidence_id,
                document_id=doc.record.document_id,
                document_name=doc.record.document_name,
                page_number=page,
                quote=quote,
                source_checksum=doc.checksum,
                location=location,
            )
        )
        return evidence_id

    add_evidence(
        "customer_name", merged.customer_name_quote,
        ("LOAN_APPLICATION", "ID_DOCUMENT"), "customer_name",
    )
    add_evidence(
        "declared_income", merged.declared_income_quote,
        ("LOAN_APPLICATION",), "declared_income",
    )
    add_evidence(
        "employer", merged.employer_quote,
        ("LOAN_APPLICATION", "EMPLOYMENT_CONTRACT"), "employer",
    )
    add_evidence(
        "contract_salary", merged.contract_salary_quote,
        ("EMPLOYMENT_CONTRACT",), "contract_salary",
    )
    add_evidence(
        "contract_expiry", merged.contract_expiry_quote,
        ("EMPLOYMENT_CONTRACT",), "contract_expiry",
    )

    salary_transactions: list[SalaryTransaction] = []
    statement_doc = docs_by_type.get("BANK_STATEMENT") or (processed_docs[0] if processed_docs else None)
    for index, tx in enumerate(merged.salary_transactions):
        month = tx.normalized_month()
        if month is None:
            continue
        amount = Decimal(tx.amount_digits)
        evidence_id = f"tx_{month.replace('-', '_')}_{index}"
        if statement_doc is not None:
            page = _page_number_for_quote(tx.quote, statement_doc.extracted_text.pages)
            evidence.append(
                EvidenceCitation(
                    evidence_id=evidence_id,
                    document_id=statement_doc.record.document_id,
                    document_name=statement_doc.record.document_name,
                    page_number=page,
                    quote=tx.quote,
                    source_checksum=statement_doc.checksum,
                    location=f"transaction:{month}",
                )
            )
        salary_transactions.append(
            SalaryTransaction(
                month=month,
                amount=amount,
                currency=merged.currency,
                source=tx.source or "UNKNOWN",
                evidence_id=evidence_id,
            )
        )

    variable_income_records: list[VariableIncomeRecord] = []
    payslip_doc = docs_by_type.get("PAYSLIP_BUNDLE") or (processed_docs[0] if processed_docs else None)
    for index, rec in enumerate(merged.variable_income_records):
        month = rec.normalized_month()
        if month is None:
            continue
        amount = Decimal(rec.amount_digits)
        evidence_id = f"variable_{month.replace('-', '_')}_{index}"
        if payslip_doc is not None:
            page = _page_number_for_quote(rec.quote, payslip_doc.extracted_text.pages)
            evidence.append(
                EvidenceCitation(
                    evidence_id=evidence_id,
                    document_id=payslip_doc.record.document_id,
                    document_name=payslip_doc.record.document_name,
                    page_number=page,
                    quote=rec.quote,
                    source_checksum=payslip_doc.checksum,
                    location=f"variable_income:{month}",
                )
            )
        variable_income_records.append(
            VariableIncomeRecord(
                month=month,
                amount=amount,
                currency=merged.currency,
                evidence_id=evidence_id,
            )
        )

    missing = [
        name
        for name, method in field_methods.items()
        if method == "NOT_FOUND" and name in ("customer_name", "declared_income_digits", "contract_salary_digits", "employer", "contract_expiry_ddmmyyyy")
    ]
    if missing or merged.customer_name is None or merged.declared_income_digits is None:
        return DocumentExtractionResult(
            status=ComponentStatus.MISSING_DATA,
            evidence=evidence,
            reason_code="CORE_INCOME_FIELDS_INCOMPLETE:" + ",".join(missing) if missing else "CORE_INCOME_FIELDS_INCOMPLETE",
        )

    contract_expiry_date = None
    if merged.contract_expiry_ddmmyyyy:
        try:
            contract_expiry_date = datetime.strptime(merged.contract_expiry_ddmmyyyy, "%d/%m/%Y").date()
        except ValueError:
            contract_expiry_date = None

    try:
        declared_income = Decimal(merged.declared_income_digits)
        contract_salary = Decimal(merged.contract_salary_digits) if merged.contract_salary_digits else None
    except (InvalidOperation, TypeError):
        return DocumentExtractionResult(
            status=ComponentStatus.MISSING_DATA,
            evidence=evidence,
            reason_code="AMOUNT_PARSE_FAILED",
        )

    extraction_confidence = _compute_confidence(field_methods)

    return DocumentExtractionResult(
        status=ComponentStatus.SUCCESS,
        extracted_fields=ExtractedFields(
            customer_name=merged.customer_name,
            declared_income=declared_income,
            contract_salary=contract_salary,
            currency=merged.currency,
            employer=merged.employer,
            contract_expiry=contract_expiry_date,
            salary_transactions=salary_transactions,
            variable_income_records=variable_income_records,
            missing_documents=[],
            extraction_confidence=extraction_confidence,
        ),
        evidence=evidence,
    )


def _compute_confidence(field_methods: dict[str, str]) -> float:
    """Deterministic, auditable confidence score — NOT an LLM self-report.
    1.0 if every field came from an LLM-validated verbatim quote, lower if
    some fields fell back to regex, lower still if any are missing."""

    weights = {"LLM_VALIDATED": 1.0, "REGEX_FALLBACK": 0.7, "NOT_FOUND": 0.0}
    scored = [weights.get(method, 0.0) for method in field_methods.values()]
    return round(sum(scored) / len(scored), 2) if scored else 0.0

