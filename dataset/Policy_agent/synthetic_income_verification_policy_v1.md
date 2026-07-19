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

## IVP-7 — Thời gian làm việc tối thiểu

**Section ID:** `IVP-7`
**Chunk type:** `POLICY_RULE`

- **Điều kiện:** Khách hàng đang trong thời gian thử việc hoặc mới ký hợp đồng
  chính thức tại đơn vị công tác hiện tại.
- **Ngưỡng:** Phải có tối thiểu 03 tháng làm việc liên tục tại đơn vị hiện tại
  tính đến ngày xác minh, xác định qua ngày bắt đầu hợp đồng hoặc phụ lục.
- **Ngoại lệ:** Trường hợp chuyển đổi loại hợp đồng (thử việc sang chính thức)
  tại cùng đơn vị được cộng dồn thời gian làm việc.
- **Hành động:** Nếu chưa đủ 03 tháng, trả `MANUAL_REVIEW_REQUIRED` và nêu rõ
  ngày bắt đầu hợp đồng làm căn cứ.

**Trích dẫn thử nghiệm:** "Phải có tối thiểu 03 tháng làm việc liên tục tại đơn
vị hiện tại tính đến ngày xác minh."

## IVP-8 — Chênh lệch giữa thu nhập khai báo và thu nhập trên sao kê

**Section ID:** `IVP-8`
**Chunk type:** `POLICY_RULE`

- **Điều kiện:** Đã tính được thu nhập bình quân từ giao dịch lương hợp lệ trên
  sao kê.
- **Ngưỡng:** Nếu thu nhập khai báo cao hơn thu nhập bình quân trên sao kê quá
  10%, hồ sơ được đánh dấu cảnh báo chênh lệch khai báo.
- **Ngoại lệ:** Chênh lệch do tháng có thưởng/phụ cấp đã được ghi nhận trong
  thu nhập biến đổi theo IVP-3 không tính là bất thường.
- **Hành động:** Trả finding `INCOME_MISMATCH` mức độ `WARNING`; nếu chênh lệch
  trên 30%, nâng mức độ `CRITICAL` và đề xuất `MANUAL_REVIEW_REQUIRED`.

**Trích dẫn thử nghiệm:** "Nếu thu nhập khai báo cao hơn thu nhập bình quân
trên sao kê quá 10%, hồ sơ được đánh dấu cảnh báo chênh lệch khai báo."

## IVP-9 — Xác minh tên đơn vị chuyển lương

**Section ID:** `IVP-9`
**Chunk type:** `POLICY_RULE`

- **Điều kiện:** Có giao dịch ghi Có nghi ngờ là lương nhưng tên bên chuyển
  không khớp hoàn toàn với tên đơn vị công tác trên hợp đồng lao động.
- **Ngưỡng:** Chấp nhận khớp gần đúng khi tên viết tắt, không dấu, hoặc thiếu
  loại hình doanh nghiệp (Cty/Ltd/JSC) vẫn giữ tối thiểu 60% token trùng khớp
  với tên đầy đủ trên hợp đồng.
- **Ngoại lệ:** Chuyển lương qua bên thứ ba (công ty trả lương thuê ngoài,
  payroll outsourcing) chỉ được chấp nhận khi có văn bản ủy quyền trả lương.
- **Hành động:** Không khớp và không có văn bản ủy quyền → trả finding
  `EMPLOYER_MISMATCH` mức độ `CRITICAL` và chuyển `MANUAL_REVIEW_REQUIRED`.

**Trích dẫn thử nghiệm:** "Chuyển lương qua bên thứ ba chỉ được chấp nhận khi
có văn bản ủy quyền trả lương."

<!-- Trang 5 -->

## IVP-10 — Nhiều nguồn thu nhập

**Section ID:** `IVP-10`
**Chunk type:** `POLICY_RULE`

- **Điều kiện:** Khách hàng khai báo từ 02 nguồn thu nhập trở lên (ví dụ lương
  chính và hợp đồng lao động thời vụ thứ hai).
