---
dataset_id: SYN-IV-DOC-001
dataset_type: CASE_EVIDENCE
target_agent: DOCUMENT_EXTRACTION_AGENT
case_id: SYN-IV-001
application_id: SYN-SHB-2026-0001
language: vi
synthetic: true
contains_real_customer_data: false
storage_scope: case_scoped_only
version: "1.0"
created_at: "2026-07-18"
---

# Bộ hồ sơ xác minh thu nhập tổng hợp — CASE SYN-IV-001

> Toàn bộ tên, số định danh, doanh nghiệp, tài khoản và giao dịch trong tài liệu
> này là dữ liệu giả lập phục vụ phát triển và kiểm thử. Không sử dụng tài liệu
> này làm chính sách và không đưa nội dung vào policy embedding toàn cục.

## Mục tiêu kiểm thử

Bộ hồ sơ dùng để kiểm tra Document Extraction Agent có thể:

- phân loại đơn vay, hợp đồng lao động, bảng lương và sao kê;
- trích xuất đúng tên khách hàng, đơn vị công tác, thu nhập khai báo, lương hợp
  đồng và thời hạn hợp đồng;
- trích xuất từng giao dịch lương cùng `evidence_id`;
- không nhầm chuyển khoản nội bộ hoặc tiền nộp mặt thành lương;
- để `null` hoặc báo thiếu khi không có phụ lục điều chỉnh lương;
- không tự kết luận thu nhập đủ điều kiện.

---

<!-- Trang 1 -->

## Tài liệu 1 — Đơn đề nghị vay tín chấp

**Document ID:** `DOC-SYN-001-APPLICATION`  
**Document type:** `LOAN_APPLICATION`

### Thông tin khách hàng

- Họ và tên: Nguyễn Minh Anh
- Số định danh: 0790******01
- Số điện thoại: 09******01
- Địa chỉ liên hệ: Quận Cầu Giấy, Hà Nội

### Thông tin công việc và khoản vay

- Đơn vị công tác: Công ty TNHH Giải pháp Minh Tâm
- Chức danh: Chuyên viên phân tích dữ liệu
- Ngày bắt đầu làm việc khai báo: 01/07/2024
- Thu nhập khai báo: 25.000.000 VND/tháng
- Số tiền đề nghị vay: 300.000.000 VND
- Thời hạn đề nghị: 36 tháng
- Mục đích vay: Chi tiêu gia đình

**Xác nhận của khách hàng:** Nguyễn Minh Anh — ngày 10/07/2026.

---

<!-- Trang 2 -->

## Tài liệu 2 — Hợp đồng lao động

**Document ID:** `DOC-SYN-001-CONTRACT`  
**Document type:** `EMPLOYMENT_CONTRACT`

**Số hợp đồng:** `MT-2024/HĐLĐ-071`  
**Ngày ký:** 25/06/2024

### Bên sử dụng lao động

- Tên đơn vị: Công ty TNHH Giải pháp Minh Tâm
- Mã số doanh nghiệp giả lập: 0109*****8
- Địa chỉ: Quận Nam Từ Liêm, Hà Nội

### Người lao động

- Họ và tên: Nguyễn Minh Anh
- Số định danh: 0790******01
- Chức danh: Chuyên viên phân tích dữ liệu

### Điều khoản công việc và tiền lương

- Loại hợp đồng: Xác định thời hạn 36 tháng
- Ngày bắt đầu: 01/07/2024
- Ngày hết hạn: 30/06/2027
- Lương cơ bản theo hợp đồng: 22.000.000 VND/tháng
- Hình thức trả lương: Chuyển khoản
- Ngày trả lương dự kiến: Từ ngày 24 đến ngày 26 hằng tháng
- Phụ cấp/thu nhập biến đổi: Theo kết quả công việc và quy định của công ty

Không có phụ lục điều chỉnh mức lương trong bộ hồ sơ này.

---

<!-- Trang 3 -->

## Tài liệu 3 — Bảng lương sáu tháng

**Document ID:** `DOC-SYN-001-PAYSLIPS`  
**Document type:** `PAYSLIP_BUNDLE`

