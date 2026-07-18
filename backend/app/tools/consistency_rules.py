"""Deterministic cross-check rules for income verification."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from app.agents.income_verification.state import (
    ExtractedFields,
    Finding,
    FindingSeverity,
    IncomeAnalysisResult,
    PolicyResult,
)


@dataclass(frozen=True, slots=True)
class ConsistencyRuleConfig:
    """Versioned thresholds used by deterministic consistency checks."""

    rule_version: str = "consistency-rules-v1"
    warning_difference_ratio: Decimal = Decimal("0.10")
    critical_difference_ratio: Decimal = Decimal("0.30")


def _stable_finding_id(case_id: str, code: str, discriminator: str = "") -> str:
    return str(uuid5(NAMESPACE_URL, f"income-verification:{case_id}:{code}:{discriminator}"))


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    ascii_value = "".join(
        character
        for character in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9]+", " ", ascii_value.lower()).strip()


def _organization_matches(left: str, right: str) -> bool:
    stop_words = {"cong", "ty", "cty", "tnhh", "co", "ltd"}
    left_tokens = set(_normalize_text(left).split()) - stop_words
    right_tokens = set(_normalize_text(right).split()) - stop_words
    if not left_tokens or not right_tokens:
        return False
    if left_tokens <= right_tokens or right_tokens <= left_tokens:
        return True
    return len(left_tokens & right_tokens) / min(len(left_tokens), len(right_tokens)) >= 0.6


def _difference_ratio(left: Decimal, right: Decimal) -> Decimal:
    denominator = max(abs(left), abs(right))
    return Decimal("0") if denominator == 0 else abs(left - right) / denominator


def _severity_for_ratio(
    ratio: Decimal, config: ConsistencyRuleConfig
) -> FindingSeverity | None:
    if ratio >= config.critical_difference_ratio:
        return FindingSeverity.CRITICAL
    if ratio >= config.warning_difference_ratio:
        return FindingSeverity.WARNING
    return None


def evaluate_consistency(
    *,
    case_id: str,
    extracted: ExtractedFields,
    income: IncomeAnalysisResult,
    policy: PolicyResult,
    valid_evidence_ids: set[str] | None = None,
    config: ConsistencyRuleConfig | None = None,
) -> list[Finding]:
    """Return stable findings from typed facts without making a credit decision."""

    rules = config or ConsistencyRuleConfig()
    findings: list[Finding] = []

    def add(
        code: str,
        severity: FindingSeverity,
        message: str,
        *,
        discriminator: str = "",
        evidence_ids: list[str] | None = None,
        source_values: dict[str, str | int | float | bool | None] | None = None,
    ) -> None:
        findings.append(
            Finding(
                finding_id=_stable_finding_id(case_id, code, discriminator),
                code=code,
                severity=severity,
                message=message,
                evidence_ids=evidence_ids or [],
                source_values=source_values or {},
                rule_version=rules.rule_version,
            )
        )

    comparisons = (
        ("DECLARED_VS_AVERAGE_MISMATCH", "declared_income", extracted.declared_income, "average_income", income.average_income),
        ("DECLARED_VS_ELIGIBLE_MISMATCH", "declared_income", extracted.declared_income, "eligible_income", policy.eligible_income),
        ("CONTRACT_VS_AVERAGE_MISMATCH", "contract_salary", extracted.contract_salary, "average_income", income.average_income),
    )
    for code, left_name, left, right_name, right in comparisons:
        if left is None or right is None:
            continue
        ratio = _difference_ratio(left, right)
        severity = _severity_for_ratio(ratio, rules)
        if severity is not None:
            add(
                code,
                severity,
                f"{left_name} differs materially from {right_name}.",
                evidence_ids=income.recognized_evidence_ids,
                source_values={
                    left_name: str(left),
                    right_name: str(right),
                    "difference_ratio": str(ratio.quantize(Decimal("0.0001"))),
                },
            )

    currencies = {
        value
        for value in (extracted.currency, income.currency, policy.currency)
        if value is not None
    }
    if len(currencies) > 1:
        add(
            "CURRENCY_MISMATCH",
            FindingSeverity.CRITICAL,
            "Income sources and policy result use different currencies.",
            source_values={"currencies": ",".join(sorted(currencies))},
        )

    recognized_sources = {
        transaction.source
        for transaction in extracted.salary_transactions
        if transaction.evidence_id in income.recognized_evidence_ids
    }
    if extracted.employer and recognized_sources and not any(
        _organization_matches(extracted.employer, source)
        for source in recognized_sources
    ):
        add(
            "EMPLOYER_SOURCE_MISMATCH",
            FindingSeverity.WARNING,
            "Declared employer does not match recognized salary transaction sources.",
            evidence_ids=income.recognized_evidence_ids,
            source_values={
                "employer": extracted.employer,
                "recognized_sources": ",".join(sorted(recognized_sources)),
            },
        )

    for anomaly in income.anomalies:
        add(
            "INCOME_PERIOD_ANOMALY",
            FindingSeverity.WARNING,
            "A salary period differs from the deterministic reference and requires review.",
            discriminator=anomaly.month or anomaly.code,
            evidence_ids=anomaly.evidence_ids,
            source_values={
                "month": anomaly.month,
                "amount": str(anomaly.amount) if anomaly.amount is not None else None,
                "deviation_ratio": (
                    str(anomaly.deviation_ratio)
                    if anomaly.deviation_ratio is not None
                    else None
                ),
                "anomaly_code": anomaly.code,
            },
        )

    for document_type in sorted(set(extracted.missing_documents)):
        add(
            "MISSING_REQUIRED_DOCUMENT",
            FindingSeverity.WARNING,
            f"Required supporting document is missing: {document_type}.",
            discriminator=document_type,
            source_values={"document_type": document_type},
        )

    if policy.required_statement_months is not None and (
        income.period_count < policy.required_statement_months
    ):
        add(
            "INSUFFICIENT_STATEMENT_PERIOD",
            FindingSeverity.CRITICAL,
            "Available salary history is shorter than the policy requirement.",
            evidence_ids=income.recognized_evidence_ids,
            source_values={
                "available_months": income.period_count,
                "required_months": policy.required_statement_months,
            },
        )

    if policy.status.value == "SUCCESS" and not policy.citations:
        add(
            "POLICY_CITATION_MISSING",
            FindingSeverity.CRITICAL,
            "Policy result has no traceable policy citation.",
        )

    if not income.calculation_version or not income.input_fact_ids:
        add(
            "CALCULATION_LINEAGE_MISSING",
            FindingSeverity.CRITICAL,
            "Income calculation does not include complete versioned input lineage.",
        )

    if valid_evidence_ids is not None:
        referenced_evidence_ids = set(income.recognized_evidence_ids).union(
            transaction.evidence_id for transaction in extracted.salary_transactions
        )
        referenced_evidence_ids.update(
            record.evidence_id for record in extracted.variable_income_records
        )
        unresolved_evidence_ids = sorted(referenced_evidence_ids - valid_evidence_ids)
        if unresolved_evidence_ids:
            add(
                "UNRESOLVED_EVIDENCE_REFERENCE",
                FindingSeverity.CRITICAL,
                "One or more income facts reference evidence that is not in the case.",
                evidence_ids=unresolved_evidence_ids,
                source_values={
                    "unresolved_evidence_ids": ",".join(unresolved_evidence_ids)
                },
            )

    return sorted(findings, key=lambda item: (item.severity.value, item.code, item.finding_id))


def has_material_findings(findings: list[Finding]) -> bool:
    """Critical findings require a specialist to resolve the case manually."""

    return any(finding.severity is FindingSeverity.CRITICAL for finding in findings)
