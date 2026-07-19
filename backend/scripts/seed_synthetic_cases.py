"""Seed 20 reproducible multi-document cases and retain their ground truth."""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.case_repository import CaseRepository


DATASET = ROOT / "dataset" / "synthetic_cases.json"
MONTHS = ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06"]


def _documents(case: dict[str, object]) -> dict[str, tuple[str, bytes]]:
    currency = str(case.get("currency", "VND"))
    customer = str(case["customer_name"])
    company = str(case["company"])
    declared = case["declared_income"]
    contract = case["contract_salary"]
    expiry = case.get("contract_expiry", "2028-12-31")
    source = str(case.get("source", company))
    amounts = list(case["salary_amounts"])
    alternate = case.get("alternate_source")
    application = (
        f"Họ và tên: {customer}\nĐơn vị công tác: {company}\n"
        f"Thu nhập khai báo: {declared} {currency}\nTiền tệ: {currency}\n"
    ).encode("utf-8")
    employment = (
        f"Khách hàng: {customer}\nCông ty: {company}\n"
        f"Lương hợp đồng: {contract} {currency}\nNgày hết hạn: {expiry}\n"
    ).encode("utf-8")
    bonus = int(case.get("bonus_amount", 0))
    payslip_rows = [
        f"{month} | base: {contract} | bonus: {bonus if index == 3 else 0}"
        for index, month in enumerate(MONTHS)
    ]
    payslips = (f"Họ và tên: {customer}\nCông ty: {company}\n" + "\n".join(payslip_rows)).encode("utf-8")
    statement_lines = ["month,amount,source,description"]
    for index, (month, amount) in enumerate(zip(MONTHS, amounts, strict=False)):
        row_source = str(alternate) if alternate and index >= 3 else source
        statement_lines.append(f"{month},{amount},{row_source},SALARY {month}")
    statement = "\n".join(statement_lines).encode("utf-8")
    return {
        "LOAN_APPLICATION": ("loan_application.txt", application),
        "EMPLOYMENT_CONTRACT": ("employment_contract.txt", employment),
        "PAYSLIP_BUNDLE": ("payslips.txt", payslips),
        "BANK_STATEMENT": ("bank_statement.csv", statement),
    }


def seed() -> list[str]:
    repository = CaseRepository()
    cases = json.loads(DATASET.read_text(encoding="utf-8"))
    seeded: list[str] = []
    for item in cases:
        application_id = f"SYN-APP-{int(item['case_no']):03d}"
        existing = repository.get_by_application(application_id)
        if existing is None:
            case_id = f"SYN-IV-{int(item['case_no']):03d}"
            row = repository.create_case(
                case_id=case_id,
                application_id=application_id,
                customer_name=str(item["customer_name"]),
                customer_code=f"SYN-CIF-{int(item['case_no']):03d}",
                company=str(item["company"]),
                requested_amount=Decimal("300000000"),
                currency=str(item.get("currency", "VND")),
            )
        else:
            row = existing
        omitted = set(item.get("omit", []))
        present = {document.document_type for document in repository.list_documents(row.id)}
        for document_type, (file_name, content) in _documents(item).items():
            if document_type in omitted:
                continue
            uploaded_type = (
                str(item["wrong_type"])
                if document_type == "BANK_STATEMENT" and item.get("wrong_type")
                else document_type
            )
            if uploaded_type in present:
                continue
            repository.add_document(
                case_id=row.id,
                file_name=file_name,
                content_type="text/csv" if file_name.endswith(".csv") else "text/plain",
                document_type=uploaded_type,
                content=content,
            )
        seeded.append(row.id)
    return seeded


if __name__ == "__main__":
    ids = seed()
    print(f"Seeded or found {len(ids)} synthetic cases.")