- **Ngưỡng:** Chỉ nguồn thu nhập chính (thu nhập cao nhất, có hợp đồng lao động
  không xác định thời hạn hoặc còn thời hạn dài nhất) được đưa vào công thức
  IVP-3; nguồn phụ chỉ ghi nhận tham khảo, không cộng dồn tự động.
- **Ngoại lệ:** Nếu chính sách sản phẩm cho phép cộng dồn nguồn phụ, phải có
  quyết định rõ ràng của chuyên viên kèm lý do, không được suy đoán.
- **Hành động:** Gắn nhãn nguồn thu nhập phụ là `SECONDARY_INCOME_NOTED`,
  không tự động đưa vào `eligible_income`.

**Trích dẫn thử nghiệm:** "Chỉ nguồn thu nhập chính được đưa vào công thức
IVP-3; nguồn phụ chỉ ghi nhận tham khảo, không cộng dồn tự động."

## IVP-11 — Thu nhập trả bằng tiền mặt

**Section ID:** `IVP-11`
**Chunk type:** `POLICY_RULE`

- **Điều kiện:** Khách hàng khai báo nhận lương một phần hoặc toàn bộ bằng tiền
  mặt, không thể hiện trên sao kê ngân hàng.
- **Ngưỡng:** Phần lương tiền mặt không được tính vào thu nhập đủ điều kiện nếu
  không có xác nhận thu nhập từ đơn vị công tác kèm chữ ký/con dấu hợp lệ.
- **Ngoại lệ:** Không áp dụng ngoại lệ; đây là ngành nghề có rủi ro xác minh
  cao và luôn yêu cầu chứng từ bổ sung.
- **Hành động:** Thiếu giấy xác nhận thu nhập → trả `MISSING_DOCUMENTS` với mã
  tài liệu `INCOME_CONFIRMATION`; không suy đoán số tiền mặt nhận được.

**Trích dẫn thử nghiệm:** "Phần lương tiền mặt không được tính vào thu nhập đủ
điều kiện nếu không có xác nhận thu nhập từ đơn vị công tác kèm chữ ký/con dấu
hợp lệ."

## IVP-12 — Thu nhập bằng ngoại tệ

**Section ID:** `IVP-12`
**Chunk type:** `POLICY_RULE`

- **Điều kiện:** Giao dịch lương hoặc lương hợp đồng ghi nhận bằng đơn vị tiền
  tệ khác VND.
- **Ngưỡng:** Không tự quy đổi ngoại tệ sang VND bằng deterministic tool hoặc
  LLM nếu chưa có tỷ giá tham chiếu chính thức được chuyên viên xác nhận cho
  ngày giao dịch tương ứng.
- **Ngoại lệ:** Nếu toàn bộ chứng từ (hợp đồng, sao kê, bảng lương) cùng dùng
  một loại ngoại tệ thống nhất, có thể giữ nguyên đơn vị tiền tệ đó cho báo cáo
  nhưng vẫn phải gắn cảnh báo `CURRENCY_NOT_VND`.
- **Hành động:** Có nguồn thu nhập khác loại tiền tệ với nguồn còn lại → trả
  `MANUAL_REVIEW_REQUIRED`, mã `CURRENCY_MISMATCH`; không gộp giá trị khác đơn
  vị tiền tệ vào cùng một phép tính.

**Trích dẫn thử nghiệm:** "Không tự quy đổi ngoại tệ sang VND bằng
deterministic tool hoặc LLM nếu chưa có tỷ giá tham chiếu chính thức."

<!-- Trang 6 -->

## IVP-13 — Bộ tài liệu bắt buộc theo sản phẩm

**Section ID:** `IVP-13`
**Chunk type:** `VERIFICATION_PROCEDURE`

```json
{
  "step": "Kiểm tra bộ tài liệu bắt buộc",
  "inputs": ["LOAN_APPLICATION", "EMPLOYMENT_CONTRACT", "PAYSLIP_BUNDLE", "BANK_STATEMENT"],
  "checks": ["document_set_completeness", "document_owner_matches_customer"],
  "output": "DOCUMENT_SET_STATUS",
  "exception": "Chuyển MISSING_DOCUMENTS nếu thiếu bất kỳ loại tài liệu bắt buộc nào"
}
```

