"""Deterministic income calculations with auditable input lineage."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from app.agents.income_verification.state import (
    IncomeAnomaly,
    SalaryTransaction,
    VariableIncomeRecord,
)


CALCULATION_VERSION = "income-calculator-v1"
DEFAULT_ROUNDING_UNIT = Decimal("1000")


class CalculationInputError(ValueError):
    """Raised when deterministic calculation inputs are incomplete or ambiguous."""


@dataclass(frozen=True, slots=True)
class IncomeCalculation:
    average_income: Decimal
    variation_ratio: Decimal
    period_count: int
    currency: str
    input_fact_ids: tuple[str, ...]
    anomalies: tuple[IncomeAnomaly, ...]
    calculation_version: str = CALCULATION_VERSION


def round_to_unit(
    value: Decimal,
    unit: Decimal = DEFAULT_ROUNDING_UNIT,
) -> Decimal:
    """Round a non-negative amount to the nearest configured monetary unit."""

    if value < 0:
        raise CalculationInputError("Income amounts cannot be negative.")
    if unit <= 0:
        raise CalculationInputError("Rounding unit must be positive.")
    return (value / unit).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * unit


def _median(values: list[Decimal]) -> Decimal:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / Decimal("2")


def calculate_income_metrics(
    transactions: list[SalaryTransaction],
    *,
    anomaly_threshold: Decimal = Decimal("0.20"),
    rounding_unit: Decimal = DEFAULT_ROUNDING_UNIT,
) -> IncomeCalculation:
    """Calculate average, dispersion and median-based anomalies deterministically."""

    if not transactions:
        raise CalculationInputError("At least one recognized salary transaction is required.")
    if anomaly_threshold < 0:
        raise CalculationInputError("Anomaly threshold cannot be negative.")

    months = [item.month for item in transactions]
    if len(months) != len(set(months)):
        raise CalculationInputError("Only one recognized salary transaction per month is allowed.")
    evidence_ids = [item.evidence_id for item in transactions]
    if len(evidence_ids) != len(set(evidence_ids)):
        raise CalculationInputError("Income evidence identifiers must be unique.")
    currencies = {item.currency for item in transactions}
    if len(currencies) != 1:
        raise CalculationInputError("All salary transactions must use one currency.")

    ordered = sorted(transactions, key=lambda item: (item.month, item.evidence_id))
    amounts = [item.amount for item in ordered]
    raw_average = sum(amounts, Decimal("0")) / Decimal(len(amounts))
    if raw_average == 0:
        variation_ratio = Decimal("0")
    else:
        variation_ratio = ((max(amounts) - min(amounts)) / raw_average).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )

    reference = _median(amounts)
    anomalies: list[IncomeAnomaly] = []
    if reference > 0:
        for transaction in ordered:
            deviation = ((transaction.amount - reference) / reference).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            )
            if abs(deviation) > anomaly_threshold:
                anomalies.append(
                    IncomeAnomaly(
                        code=(
                            "INCOME_BELOW_REFERENCE"
                            if deviation < 0
                            else "INCOME_ABOVE_REFERENCE"
                        ),
                        month=transaction.month,
                        amount=transaction.amount,
                        deviation_ratio=deviation,
                        evidence_ids=[transaction.evidence_id],
                    )
                )

    return IncomeCalculation(
        average_income=round_to_unit(raw_average, rounding_unit),
        variation_ratio=variation_ratio,
        period_count=len(ordered),
        currency=next(iter(currencies)),
        input_fact_ids=tuple(item.evidence_id for item in ordered),
        anomalies=tuple(anomalies),
    )


def calculate_eligible_income(
    *,
    average_income: Decimal,
    contract_salary: Decimal,
    average_documented_variable_income: Decimal = Decimal("0"),
    variable_income_cap: Decimal = Decimal("0"),
    rounding_unit: Decimal = DEFAULT_ROUNDING_UNIT,
) -> Decimal:
    """Apply the policy formula using explicit, non-negative numeric inputs."""

    values = (
        average_income,
        contract_salary,
        average_documented_variable_income,
        variable_income_cap,
    )
    if any(value < 0 for value in values):
        raise CalculationInputError("Eligible-income inputs cannot be negative.")
    contract_limit = contract_salary + min(
        average_documented_variable_income,
        variable_income_cap,
    )
    return round_to_unit(min(average_income, contract_limit), rounding_unit)


def calculate_average_variable_income(
    records: list[VariableIncomeRecord],
    *,
    required_periods: int,
    minimum_positive_periods: int,
    rounding_unit: Decimal = DEFAULT_ROUNDING_UNIT,
) -> tuple[Decimal, tuple[str, ...]]:
    """Average documented variable income across the complete required period."""

    if required_periods < 1 or minimum_positive_periods < 0:
        raise CalculationInputError("Variable-income period requirements are invalid.")
    if len(records) != required_periods:
        raise CalculationInputError("Variable-income records must cover every required period.")
    months = [record.month for record in records]
    if len(months) != len(set(months)):
        raise CalculationInputError("Variable-income periods must be unique.")
    evidence_ids = [record.evidence_id for record in records]
    if len(evidence_ids) != len(set(evidence_ids)):
        raise CalculationInputError("Variable-income evidence identifiers must be unique.")
    if len({record.currency for record in records}) != 1:
        raise CalculationInputError("Variable-income records must use one currency.")
    if sum(record.amount > 0 for record in records) < minimum_positive_periods:
        raise CalculationInputError("Variable income does not meet the documented-period rule.")
    average = sum((record.amount for record in records), Decimal("0")) / Decimal(
        required_periods
    )
    ordered = sorted(records, key=lambda record: (record.month, record.evidence_id))
    return round_to_unit(average, rounding_unit), tuple(
        record.evidence_id for record in ordered
    )
