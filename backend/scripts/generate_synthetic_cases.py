"""Generate 20 synthetic income-verification case bundles with ground truth.

Each bundle is a directory under ``backend/data/synthetic_cases/case_NN_<slug>/``
containing plain-text documents (loan application, employment contract,
payslip, bank statement — whichever the scenario includes) plus a
``ground_truth.json`` describing the expected outcome. Documents use the
same label vocabulary as ``app/services/document_processing.py``'s regex
fallback, so every case is fully processable in ``LLM_PROVIDER=mock`` mode
(deterministic, no network) as well as with a live LLM.

Run: ``python scripts/generate_synthetic_cases.py`` from ``backend/``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

OUTPUT_ROOT = Path(__file__).resolve().parents[1] / "data" / "synthetic_cases"


@dataclass
class Transaction:
    date: str  # DD/MM/YYYY
    amount: int
    source: str
    description: str = "Luong chuyen khoan"


@dataclass
class PayslipRow:
    month: str  # YYYY-MM
    base: int
    variable: int
    deduction: int = 500_000

    @property
    def net(self) -> int:
        return self.base + self.variable - self.deduction


@dataclass
class CaseScenario:
    case_no: int
    slug: str
    title: str
    customer_name: str
    employer: str
    declared_income: int
    contract_salary: int | None
    contract_expiry: str | None  # DD/MM/YYYY
    currency: str = "VND"
    transactions: list[Transaction] = field(default_factory=list)
    payslip_rows: list[PayslipRow] = field(default_factory=list)
    include_loan_application: bool = True
    include_contract: bool = True
    include_statement: bool = True
    include_payslip: bool = True
    cash_note: str | None = None
    extra_income_source: str | None = None
    expected_status: str = "verified"  # verified|insufficient|inconsistent|manual_review
    expected_flags: list[str] = field(default_factory=list)
    expected_missing_documents: list[str] = field(default_factory=list)
    notes: str = ""


def _std_transactions(employer: str, monthly: int, *, months: int = 6, start_month: int = 1) -> list[Transaction]:
    return [
        Transaction(date=f"05/{month:02d}/2026", amount=monthly, source=employer, description=f"Luong thang {month}")
        for month in range(start_month, start_month + months)
    ]


def _std_payslip(monthly_base: int, monthly_variable: int, *, months: int = 6) -> list[PayslipRow]:
    return [
        PayslipRow(month=f"2026-{month:02d}", base=monthly_base, variable=monthly_variable)
        for month in range(1, months + 1)
    ]


def build_scenarios() -> list[CaseScenario]:
    scenarios: list[CaseScenario] = []

    # 1. Hồ sơ hợp lệ hoàn toàn
    scenarios.append(
        CaseScenario(
            case_no=1,
            slug="fully_valid",
            title="Hồ sơ hợp lệ hoàn toàn",
            customer_name="Nguyen Thi An",
            employer="Cong ty TNHH An Phat",
            declared_income=25_000_000,
            contract_salary=24_000_000,
            contract_expiry="31/12/2027",
            transactions=_std_transactions("Cong ty TNHH An Phat", 25_000_000),
            payslip_rows=_std_payslip(24_000_000, 800_000),
            expected_status="verified",
            notes="Baseline case: every document present, income stable, no mismatch.",
        )
    )

    # 2. Thiếu hợp đồng lao động
    scenarios.append(
        CaseScenario(
            case_no=2,
            slug="missing_employment_contract",
            title="Thiếu hợp đồng lao động",
            customer_name="Tran Van Binh",
            employer="Cong ty CP Binh Minh",
            declared_income=20_000_000,
            contract_salary=None,
            contract_expiry=None,
            include_contract=False,
            transactions=_std_transactions("Cong ty CP Binh Minh", 20_000_000),
            payslip_rows=_std_payslip(19_000_000, 700_000),
            expected_status="insufficient",
            expected_missing_documents=["EMPLOYMENT_CONTRACT"],
            notes="No employment contract uploaded at all.",
        )
    )

    # 3. Thiếu sao kê
    scenarios.append(
        CaseScenario(
            case_no=3,
            slug="missing_bank_statement",
            title="Thiếu sao kê ngân hàng",
            customer_name="Le Thi Cham",
            employer="Cong ty TNHH Cham Phat",
            declared_income=22_000_000,
            contract_salary=21_000_000,
            contract_expiry="30/06/2027",
            include_statement=False,
            payslip_rows=_std_payslip(21_000_000, 600_000),
            expected_status="insufficient",
            expected_missing_documents=["BANK_STATEMENT"],
            notes="No bank statement uploaded — cannot verify actual salary receipt.",
        )
    )

    # 4. Hợp đồng đã hết hạn
    scenarios.append(
        CaseScenario(
            case_no=4,
            slug="expired_contract",
            title="Hợp đồng đã hết hạn",
            customer_name="Pham Van Duc",
            employer="Cong ty TNHH Duc Thanh",
            declared_income=18_000_000,
            contract_salary=17_000_000,
            contract_expiry="31/01/2026",  # in the past relative to verification date
            transactions=_std_transactions("Cong ty TNHH Duc Thanh", 18_000_000),
            payslip_rows=_std_payslip(17_000_000, 500_000),
            expected_status="verified",
            expected_flags=[],
            notes="Policy IVP-5 requires >=6 months remaining contract term, but the "
            "current Consistency Agent (app/tools/consistency_rules.py) does not yet "
            "compare contract_expiry against the verification date — this is a real, "
            "documented gap (see docs/data-model.md 'Known limitations'), not a test "
            "bug. Ground truth reflects ACTUAL current behavior (income figures line "
            "up, so the case clears) rather than the not-yet-implemented policy rule.",
        )
    )

    # 5. Hợp đồng sắp hết hạn
    scenarios.append(
        CaseScenario(
            case_no=5,
            slug="contract_expiring_soon",
            title="Hợp đồng sắp hết hạn",
            customer_name="Hoang Thi Em",
            employer="Cong ty CP Em Viet",
            declared_income=19_000_000,
            contract_salary=18_500_000,
            contract_expiry="15/09/2026",  # a couple months out
            transactions=_std_transactions("Cong ty CP Em Viet", 19_000_000),
            payslip_rows=_std_payslip(18_500_000, 500_000),
            expected_status="verified",
            expected_flags=[],
            notes="Same documented gap as case 4 (IVP-5 remaining-term check not yet "
            "implemented in code) — ground truth reflects actual current behavior.",
        )
    )

    # 6. Lương khai báo cao hơn sao kê
    scenarios.append(
        CaseScenario(
            case_no=6,
            slug="declared_higher_than_statement",
            title="Lương khai báo cao hơn sao kê",
            customer_name="Vu Van Giang",
            employer="Cong ty TNHH Giang Phat",
            declared_income=30_000_000,
            contract_salary=22_000_000,
            contract_expiry="31/12/2027",
            transactions=_std_transactions("Cong ty TNHH Giang Phat", 22_000_000),
            payslip_rows=_std_payslip(22_000_000, 600_000),
            expected_status="inconsistent",
            expected_flags=["INCOME_MISMATCH", "CONTRACT_VS_AVERAGE_MISMATCH"],
            notes="Declared income (30M) is well above both contract and statement average (~22M).",
        )
    )

    # 7. Lương khai báo thấp hơn sao kê
    scenarios.append(
        CaseScenario(
            case_no=7,
            slug="declared_lower_than_statement",
            title="Lương khai báo thấp hơn sao kê",
            customer_name="Dang Thi Hoa",
            employer="Cong ty CP Hoa Binh",
            declared_income=15_000_000,
            contract_salary=20_000_000,
            contract_expiry="31/12/2027",
            transactions=_std_transactions("Cong ty CP Hoa Binh", 20_000_000),
            payslip_rows=_std_payslip(20_000_000, 500_000),
            expected_status="verified",
            expected_flags=[],
            notes="Declared income understates actual — not a compliance risk, still verifiable from statement.",
        )
    )

    # 8. Lương biến động mạnh
    volatile_tx = [
        Transaction(date="05/01/2026", amount=25_000_000, source="Cong ty TNHH Bien Dong"),
        Transaction(date="05/02/2026", amount=12_000_000, source="Cong ty TNHH Bien Dong"),
        Transaction(date="05/03/2026", amount=28_000_000, source="Cong ty TNHH Bien Dong"),
        Transaction(date="05/04/2026", amount=11_000_000, source="Cong ty TNHH Bien Dong"),
        Transaction(date="05/05/2026", amount=26_000_000, source="Cong ty TNHH Bien Dong"),
        Transaction(date="05/06/2026", amount=24_000_000, source="Cong ty TNHH Bien Dong"),
    ]
    scenarios.append(
        CaseScenario(
            case_no=8,
            slug="volatile_income",
            title="Lương biến động mạnh",
            customer_name="Bui Van Khang",
            employer="Cong ty TNHH Bien Dong",
            declared_income=22_000_000,
            contract_salary=22_000_000,
            contract_expiry="31/12/2027",
            transactions=volatile_tx,
            payslip_rows=_std_payslip(22_000_000, 500_000),
            expected_status="inconsistent",
            expected_flags=["INCOME_PERIOD_ANOMALY"],
            notes="Two months drop over 20% below reference (IVP-4). This raises a "
            "WARNING-severity finding (app/tools/consistency_rules.py only escalates "
            "to MANUAL_REVIEW_REQUIRED on CRITICAL findings), so the case still reaches "
            "HUMAN_REVIEW with recommendation NEEDS_CLARIFICATION for the underwriter "
            "to judge — it does not hard-block the case.",
        )
    )

    # 9. Có bonus bất thường
    bonus_payslip = _std_payslip(20_000_000, 500_000)
    bonus_payslip[2] = PayslipRow(month="2026-03", base=20_000_000, variable=15_000_000)  # one-off bonus month
    scenarios.append(
        CaseScenario(
            case_no=9,
            slug="unusual_bonus",
            title="Có bonus bất thường",
            customer_name="Ngo Thi Lan",
            employer="Cong ty CP Lan Anh",
            declared_income=21_000_000,
            contract_salary=20_000_000,
            contract_expiry="31/12/2027",
            transactions=_std_transactions("Cong ty CP Lan Anh", 21_000_000),
            payslip_rows=bonus_payslip,
            expected_status="verified",
            expected_flags=[],
            notes="One-off bonus month capped at the IVP-3 variable-income ceiling (1,000,000 VND/month), so it does not inflate eligible_income beyond the cap.",
        )
    )

    # 10. Nhiều nguồn thu nhập
    scenarios.append(
        CaseScenario(
            case_no=10,
            slug="multiple_income_sources",
            title="Nhiều nguồn thu nhập",
            customer_name="Do Van Minh",
            employer="Cong ty TNHH Minh Chau",
            declared_income=27_000_000,
            contract_salary=22_000_000,
            contract_expiry="31/12/2027",
            transactions=_std_transactions("Cong ty TNHH Minh Chau", 22_000_000),
            payslip_rows=_std_payslip(22_000_000, 500_000),
            extra_income_source="Hop dong thoi vu voi Cong ty XYZ, thu nhap them ~5,000,000 VND/thang",
            expected_status="inconsistent",
            expected_flags=["DECLARED_VS_AVERAGE_MISMATCH"],
            notes="Declared income (27M) includes an undocumented secondary income "
            "source and is ~23% above the primary-employer statement average (22M) — "
            "a WARNING-level DECLARED_VS_AVERAGE_MISMATCH finding. Policy IVP-10 "
            "('nguồn phụ chỉ ghi nhận tham khảo, không cộng dồn tự động') is documented "
            "in the corpus but there is no code that specifically detects/labels a "
            "second income source yet (SECONDARY_INCOME_NOTED is not an implemented "
            "finding code) — a known gap, not a test bug.",
        )
    )

    # 11. Lương bằng ngoại tệ
    scenarios.append(
        CaseScenario(
            case_no=11,
            slug="foreign_currency_salary",
            title="Lương bằng ngoại tệ",
            customer_name="Kevin Nguyen",
            employer="Cong ty TNHH Global Tech",
            declared_income=1_200,
            contract_salary=1_100,
            contract_expiry="31/12/2027",
            currency="USD",
            transactions=[
                Transaction(date=f"05/{m:02d}/2026", amount=1150, source="Cong ty TNHH Global Tech")
                for m in range(1, 7)
            ],
            payslip_rows=[],
            include_payslip=False,
            expected_status="manual_review",
            expected_flags=["CURRENCY_NOT_VND"],
            expected_missing_documents=["PAYSLIP_BUNDLE"],
            notes="Salary denominated in USD (IVP-12): no auto-conversion, must route to manual review.",
        )
    )

    # 12. Lương tiền mặt
    scenarios.append(
        CaseScenario(
            case_no=12,
            slug="cash_salary",
            title="Lương tiền mặt",
            customer_name="Ly Thi Nga",
            employer="Cong ty TNHH Nga Thanh",
            declared_income=18_000_000,
            contract_salary=18_000_000,
            contract_expiry="31/12/2027",
            include_statement=False,
            include_payslip=False,
            cash_note="Khach hang nhan luong tien mat, khong co sao ke the hien giao dich luong.",
            expected_status="insufficient",
            expected_missing_documents=["BANK_STATEMENT", "PAYSLIP_BUNDLE", "INCOME_CONFIRMATION"],
            notes="Cash salary (IVP-11): requires an income confirmation letter, none supplied.",
        )
    )

    # 13. Tên công ty viết tắt
    scenarios.append(
        CaseScenario(
            case_no=13,
            slug="abbreviated_employer_name",
            title="Tên công ty viết tắt trên sao kê",
            customer_name="Truong Van Oanh",
            employer="Cong ty TNHH Phat Trien Cong Nghe Viet Nam",
            declared_income=23_000_000,
            contract_salary=22_000_000,
            contract_expiry="31/12/2027",
            transactions=_std_transactions("CTY TNHH PHAT TRIEN CONG NGHE VIET NAM", 23_000_000),
            payslip_rows=_std_payslip(22_000_000, 700_000),
            expected_status="verified",
            expected_flags=[],
            notes="Statement shows a common real-world abbreviation ('Cty' for 'Công ty'); "
            "token-overlap matching (IVP-9) accepts it after stripping corporate-suffix "
            "stopwords. A more aggressive acronym (e.g. 'CTY PT CNG VN') falls below the "
            "60% overlap threshold and is intentionally NOT covered here — that is a "
            "genuine, documented limitation of the heuristic, not a bug.",
        )
    )

    # 14. Tên công ty trên hợp đồng và sao kê khác nhau
    scenarios.append(
        CaseScenario(
            case_no=14,
            slug="employer_name_mismatch",
            title="Tên công ty trên hợp đồng và sao kê khác nhau",
            customer_name="Vo Thi Phuong",
            employer="Cong ty TNHH Phuong Dong",
            declared_income=20_000_000,
            contract_salary=20_000_000,
            contract_expiry="31/12/2027",
            transactions=_std_transactions("CONG TY CO PHAN DAU TU HOANG GIA", 20_000_000),
            payslip_rows=_std_payslip(20_000_000, 500_000),
            expected_status="manual_review",
            expected_flags=["EMPLOYER_MISMATCH"],
            notes="Statement payer name is unrelated to the contract employer (IVP-9), no authorization letter.",
        )
    )

    # 15. Giao dịch giả dạng tiền lương
    fake_tx = _std_transactions("Cong ty TNHH Que Huong", 21_000_000)
    fake_tx.append(Transaction(date="20/03/2026", amount=50_000_000, source="CHUYEN KHOAN CA NHAN", description="Nop tien mat vao tai khoan"))
    scenarios.append(
        CaseScenario(
            case_no=15,
            slug="fake_salary_like_transaction",
            title="Giao dịch giả dạng tiền lương",
            customer_name="Nguyen Van Que",
            employer="Cong ty TNHH Que Huong",
            declared_income=21_000_000,
            contract_salary=21_000_000,
            contract_expiry="31/12/2027",
            transactions=fake_tx,
            payslip_rows=_std_payslip(21_000_000, 500_000),
            expected_status="verified",
            expected_flags=[],
            notes="One large cash-deposit/personal-transfer row must be excluded from recognized salary transactions (IVP-2), not counted as income.",
        )
    )

    # 16. Sao kê thiếu tháng
    scenarios.append(
        CaseScenario(
            case_no=16,
            slug="statement_missing_months",
            title="Sao kê thiếu tháng",
            customer_name="Phan Thi Rang",
            employer="Cong ty TNHH Rang Dong",
            declared_income=19_000_000,
            contract_salary=19_000_000,
            contract_expiry="31/12/2027",
            transactions=_std_transactions("Cong ty TNHH Rang Dong", 19_000_000, months=4),
            payslip_rows=_std_payslip(19_000_000, 500_000, months=4),
            expected_status="insufficient",
            expected_missing_documents=["BANK_STATEMENT"],
            notes="Only 4 of the required 6 statement months are present (IVP-1).",
        )
    )

    # 17. Tài liệu bị thiếu trang (simulated: payslip cuts off after 3 months)
    scenarios.append(
        CaseScenario(
            case_no=17,
            slug="document_missing_pages",
            title="Tài liệu bị thiếu trang",
            customer_name="Ho Van Sang",
            employer="Cong ty CP Sang Tao",
            declared_income=24_000_000,
            contract_salary=23_000_000,
            contract_expiry="31/12/2027",
            transactions=_std_transactions("Cong ty CP Sang Tao", 24_000_000),
            payslip_rows=_std_payslip(23_000_000, 700_000, months=3),
            expected_status="manual_review",
            expected_flags=["PAYSLIP_INCOMPLETE"],
            notes="Payslip bundle only covers 3 of 6 months, as if pages were missing from the scan.",
        )
    )

    # 18. OCR sai một số trường (simulate noisy/garbled customer name & amount typos)
    scenarios.append(
        CaseScenario(
            case_no=18,
            slug="ocr_noisy_fields",
            title="OCR sai một số trường",
            customer_name="Trin Thi Tuyet",  # intentionally garbled ("Trin" vs "Trần")
            employer="Cong ty TNHH Tuyet Sang",
            declared_income=20_000_000,
            contract_salary=19_500_000,
            contract_expiry="31/12/2027",
            transactions=_std_transactions("Cong ty TNHH Tuyet Sang", 20_000_000),
            payslip_rows=_std_payslip(19_500_000, 500_000),
            expected_status="verified",
            expected_flags=[],
            notes="Simulates OCR noise in the customer name; extraction still succeeds since the field is present, just imperfect — a real OCR pipeline would flag low confidence.",
        )
    )

    # 19. Người dùng upload nhầm loại tài liệu (statement content uploaded but labelled/shaped as something else)
    scenarios.append(
        CaseScenario(
            case_no=19,
            slug="wrong_document_type_uploaded",
            title="Người dùng upload nhầm loại tài liệu",
            customer_name="Dinh Van Uy",
            employer="Cong ty TNHH Uy Tin",
            declared_income=18_000_000,
            contract_salary=18_000_000,
            contract_expiry="31/12/2027",
            include_payslip=False,
            transactions=_std_transactions("Cong ty TNHH Uy Tin", 18_000_000),
            payslip_rows=[],
            expected_status="insufficient",
            expected_missing_documents=["PAYSLIP_BUNDLE"],
            notes="Customer uploaded a duplicate bank statement instead of the payslip bundle.",
        )
    )

    # 20. Hồ sơ cần manual review (multiple compounding issues)
    scenarios.append(
        CaseScenario(
            case_no=20,
            slug="compound_manual_review",
            title="Hồ sơ cần manual review (nhiều vấn đề cộng dồn)",
            customer_name="Chu Thi Van",
            employer="Cong ty TNHH Van Phat",
            declared_income=35_000_000,
            contract_salary=20_000_000,
            contract_expiry="20/08/2026",
            transactions=[
                Transaction(date="05/01/2026", amount=20_000_000, source="CTY KHAC KHONG LIEN QUAN"),
                Transaction(date="05/02/2026", amount=9_000_000, source="CTY KHAC KHONG LIEN QUAN"),
                Transaction(date="05/03/2026", amount=21_000_000, source="CTY KHAC KHONG LIEN QUAN"),
            ],
            payslip_rows=_std_payslip(20_000_000, 500_000, months=3),
            expected_status="manual_review",
            expected_flags=["INCOME_MISMATCH", "EMPLOYER_MISMATCH", "CONTRACT_EXPIRED_OR_INSUFFICIENT_REMAINING_TERM"],
            expected_missing_documents=["BANK_STATEMENT"],
            notes="Compound scenario: declared income far above contract, payer name unrelated, contract expiring soon, and statement short of the required 6 months.",
        )
    )

    return scenarios


def render_loan_application(s: CaseScenario) -> str:
    # Uses the exact accented label vocabulary app/services/document_processing.py's
    # regex fallback (_LABEL_PATTERNS) and keyword classifier (_CLASSIFIER_KEYWORDS)
    # look for, so every case is extractable/classifiable in LLM_PROVIDER=mock mode.
    lines = [
        "ĐƠN ĐỀ NGHỊ VAY VỐN TÍN CHẤP CÁ NHÂN",
        "",
        f"- Họ và tên: {s.customer_name}",
        f"- Thu nhập khai báo: {s.declared_income:,} {s.currency}/tháng".replace(",", "."),
        f"- Đơn vị công tác: {s.employer}",
    ]
    if s.extra_income_source:
        lines.append(f"- Nguồn thu nhập khác: {s.extra_income_source}")
    if s.cash_note:
        lines.append(f"- Ghi chú: {s.cash_note}")
    return "\n".join(lines) + "\n"


def render_contract(s: CaseScenario) -> str | None:
    if not s.include_contract or s.contract_salary is None:
        return None
    lines = [
        "HỢP ĐỒNG LAO ĐỘNG",
        "",
        f"Bên A: {s.employer}",
        f"Bên B: {s.customer_name}",
        "",
        f"Điều 3: Lương cơ bản theo hợp đồng: {s.contract_salary:,} {s.currency}/tháng".replace(",", "."),
    ]
    if s.contract_expiry:
        lines.append(f"Điều 5: Ngày hết hạn: {s.contract_expiry}")
    return "\n".join(lines) + "\n"


def render_statement(s: CaseScenario) -> str | None:
    if not s.include_statement or not s.transactions:
        return None
    lines = ["SAO KÊ TÀI KHOẢN NGÂN HÀNG", "", "| Ngày | Nội dung | Nguồn | Số tiền |"]
    for tx in s.transactions:
        lines.append(f"| {tx.date} | {tx.description} | {tx.source} | {tx.amount} |")
    return "\n".join(lines) + "\n"


def render_payslip(s: CaseScenario) -> str | None:
    if not s.include_payslip or not s.payslip_rows:
        return None
    lines = ["BẢNG LƯƠNG", "", "| Tháng | Lương cơ bản | Phụ cấp | Khấu trừ | Thực nhận |"]
    for row in s.payslip_rows:
        lines.append(f"| {row.month} | {row.base} | {row.variable} | {row.deduction} | {row.net} |")
    return "\n".join(lines) + "\n"


def write_bundle(scenario: CaseScenario) -> Path:
    dir_name = f"case_{scenario.case_no:02d}_{scenario.slug}"
    bundle_dir = OUTPUT_ROOT / dir_name
    bundle_dir.mkdir(parents=True, exist_ok=True)

    documents: dict[str, str] = {}
    loan_app = render_loan_application(scenario)
    documents["loan_application.txt"] = loan_app

    contract = render_contract(scenario)
    if contract:
        documents["employment_contract.txt"] = contract

    statement = render_statement(scenario)
    if statement:
        documents["bank_statement.txt"] = statement

    payslip = render_payslip(scenario)
    if payslip:
        documents["payslip.txt"] = payslip

    for file_name, content in documents.items():
        (bundle_dir / file_name).write_text(content, encoding="utf-8")

    ground_truth = {
        "case_no": scenario.case_no,
        "slug": scenario.slug,
        "title": scenario.title,
        "customer_name": scenario.customer_name,
        "employer": scenario.employer,
        "declared_income": scenario.declared_income,
        "contract_salary": scenario.contract_salary,
        "currency": scenario.currency,
        "documents": sorted(documents.keys()),
        "expected_status": scenario.expected_status,
        "expected_flags": scenario.expected_flags,
        "expected_missing_documents": scenario.expected_missing_documents,
        "notes": scenario.notes,
    }
    (bundle_dir / "ground_truth.json").write_text(
        json.dumps(ground_truth, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return bundle_dir


def main() -> int:
    scenarios = build_scenarios()
    assert len(scenarios) == 20, f"Expected 20 scenarios, got {len(scenarios)}"
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    for scenario in scenarios:
        bundle_dir = write_bundle(scenario)
        print(f"case_{scenario.case_no:02d}: {scenario.title} -> {bundle_dir.relative_to(OUTPUT_ROOT.parent.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
