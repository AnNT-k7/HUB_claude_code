---
dataset_id: SYN-IV-POLICY-001
dataset_type: POLICY_RULE
target_agent: POLICY_AGENT
domain: INCOME_VERIFICATION
product: UNSECURED_PERSONAL_LOAN
document_name: Synthetic Income Verification Policy v1.0
issuer: SYNTHETIC_SHB_DEMO
approval_status: APPROVED_FOR_DEMO
effective_date: "2026-07-01"
effective_to: null
language: vi
synthetic: true
production_use: prohibited
version: "1.0"
---

# Chính sách xác minh thu nhập tín chấp — Bản tổng hợp dùng cho demo

> Tài liệu này do dự án tự tạo, không phải chính sách thực tế của SHB và không
> được sử dụng để xử lý hồ sơ thật. Mục tiêu duy nhất là phát triển, kiểm thử RAG
> và minh họa human review. Mọi triển khai production phải thay thế bằng chính
> sách đã được chủ sở hữu nghiệp vụ phê duyệt.

<!-- Trang 1 -->

## IVP-1 — Kỳ sao kê bắt buộc

**Section ID:** `IVP-1`  
**Chunk type:** `POLICY_RULE`

- **Điều kiện:** Khách hàng cá nhân đề nghị vay tín chấp và khai báo nguồn trả
  nợ chính từ tiền lương chuyển khoản.
- **Ngưỡng:** Phải có sao kê của 06 tháng liên tiếp gần nhất tính đến ngày xác
  minh; mỗi tháng phải xác định được trạng thái có hoặc không có giao dịch lương.
- **Ngoại lệ:** Không tự động bù kỳ còn thiếu bằng bảng lương hoặc lời khai của
  khách hàng.
- **Hành động:** Nếu thiếu bất kỳ kỳ nào, trả `MISSING_DOCUMENTS`, nêu rõ tháng
  thiếu và đề xuất chuyên viên yêu cầu bổ sung sao kê.

**Trích dẫn thử nghiệm:** “Phải có sao kê của 06 tháng liên tiếp gần nhất tính
đến ngày xác minh.”

## IVP-2 — Nhận diện khoản lương trên sao kê

**Section ID:** `IVP-2`  
**Chunk type:** `POLICY_RULE`

- **Điều kiện:** Giao dịch ghi Có được xem xét là lương khi bên chuyển khớp đơn
  vị công tác và nội dung giao dịch thể hiện kỳ trả lương.
- **Ngưỡng:** Nguồn chuyển phải xuất hiện tối thiểu 05 trong 06 tháng và mỗi giao
  dịch phải có `evidence_id` truy ngược về sao kê.
- **Ngoại lệ:** Tên viết tắt của doanh nghiệp được chấp nhận khi bảng ánh xạ tên
  đã được chuyên viên xác nhận.
- **Hành động:** Chuyển khoản nội bộ, tiền nộp mặt hoặc giao dịch không xác định
  được nguồn không được tính là lương nếu không có chứng từ bổ sung.

**Trích dẫn thử nghiệm:** “Chuyển khoản nội bộ, tiền nộp mặt hoặc giao dịch không
xác định được nguồn không được tính là lương nếu không có chứng từ bổ sung.”

<!-- Trang 2 -->

## IVP-3 — Thu nhập đủ điều kiện

**Section ID:** `IVP-3`  
**Chunk type:** `POLICY_RULE`

- **Điều kiện:** Có đủ 06 tháng sao kê, hợp đồng lao động còn hiệu lực và giao
  dịch lương đã được Income Analysis Agent phân loại bằng deterministic tool.
- **Ngưỡng:** Thu nhập đủ điều kiện bằng giá trị nhỏ hơn giữa:
  1. thu nhập lương bình quân của 06 tháng hợp lệ; và
  2. lương cơ bản trên hợp đồng cộng phần thu nhập biến đổi được chấp nhận.
- **Thu nhập biến đổi:** Phần hỗ trợ hiệu suất chỉ được tính tối đa 1.000.000
  VND/tháng và phải xuất hiện trên bảng lương của ít nhất 04 trong 06 tháng.
- **Ngoại lệ:** Không tính thưởng một lần, tiền nộp mặt, chuyển khoản nội bộ hoặc
  khoản thu không có bằng chứng về nguồn.
- **Hành động:** Công thức phải chạy bằng deterministic tool, sử dụng VND và làm
  tròn đến 1.000 VND gần nhất. Policy Agent không tự tính nhẩm bằng LLM.

