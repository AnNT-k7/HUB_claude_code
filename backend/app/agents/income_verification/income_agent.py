"""Evidence-bound income classification and deterministic analysis agent."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal

from app.tools.income_calculator import (
    CalculationInputError,
    calculate_income_metrics,
)

from .state import (
    CaseContext,
    ComponentStatus,
    IncomeAnalysisResult,
    SalaryTransaction,
)


_CORPORATE_STOP_WORDS = {
    "cong",
    "ty",
    "cty",
    "tnhh",
    "co",
    "ltd",
    "corporation",
}


@dataclass(frozen=True, slots=True)
class IncomeAgentConfig:
    anomaly_threshold: Decimal = Decimal("0.20")
    minimum_source_token_overlap: Decimal = Decimal("0.60")


def _tokens(value: str) -> list[str]:
    ascii_value = "".join(
        character
        for character in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(character)
    )
    return [
        token
        for token in re.findall(r"[a-z0-9]+", ascii_value.lower())
        if token not in _CORPORATE_STOP_WORDS
    ]


def source_matches_employer(
    source: str,
    employer: str,
    *,
    minimum_overlap: Decimal = Decimal("0.60"),
) -> bool:
    """Match normalized employer aliases without relying on an LLM decision."""

    source_tokens = set(_tokens(source))
    employer_tokens = set(_tokens(employer))
    if not source_tokens or not employer_tokens:
        return False
    if source_tokens <= employer_tokens or employer_tokens <= source_tokens:
        return True
    overlap = Decimal(len(source_tokens & employer_tokens)) / Decimal(
        min(len(source_tokens), len(employer_tokens))
    )
    return overlap >= minimum_overlap


def select_recognized_transactions(
    context: CaseContext,
    *,
    config: IncomeAgentConfig | None = None,
) -> tuple[list[SalaryTransaction], dict[str, str]]:
    """Classify extracted credits using employer source and evidence integrity."""

    rules = config or IncomeAgentConfig()
    extracted = context.extracted_fields
    if extracted is None or not extracted.employer:
        return [], {}
    valid_evidence_ids = {item.evidence_id for item in context.evidence}
    recognized: list[SalaryTransaction] = []
    excluded: dict[str, str] = {}
    for transaction in extracted.salary_transactions:
        if transaction.evidence_id not in valid_evidence_ids:
            excluded[transaction.evidence_id] = "EVIDENCE_NOT_FOUND"
        elif not source_matches_employer(
            transaction.source,
            extracted.employer,
            minimum_overlap=rules.minimum_source_token_overlap,
        ):
            excluded[transaction.evidence_id] = "SOURCE_NOT_MATCHED_TO_EMPLOYER"
        else:
            recognized.append(transaction)
    return recognized, excluded


class IncomeAnalysisAgent:
    """Analyze extracted transactions while preserving exclusions and lineage."""

    def __init__(self, *, config: IncomeAgentConfig | None = None) -> None:
        self.config = config or IncomeAgentConfig()

    async def __call__(self, context: CaseContext) -> IncomeAnalysisResult:
        extracted = context.extracted_fields
        if extracted is None:
            return IncomeAnalysisResult(
                status=ComponentStatus.MISSING_DATA,
                reason_code="EXTRACTED_FIELDS_NOT_AVAILABLE",
            )
        if not extracted.employer:
            return IncomeAnalysisResult(
                status=ComponentStatus.MISSING_DATA,
                reason_code="EMPLOYER_NOT_AVAILABLE",
            )
        if not extracted.salary_transactions:
            return IncomeAnalysisResult(
                status=ComponentStatus.MISSING_DATA,
                reason_code="TRANSACTIONS_NOT_AVAILABLE",
            )

        recognized, excluded = select_recognized_transactions(
            context,
            config=self.config,
        )
        if not recognized:
            return IncomeAnalysisResult(
                status=ComponentStatus.MANUAL_REVIEW,
                excluded_evidence_reasons=excluded,
                reason_code="NO_RECOGNIZED_SALARY_TRANSACTIONS",
            )
        try:
            calculation = calculate_income_metrics(
                recognized,
                anomaly_threshold=self.config.anomaly_threshold,
            )
        except CalculationInputError:
            return IncomeAnalysisResult(
                status=ComponentStatus.MANUAL_REVIEW,
                recognized_evidence_ids=[item.evidence_id for item in recognized],
                excluded_evidence_reasons=excluded,
                input_fact_ids=[item.evidence_id for item in recognized],
                reason_code="AMBIGUOUS_INCOME_INPUTS",
            )

        return IncomeAnalysisResult(
            status=ComponentStatus.SUCCESS,
            average_income=calculation.average_income,
            variation_ratio=calculation.variation_ratio,
            period_count=calculation.period_count,
            currency=calculation.currency,
            recognized_evidence_ids=list(calculation.input_fact_ids),
            excluded_evidence_reasons=excluded,
            calculation_version=calculation.calculation_version,
            input_fact_ids=list(calculation.input_fact_ids),
            anomalies=list(calculation.anomalies),
        )