| Kỳ lương | Lương cơ bản thực trả | Hỗ trợ hiệu suất | Khấu trừ | Thực nhận |
| --- | ---: | ---: | ---: | ---: |
| 2026-01 | 22.000.000 | 2.800.000 | 0 | 24.800.000 |
| 2026-02 | 22.000.000 | 3.100.000 | 0 | 25.100.000 |
| 2026-03 | 22.000.000 | 2.900.000 | 0 | 24.900.000 |
| 2026-04 | 22.000.000 | 3.200.000 | 0 | 25.200.000 |
| 2026-05 | 18.000.000 | 0 | 0 | 18.000.000 |
| 2026-06 | 22.000.000 | 3.000.000 | 0 | 25.000.000 |

Ghi chú trên bảng lương tháng 05/2026: Nghỉ không hưởng lương một phần kỳ.

---

<!-- Trang 4 -->

## Tài liệu 4 — Sao kê tài khoản sáu tháng

**Document ID:** `DOC-SYN-001-STATEMENT`  
**Document type:** `BANK_STATEMENT`  
**Chủ tài khoản:** Nguyễn Minh Anh  
**Số tài khoản:** 10******01  
**Kỳ sao kê:** 01/01/2026–30/06/2026  
**Đơn vị tiền tệ:** VND

| Evidence ID | Ngày | Diễn giải | Bên chuyển/Nộp | Ghi Có |
| --- | --- | --- | --- | ---: |
| `statement_p1_row08` | 25/01/2026 | LUONG T01/2026 NMA | CTY TNHH GP MINH TAM | 24.800.000 |
| `statement_p1_row16` | 28/01/2026 | CHUYEN TIEN NOI BO | NGUYEN MINH ANH | 5.000.000 |
| `statement_p2_row07` | 25/02/2026 | LUONG T02/2026 NMA | CTY TNHH GP MINH TAM | 25.100.000 |
| `statement_p2_row19` | 27/02/2026 | NOP TIEN MAT | NGUYEN MINH ANH | 3.000.000 |
| `statement_p3_row09` | 25/03/2026 | LUONG T03/2026 NMA | CTY TNHH GP MINH TAM | 24.900.000 |
| `statement_p4_row06` | 24/04/2026 | LUONG T04/2026 NMA | CTY TNHH GP MINH TAM | 25.200.000 |
| `statement_p5_row11` | 26/05/2026 | LUONG T05/2026 NMA | CTY TNHH GP MINH TAM | 18.000.000 |
| `statement_p6_row08` | 25/06/2026 | LUONG T06/2026 NMA | CTY TNHH GP MINH TAM | 25.000.000 |

---

<!-- Trang 5 -->

## Nhãn chuẩn dùng để đánh giá extraction

Khối này là ground truth của dataset, không phải nội dung khách hàng cung cấp.

```json
{
  "case_id": "SYN-IV-001",
  "customer_name": "Nguyễn Minh Anh",
  "declared_income": 25000000,
  "currency": "VND",
  "employer": "Công ty TNHH Giải pháp Minh Tâm",
  "contract_salary": 22000000,
  "contract_start_date": "2024-07-01",
  "contract_expiry": "2027-06-30",
  "statement_period_start": "2026-01-01",
  "statement_period_end": "2026-06-30",
  "salary_transaction_evidence_ids": [
    "statement_p1_row08",
    "statement_p2_row07",
    "statement_p3_row09",
    "statement_p4_row06",
    "statement_p5_row11",
    "statement_p6_row08"
  ],
  "non_salary_transaction_evidence_ids": [
    "statement_p1_row16",
    "statement_p2_row19"
  ],
  "documents_present": [
    "LOAN_APPLICATION",
    "EMPLOYMENT_CONTRACT",
    "PAYSLIP_BUNDLE",
    "BANK_STATEMENT"
  ],
  "documents_not_present": [
    "SALARY_ADJUSTMENT_APPENDIX"
  ],
  "expected_extraction_status": "SUCCESS_WITH_MISSING_DOCUMENT"
}
```