```text
eligible_income = min(
    average_recognized_salary_6m,
    contract_salary + min(average_documented_variable_income, 1_000_000)
)
```

**Trích dẫn thử nghiệm:** “Thu nhập đủ điều kiện bằng giá trị nhỏ hơn giữa thu
nhập lương bình quân và lương hợp đồng cộng phần thu nhập biến đổi được chấp
nhận.”

## IVP-4 — Phát hiện tháng thu nhập bất thường

**Section ID:** `IVP-4`  
**Chunk type:** `POLICY_RULE`

- **Điều kiện:** Có ít nhất 05 tháng thu nhập lương hợp lệ để thiết lập mức tham
  chiếu.
- **Ngưỡng:** Một tháng được đánh dấu bất thường khi thu nhập giảm trên 20% so
  với mức tham chiếu do deterministic tool tính.
- **Ngoại lệ:** Không tự loại tháng bất thường khỏi phép tính nếu chưa có quyết
  định của chuyên viên và căn cứ chính sách bổ sung.
- **Hành động:** Trả `MANUAL_REVIEW_REQUIRED`, gắn giao dịch và bảng lương liên
  quan, đồng thời đề xuất chuyên viên xác minh nguyên nhân.

**Trích dẫn thử nghiệm:** “Một tháng được đánh dấu bất thường khi thu nhập giảm
trên 20% so với mức tham chiếu.”

<!-- Trang 3 -->

## IVP-5 — Thời hạn hợp đồng lao động

**Section ID:** `IVP-5`  
**Chunk type:** `POLICY_RULE`

- **Điều kiện:** Nguồn thu nhập chính đến từ hợp đồng lao động xác định thời hạn.
- **Ngưỡng:** Hợp đồng phải còn ít nhất 06 tháng tại ngày xác minh.
- **Ngoại lệ:** Hợp đồng không xác định thời hạn không áp dụng ngưỡng thời gian
  còn lại nhưng vẫn phải có bằng chứng đang làm việc.
- **Hành động:** Nếu không xác định được ngày hết hạn hoặc hợp đồng không đạt
  ngưỡng, trả `MANUAL_REVIEW_REQUIRED`; không suy đoán ngày gia hạn.

**Trích dẫn thử nghiệm:** “Hợp đồng phải còn ít nhất 06 tháng tại ngày xác minh.”

## IVP-6 — Chênh lệch giữa thu nhập khai báo và lương hợp đồng

**Section ID:** `IVP-6`  
**Chunk type:** `POLICY_RULE`

- **Điều kiện:** Thu nhập khai báo cao hơn lương cơ bản ghi trên hợp đồng lao
  động.
- **Ngưỡng:** Chênh lệch lớn hơn 10% phải có phụ lục điều chỉnh lương, bảng lương
  hoặc chứng từ tương đương giải thích phần chênh lệch.
- **Ngoại lệ:** Không chấp nhận giải thích chỉ dựa trên lời khai của khách hàng.
- **Hành động:** Nếu thiếu chứng từ, trả `MISSING_DOCUMENTS` và đề xuất yêu cầu
  bổ sung phụ lục điều chỉnh lương; không tự kết luận hồ sơ đạt hoặc không đạt.

**Trích dẫn thử nghiệm:** “Chênh lệch lớn hơn 10% phải có phụ lục điều chỉnh
lương, bảng lương hoặc chứng từ tương đương giải thích phần chênh lệch.”

<!-- Trang 4 -->

## Metadata citation bắt buộc

Mọi kết quả áp dụng một điều khoản trong tài liệu này phải trả tối thiểu:

```json
{
  "document_name": "Synthetic Income Verification Policy v1.0",
  "page_number": 1,
  "section_id": "IVP-1",
  "effective_date": "2026-07-01",
  "quote": "Phải có sao kê của 06 tháng liên tiếp gần nhất tính đến ngày xác minh.",
  "chunk_id": "SYN-IV-POLICY-001-IVP-1",
  "approval_status": "APPROVED_FOR_DEMO"
}
```

Nếu không tìm thấy điều khoản phù hợp, tài liệu hết hiệu lực hoặc nhiều điều
khoản mâu thuẫn, Policy Agent phải trả `POLICY_NOT_FOUND` hoặc
`MANUAL_REVIEW_REQUIRED` và chuyển chuyên viên xử lý.

