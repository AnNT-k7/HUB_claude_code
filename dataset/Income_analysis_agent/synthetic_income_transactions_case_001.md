---
dataset_id: SYN-IV-INCOME-001
dataset_type: STRUCTURED_FACT
target_agent: INCOME_ANALYSIS_AGENT
case_id: SYN-IV-001
application_id: SYN-SHB-2026-0001
currency: VND
synthetic: true
contains_real_customer_data: false
calculation_version: income-analysis-demo-v1
version: "1.0"
created_at: "2026-07-18"
---

# Dữ liệu giao dịch thu nhập chuẩn hóa — CASE SYN-IV-001

> Đây là dữ liệu tổng hợp, không phải dữ liệu khách hàng thật. Agent chỉ phân
> tích giao dịch và tạo chỉ số; việc xác định thu nhập đủ điều kiện thuộc Policy
> Agent. Mọi phép tính phải được thực hiện bằng deterministic tool.

## Dữ liệu đầu vào

```json
{
  "case_id": "SYN-IV-001",
  "declared_income": 25000000,
  "contract_salary": 22000000,
  "employer_normalized": "CONG TY TNHH GIAI PHAP MINH TAM",
  "analysis_period": {
    "from": "2026-01-01",
    "to": "2026-06-30",
    "expected_months": 6
  },
  "currency": "VND",
  "transactions": [
    {
      "transaction_id": "TXN-20260125-01",
      "date": "2026-01-25",
      "amount": 24800000,
      "direction": "CREDIT",
      "sender": "CTY TNHH GP MINH TAM",
      "description": "LUONG T01/2026 NMA",
      "source_document_id": "DOC-SYN-001-STATEMENT",
      "evidence_id": "statement_p1_row08"
    },
    {
      "transaction_id": "TXN-20260128-02",
      "date": "2026-01-28",
      "amount": 5000000,
      "direction": "CREDIT",
      "sender": "NGUYEN MINH ANH",
      "description": "CHUYEN TIEN NOI BO",
      "source_document_id": "DOC-SYN-001-STATEMENT",
      "evidence_id": "statement_p1_row16"
    },
    {
      "transaction_id": "TXN-20260225-01",
      "date": "2026-02-25",
      "amount": 25100000,
      "direction": "CREDIT",
      "sender": "CTY TNHH GP MINH TAM",
      "description": "LUONG T02/2026 NMA",
      "source_document_id": "DOC-SYN-001-STATEMENT",
      "evidence_id": "statement_p2_row07"
    },
    {
      "transaction_id": "TXN-20260227-02",
      "date": "2026-02-27",
      "amount": 3000000,
      "direction": "CREDIT",
      "sender": "NGUYEN MINH ANH",
      "description": "NOP TIEN MAT",
      "source_document_id": "DOC-SYN-001-STATEMENT",
      "evidence_id": "statement_p2_row19"
    },
    {
      "transaction_id": "TXN-20260325-01",
      "date": "2026-03-25",
      "amount": 24900000,
      "direction": "CREDIT",
      "sender": "CTY TNHH GP MINH TAM",
      "description": "LUONG T03/2026 NMA",
      "source_document_id": "DOC-SYN-001-STATEMENT",
      "evidence_id": "statement_p3_row09"
    },
    {
      "transaction_id": "TXN-20260424-01",
      "date": "2026-04-24",
      "amount": 25200000,
      "direction": "CREDIT",
      "sender": "CTY TNHH GP MINH TAM",
      "description": "LUONG T04/2026 NMA",
      "source_document_id": "DOC-SYN-001-STATEMENT",
      "evidence_id": "statement_p4_row06"
    },
    {
      "transaction_id": "TXN-20260526-01",
      "date": "2026-05-26",
      "amount": 18000000,
      "direction": "CREDIT",
      "sender": "CTY TNHH GP MINH TAM",
      "description": "LUONG T05/2026 NMA",
      "source_document_id": "DOC-SYN-001-STATEMENT",
      "evidence_id": "statement_p5_row11"
    },
    {
      "transaction_id": "TXN-20260625-01",
      "date": "2026-06-25",
      "amount": 25000000,
      "direction": "CREDIT",
      "sender": "CTY TNHH GP MINH TAM",
      "description": "LUONG T06/2026 NMA",
      "source_document_id": "DOC-SYN-001-STATEMENT",
      "evidence_id": "statement_p6_row08"
    }
  ],
  "payroll_components": [
    {"period": "2026-01", "base_salary": 22000000, "variable_support": 2800000, "evidence_id": "payslip_202601_total"},
    {"period": "2026-02", "base_salary": 22000000, "variable_support": 3100000, "evidence_id": "payslip_202602_total"},
    {"period": "2026-03", "base_salary": 22000000, "variable_support": 2900000, "evidence_id": "payslip_202603_total"},
    {"period": "2026-04", "base_salary": 22000000, "variable_support": 3200000, "evidence_id": "payslip_202604_total"},
    {"period": "2026-05", "base_salary": 18000000, "variable_support": 0, "evidence_id": "payslip_202605_total"},
    {"period": "2026-06", "base_salary": 22000000, "variable_support": 3000000, "evidence_id": "payslip_202606_total"}
  ]
}
```

## Nhãn chuẩn dùng để đánh giá phân tích

```json
{
  "recognized_salary_transaction_ids": [
    "TXN-20260125-01",
    "TXN-20260225-01",
    "TXN-20260325-01",
    "TXN-20260424-01",
    "TXN-20260526-01",
    "TXN-20260625-01"
  ],
  "excluded_transaction_ids": [
    "TXN-20260128-02",
    "TXN-20260227-02"
  ],
  "exclusion_reasons": {
    "TXN-20260128-02": "SELF_TRANSFER",
    "TXN-20260227-02": "CASH_DEPOSIT_WITHOUT_INCOME_EVIDENCE"
  },
  "valid_salary_month_count": 6,
  "missing_salary_months": [],
  "recognized_salary_total": 143000000,
  "average_recognized_salary_raw": 23833333.333333,
  "average_recognized_salary_rounded": 23833000,
  "rounding_rule": "ROUND_TO_NEAREST_1000_VND",
  "reference_monthly_salary": 25000000,
  "anomalies": [
    {
      "period": "2026-05",
      "type": "INCOME_DROP",
      "amount": 18000000,
      "difference_from_reference_percent": -28.0,
      "evidence_ids": [
        "statement_p5_row11",
        "payslip_202605_total"
      ]
    }
  ],
  "eligible_income": null,
  "eligible_income_reason": "POLICY_AGENT_RESPONSIBILITY",
  "expected_status": "SUCCESS_WITH_ANOMALY"
}
```

## Công thức bắt buộc cho deterministic tool

```text
recognized_salary_total = sum(recognized salary transaction amounts)
average_recognized_salary = recognized_salary_total / valid_salary_month_count
difference_percent = (observed_amount - reference_amount) / reference_amount * 100
```

Tool phải lưu danh sách `transaction_id`, `evidence_id`, kỳ dữ liệu, currency,
phiên bản công thức và quy tắc làm tròn cùng kết quả.

