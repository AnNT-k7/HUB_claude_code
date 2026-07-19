"""Policy namespace retrieval with exact citations and deterministic application."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Protocol

from app.services.namespace_rag import (
    DEFAULT_CORPUS_PATH,
    NamespaceHit,
    NamespaceQuery,
    RagNamespace,
    search_namespace,
)
from app.tools.income_calculator import (
    CALCULATION_VERSION,
    CalculationInputError,
    calculate_average_variable_income,
    calculate_eligible_income,
    calculate_income_metrics,
)

from .income_agent import select_recognized_transactions
from .state import (
    CaseContext,
    ComponentStatus,
    PolicyCitation,
    PolicyResult,
)


class PolicyRetriever(Protocol):
    async def retrieve(self, query: NamespaceQuery) -> list[NamespaceHit]: ...


@dataclass(frozen=True, slots=True)
class PolicyAgentConfig:
    allowed_scopes: tuple[str, ...] = ("GLOBAL_POLICY", "REVIEW_ONLY")
    accepted_approval_statuses: tuple[str, ...] = (
        "APPROVED",
        "APPROVED_FOR_DEMO",
    )
    required_rule_ids: tuple[str, ...] = (
        "IVP-1",
        "IVP-2",
        "IVP-3",
        "IVP-4",
        "IVP-5",
        "IVP-6",
    )
    as_of_date: date | None = None


class NamespacePolicyRetriever:
    """Async adapter around the shared 512-dimensional namespace retriever."""

    def __init__(self, *, corpus_path: Path = DEFAULT_CORPUS_PATH) -> None:
        self.corpus_path = corpus_path

    async def retrieve(self, query: NamespaceQuery) -> list[NamespaceHit]:
        return await asyncio.to_thread(
            search_namespace,
            query,
            corpus_path=self.corpus_path,
        )


def _parse_integer_rule_value(content: str, pattern: str) -> int | None:
    match = re.search(pattern, content, flags=re.IGNORECASE | re.DOTALL)
    return int(re.sub(r"[^0-9]", "", match.group(1))) if match else None


def _extract_quote(content: str) -> str:
    match = re.search(
        r"\*\*Trích dẫn thử nghiệm:\*\*\s*(?:“([^”]+)”|\"([^\"]+)\")",
        content,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if match:
        return re.sub(r"\s+", " ", match.group(1) or match.group(2)).strip()
    for line in content.splitlines():
        cleaned = re.sub(r"[`*_#]", "", line).strip(" -")
        if cleaned and not cleaned.startswith(("Section ID:", "Chunk type:")):
            return cleaned
    raise ValueError("Policy chunk has no citable text.")


class PolicyAgent:
    """Retrieve complete policy rules and apply only explicit numeric parameters."""

    def __init__(
        self,
        retriever: PolicyRetriever | None = None,
        *,
        config: PolicyAgentConfig | None = None,
    ) -> None:
        self.retriever = retriever or NamespacePolicyRetriever()
        self.config = config or PolicyAgentConfig()

    async def __call__(self, context: CaseContext) -> PolicyResult:
        extracted = context.extracted_fields
        if extracted is None:
            return PolicyResult(
                status=ComponentStatus.MISSING_DATA,
                reason_code="EXTRACTED_FIELDS_NOT_AVAILABLE",
            )
        hits = await self.retriever.retrieve(
            NamespaceQuery(
                query_text=(
                    "Quy định xác minh thu nhập vay tín chấp: kỳ sao kê, nhận diện "
                    "lương, công thức thu nhập đủ điều kiện, bất thường, hợp đồng và "
                    "chênh lệch thu nhập khai báo"
                ),
                namespace=RagNamespace.POLICY,
                domain="INCOME_VERIFICATION",
                product="UNSECURED_PERSONAL_LOAN",
                top_k=10,
                chunk_types=["POLICY_RULE"],
                allowed_scopes=list(self.config.allowed_scopes),
                approval_statuses=list(self.config.accepted_approval_statuses),
                as_of_date=self.config.as_of_date or date.today(),
            )
        )
        accepted = self._accepted_hits(hits)
        by_rule: dict[str, list[NamespaceHit]] = {}
        for hit in accepted:
            if hit.section_id in self.config.required_rule_ids:
                by_rule.setdefault(hit.section_id, []).append(hit)

        conflicts = [
            rule_id
            for rule_id, rule_hits in by_rule.items()
            if len({item.content for item in rule_hits}) > 1
        ]
        if conflicts:
            return PolicyResult(
                status=ComponentStatus.CONFLICT,
                conflicts=sorted(conflicts),
                reason_code="CONFLICTING_POLICY_RULES",
            )
        missing_rules = sorted(set(self.config.required_rule_ids) - set(by_rule))
        if missing_rules:
            return PolicyResult(
                status=ComponentStatus.NOT_FOUND,
                reason_code="POLICY_RULES_NOT_FOUND:" + ",".join(missing_rules),
            )

        selected = {rule_id: rule_hits[0] for rule_id, rule_hits in by_rule.items()}
        statement_months = _parse_integer_rule_value(
            selected["IVP-1"].content,
            r"sao kê của\s+0?(\d+)\s+tháng",
        )
        variable_cap = _parse_integer_rule_value(
            selected["IVP-3"].content,
            r"tối đa\s+([\d.]+)\s*VND",
        )
        minimum_variable_periods = _parse_integer_rule_value(
            selected["IVP-3"].content,
            r"ít nhất\s+0?(\d+)\s+trong\s+0?\d+\s+tháng",
        )
        if (
            statement_months is None
            or variable_cap is None
            or minimum_variable_periods is None
        ):
            return PolicyResult(
                status=ComponentStatus.MANUAL_REVIEW,
                reason_code="POLICY_PARAMETER_NOT_PARSEABLE",
            )
        variable_cap_decimal = Decimal(variable_cap)

        citations: list[PolicyCitation] = []
        try:
            for rule_id in self.config.required_rule_ids:
                hit = selected[rule_id]
                if hit.effective_date is None:
                    raise ValueError("Policy effective date is required.")
                citations.append(
                    PolicyCitation(
                        document_name=hit.document_name,
                        page_number=hit.page_number,
                        section_id=hit.section_id,
                        effective_date=hit.effective_date,
                        quote=_extract_quote(hit.content),
                        chunk_id=hit.chunk_id,
                    )
                )
        except ValueError:
            return PolicyResult(
                status=ComponentStatus.MANUAL_REVIEW,
                reason_code="POLICY_CITATION_INCOMPLETE",
            )

        if extracted.contract_salary is None:
            return PolicyResult(
                status=ComponentStatus.MISSING_DATA,
                required_documents=["EMPLOYMENT_CONTRACT"],
                required_statement_months=statement_months,
                applied_rule_ids=list(self.config.required_rule_ids),
                citations=citations,
                reason_code="CONTRACT_SALARY_NOT_AVAILABLE",
            )
        recognized, _ = select_recognized_transactions(context)
        try:
            metrics = calculate_income_metrics(recognized)
            # A dossier that declares no variable income does not fail the
            # positive-period rule; it contributes exactly zero. The minimum
            # positive-period requirement applies only when variable income is
            # claimed and included in eligible income.
            if extracted.variable_income_records and not any(
                record.amount > 0 for record in extracted.variable_income_records
            ):
                variable_average = Decimal("0")
                variable_fact_ids = tuple(
                    record.evidence_id for record in extracted.variable_income_records
                )
            else:
                variable_average, variable_fact_ids = calculate_average_variable_income(
                    extracted.variable_income_records,
                    required_periods=statement_months,
                    minimum_positive_periods=minimum_variable_periods,
                )
            eligible_income = calculate_eligible_income(
                average_income=metrics.average_income,
                contract_salary=extracted.contract_salary,
                average_documented_variable_income=variable_average,
                variable_income_cap=variable_cap_decimal,
            )
        except CalculationInputError:
            return PolicyResult(
                status=ComponentStatus.MANUAL_REVIEW,
                required_statement_months=statement_months,
                applied_rule_ids=list(self.config.required_rule_ids),
                citations=citations,
                reason_code="ELIGIBLE_INCOME_INPUTS_INVALID",
            )

        return PolicyResult(
            status=ComponentStatus.SUCCESS,
            eligible_income=eligible_income,
            currency=metrics.currency,
            required_documents=[
                "BANK_STATEMENT",
                "EMPLOYMENT_CONTRACT",
                "PAYSLIP_BUNDLE",
            ],
            required_statement_months=statement_months,
            applied_rule_ids=list(self.config.required_rule_ids),
            citations=citations,
            average_documented_variable_income=variable_average,
            variable_income_cap=variable_cap_decimal,
            calculation_version=CALCULATION_VERSION,
            input_fact_ids=list(metrics.input_fact_ids) + list(variable_fact_ids),
        )

    def _accepted_hits(self, hits: list[NamespaceHit]) -> list[NamespaceHit]:
        as_of = self.config.as_of_date or date.today()
        return [
            hit
            for hit in hits
            if hit.indexing_scope in self.config.allowed_scopes
            and hit.domain == "INCOME_VERIFICATION"
            and hit.product == "UNSECURED_PERSONAL_LOAN"
            and hit.approval_status in self.config.accepted_approval_statuses
            and hit.effective_date is not None
            and hit.effective_date <= as_of
            and (hit.expiry_date is None or hit.expiry_date >= as_of)
        ]