- **Điều kiện:** Mọi hồ sơ vay tín chấp cá nhân thuộc phạm vi Income
  Verification Expert.
- **Ngưỡng:** Bộ tài liệu tối thiểu gồm đơn đề nghị vay, hợp đồng lao động
  (kèm phụ lục nếu có), bảng lương và sao kê ngân hàng đúng số kỳ theo IVP-1.
- **Ngoại lệ:** Giấy xác nhận thu nhập có thể thay thế bảng lương khi đơn vị
  công tác không phát hành bảng lương chi tiết, nhưng phải nêu rõ lý do.
- **Hành động:** Thiếu tài liệu bắt buộc → trả `MISSING_DOCUMENTS` kèm danh
  sách tài liệu còn thiếu theo mã loại tài liệu.

**Trích dẫn thử nghiệm:** "Bộ tài liệu tối thiểu gồm đơn đề nghị vay, hợp đồng
lao động, bảng lương và sao kê ngân hàng đúng số kỳ."

## IVP-14 — Ngưỡng chất lượng trích xuất và dữ liệu thiếu

**Section ID:** `IVP-14`
**Chunk type:** `POLICY_RULE`

- **Điều kiện:** Document Agent đã trả `extraction_confidence` cho hồ sơ.
- **Ngưỡng:** `extraction_confidence` dưới 0.90 hoặc bất kỳ trường thu nhập
  cốt lõi nào (tên khách hàng, thu nhập khai báo, lương hợp đồng, đơn vị công
  tác) không trích xuất được đều bắt buộc chuyển human review trước khi Income
  Analysis Agent hoặc Policy Agent chạy tiếp.
- **Ngoại lệ:** Ngưỡng minh họa này nằm trong cấu hình runtime, có thể điều
  chỉnh theo rule version được domain owner phê duyệt; không hard-code trong
  prompt của bất kỳ agent nào.
- **Hành động:** Dưới ngưỡng → trả `MANUAL_REVIEW_REQUIRED`, mã
  `LOW_EXTRACTION_CONFIDENCE`, không suy đoán giá trị còn thiếu.

**Trích dẫn thử nghiệm:** "extraction_confidence dưới 0.90 hoặc bất kỳ trường
thu nhập cốt lõi nào không trích xuất được đều bắt buộc chuyển human review."

## IVP-15 — Danh mục trường hợp bắt buộc chuyển chuyên viên

**Section ID:** `IVP-15`
**Chunk type:** `VERIFICATION_PROCEDURE`

```json
{
  "step": "Routing ngoại lệ sang human review",
  "inputs": ["income_analysis", "policy_result", "consistency_findings"],
  "checks": [
    "policy_not_found_or_conflict",
    "employer_mismatch",
    "currency_mismatch",
    "income_drop_over_20_percent",
    "missing_required_documents",
    "extraction_confidence_below_threshold"
  ],
  "output": "ROUTING_DECISION",
  "exception": "Không tự động coi bất kỳ trường hợp nào trong danh sách là hồ sơ đạt"
}
```

- **Điều kiện:** Áp dụng cho mọi bước trong workflow xác minh thu nhập, không
  giới hạn ở Policy Agent.
- **Ngưỡng:** Bất kỳ điều kiện nào sau đây cũng bắt buộc chuyển người: không
  tìm thấy policy hoặc policy mâu thuẫn (IVP không khớp), đơn vị chuyển lương
  không khớp hợp đồng (IVP-9), khác loại tiền tệ giữa các nguồn (IVP-12),
  tháng thu nhập giảm trên 20% (IVP-4), thiếu tài liệu bắt buộc (IVP-13), hoặc
  extraction_confidence dưới ngưỡng (IVP-14).
- **Ngoại lệ:** Không có ngoại lệ; đây là rule tổng hợp, không thay thế các
  rule chi tiết ở trên.
- **Hành động:** Ghi rõ rule_id nào kích hoạt routing trong audit event; không
  gộp nhiều lý do thành một mã lỗi chung chung.

**Trích dẫn thử nghiệm:** "Không tự động coi bất kỳ trường hợp nào trong danh
sách là hồ sơ đạt."

<!-- Trang 7 -->

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

