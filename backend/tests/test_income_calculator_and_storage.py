"""Deterministic calculator and case-scoped storage edge tests."""

from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agents.income_verification.state import SalaryTransaction, VariableIncomeRecord  # noqa: E402
from app.services.storage import CaseScopedDocumentStore, DocumentStorageError  # noqa: E402
from app.tools.income_calculator import (  # noqa: E402
    CalculationInputError,
    calculate_average_variable_income,
    calculate_income_metrics,
    calculate_eligible_income,
)


def salary(month: str, amount: str, evidence_id: str, currency: str = "VND") -> SalaryTransaction:
    return SalaryTransaction(
        month=month,
        amount=Decimal(amount),
        currency=currency,
        source="EMPLOYER",
        evidence_id=evidence_id,
    )


class CalculatorAndStorageTests(unittest.TestCase):
    def test_rounding_boundary_and_reproducible_lineage(self) -> None:
        transactions = [
            salary("2026-01", "1000500", "ev-1"),
            salary("2026-02", "1000500", "ev-2"),
        ]
        result = calculate_income_metrics(transactions)
        self.assertEqual(result.average_income, Decimal("1001000"))
        self.assertEqual(result.input_fact_ids, ("ev-1", "ev-2"))
        self.assertEqual(result.calculation_version, "income-calculator-v1")

    def test_duplicate_month_and_mixed_currency_are_rejected(self) -> None:
        with self.assertRaises(CalculationInputError):
            calculate_income_metrics(
                [salary("2026-01", "1000000", "ev-1"), salary("2026-01", "2000000", "ev-2")]
            )
        with self.assertRaises(CalculationInputError):
            calculate_income_metrics(
                [salary("2026-01", "1000000", "ev-1"), salary("2026-02", "2000000", "ev-2", "USD")]
            )

    def test_variable_income_requires_documented_periods(self) -> None:
        records = [
            VariableIncomeRecord(month=f"2026-0{month}", amount=Decimal("1000000"), currency="VND", evidence_id=f"var-{month}")
            for month in range(1, 7)
        ]
        average, facts = calculate_average_variable_income(
            records,
            required_periods=6,
            minimum_positive_periods=4,
        )
        self.assertEqual(average, Decimal("1000000"))
        self.assertEqual(len(facts), 6)
        with self.assertRaises(CalculationInputError):
            calculate_average_variable_income(
                records[:5], required_periods=6, minimum_positive_periods=4
            )

    def test_case_document_store_blocks_cross_case_reads(self) -> None:
        store = CaseScopedDocumentStore()
        stored = store.put(
            case_id="case-a",
            application_id="app-a",
            document_id="doc-a",
            file_name="statement.pdf",
            content_type="application/pdf",
            content=b"synthetic bytes",
        )
        self.assertEqual(stored.size_bytes, 15)
        self.assertEqual(store.get(case_id="case-a", application_id="app-a", document_id="doc-a"), b"synthetic bytes")
        with self.assertRaises(DocumentStorageError):
            store.get(case_id="case-b", application_id="app-b", document_id="doc-a")
        with self.assertRaises(DocumentStorageError):
            store.put(
                case_id="case-a",
                application_id="app-a",
                document_id="doc-b",
                file_name="statement.exe",
                content_type="application/octet-stream",
                content=b"no",
            )

    def test_eligible_income_uses_explicit_inputs_only(self) -> None:
        result = calculate_eligible_income(
            average_income=Decimal("23833000"),
            contract_salary=Decimal("22000000"),
            average_documented_variable_income=Decimal("2500000"),
            variable_income_cap=Decimal("1000000"),
        )
        self.assertEqual(result, Decimal("23000000"))


if __name__ == "__main__":
    unittest.main()
