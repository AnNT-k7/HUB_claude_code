---
dataset_id: REF-INCOME-NOTES-001
dataset_type: REFERENCE_NOTE
target_agent: INCOME_ANALYSIS_AGENT
domain: INCOME_VERIFICATION
product: UNSECURED_PERSONAL_LOAN
document_name: SHB and Government Web Source Review Notes for Income Analysis
document_version: "2026-07-18"
issuer: PROJECT_RESEARCH_NOTES
approval_status: PENDING_REVIEW
effective_date: null
effective_to: null
language: vi
synthetic: false
production_use: prohibited
source_kind: PUBLIC_WEB_RESEARCH
case_scoped: false
---

# Ghi chú nguồn web SHB và nguồn Chính phủ phục vụ Income Analysis Agent

**Dự án:** MAS hỗ trợ xác minh thu nhập và thẩm định tín dụng tại SHB  
**Agent áp dụng:** Income Analysis Agent, đồng thời cung cấp đầu vào cho Document Extraction Agent, Policy Agent và Consistency Agent  
**Ngày rà soát:** 18/07/2026  
**Loại nguồn trong tài liệu này:**

1. Các **trang web HTML công khai của SHB** liên quan đến thu nhập, dòng tiền, khả năng trả nợ, hạn mức tín dụng, thấu chi, lương và hồ sơ chứng minh tài chính.
2. Các **nguồn chính thức của Quốc hội, Chính phủ, Ngân hàng Nhà nước và cơ quan quản lý nhà nước** có liên quan tới hoạt động phân tích thu nhập.

> Tài liệu này không liệt kê lại các PDF SHB đã được ưu tiên tải xuống trong giai đoạn thu thập trước. Trọng tâm SHB ở đây là các trang web không phải file tải trực tiếp.
>
> “Tất cả nguồn” được hiểu là rà soát theo hướng bao phủ tối đa các nguồn công khai, đang truy cập được và được công cụ tìm kiếm lập chỉ mục tại thời điểm lập tài liệu. Website có thể tồn tại tài liệu không được lập chỉ mục, nội dung đã gỡ, nội dung chỉ hiển thị theo phiên đăng nhập hoặc trang động không thể thu thập đầy đủ.
>
> Đây là tài liệu phân tích phục vụ thiết kế dataset và hệ thống, không thay thế ý kiến chính thức của Pháp chế, Quản trị rủi ro hoặc Khối Tín dụng SHB.

---

# 1. Phạm vi nghiệp vụ của Income Analysis Agent

Income Analysis Agent nhận dữ liệu đã được Document Extraction Agent chuẩn hóa từ:

- đơn vay;
- hợp đồng lao động;
- phụ lục hợp đồng;
- bảng lương;
- giấy xác nhận thu nhập;
- sao kê tài khoản;
- sao kê thẻ;
- quyết định lương;
- hồ sơ thuế;
- chứng từ bảo hiểm;
- chứng từ thu nhập kinh doanh;
- dữ liệu khoản vay và nghĩa vụ nợ.

Agent thực hiện:

1. Phân loại nguồn thu nhập.
2. Nhóm các giao dịch cùng nguồn.
3. Xác định tính định kỳ và ổn định.
4. Tính tổng thu nhập khai báo, thu nhập xác minh và thu nhập đủ điều kiện.
5. Loại trừ các dòng tiền không phải thu nhập.
6. Phân biệt thu nhập gộp và thu nhập ròng.
7. Xác định nghĩa vụ nợ.
8. Tính DTI và các chỉ tiêu khả năng trả nợ.
9. Phát hiện bất thường.
10. Tạo kết quả có bằng chứng để chuyên viên hoặc agent khác kiểm tra.

Agent **không tự phê duyệt hoặc từ chối khoản vay**.

---

# 2. Nguyên tắc sử dụng nguồn SHB công khai

Các trang sản phẩm và chương trình của SHB có giá trị lớn để:

- xây taxonomy sản phẩm;
- hiểu cách SHB công khai khái niệm thu nhập;
- nhận diện nhóm khách hàng;
- tạo synthetic dataset;
- tạo feature và rule candidate;
- xây bộ câu hỏi kiểm thử;
- xác định loại hồ sơ chứng minh thu nhập.

Tuy nhiên, nội dung marketing hoặc chương trình ưu đãi:

- có thể hết hiệu lực;
- có thể chỉ áp dụng cho một phân khúc;
- có thể thiếu điều kiện nội bộ;
- không được coi là policy production nếu chưa được chủ sở hữu chính sách xác nhận;
- phải gắn ngày crawl, ngày công bố, thời hạn chương trình và URL nguồn.

Metadata tối thiểu:

```yaml
source_type: shb_public_web
source_url: ""
page_title: ""
published_date: null
crawled_at: ""
effective_from: null
effective_to: null
customer_segment: ""
product: ""
policy_status: reference_only
```

---

# 3. Các nguồn web SHB không phải file tải trực tiếp

## 3.1. Vay tiêu dùng không tài sản bảo đảm

**URL:**  
https://www.shb.com.vn/tin-chap-tieu-dung/

### Nội dung liên quan

Trang sản phẩm công khai:

- hạn mức có thể lên tới 500 triệu đồng;
- phương thức rút vốn theo món hoặc hạn mức tín dụng;
- thời gian vay có thể lên tới 60 tháng;
- không yêu cầu tài sản bảo đảm;
- quy trình và điều kiện phụ thuộc hồ sơ khách hàng.

### Ứng dụng với Income Analysis Agent

Agent cần xác định thu nhập đủ để hỗ trợ:

```text
requested_loan_amount
loan_tenor
estimated_monthly_payment
existing_unsecured_debt
available_income_for_debt_service
```

### Dataset cần tạo

- khách hàng có lương cố định;
- khách hàng có lương và thưởng;
- khách hàng có nhiều khoản vay tín chấp;
- khách hàng có thấu chi và thẻ tín dụng;
- khách hàng có thu nhập dao động;
- khách hàng thiếu một tháng sao kê.

### Cờ kiểm tra

```text
UNSTABLE_INCOME
INSUFFICIENT_HISTORY
HIGH_EXISTING_UNSECURED_DEBT
DECLARED_VERIFIED_INCOME_GAP
```

---

## 3.2. Vay thấu chi online tín chấp

**URL:**  
https://www.shb.com.vn/vay-thau-chi-online-tin-chap/

### Nội dung liên quan

Trang công khai mô tả:

- hạn mức thấu chi tối đa theo chương trình;
- mục đích tiêu dùng;
- không có tài sản bảo đảm;
- hạn mức thường được duy trì theo thời hạn xác định;
- nhóm khách hàng có thể gồm người nhận lương qua SHB, người có tiền gửi hoặc quan hệ tín dụng.

### Ứng dụng

Thu nhập không phải biến duy nhất. Agent cần cung cấp thêm:

```text
salary_cashflow
average_account_balance
deposit_balance
existing_credit_relationship
account_turnover
credit_frequency
```

### Phân biệt quan trọng

- số dư tài khoản không đồng nghĩa thu nhập;
- tiền gửi không đồng nghĩa dòng tiền trả nợ hàng tháng;
- hạn mức thấu chi chưa sử dụng không phải nghĩa vụ nợ thực tế;
- dư nợ thấu chi đã sử dụng tạo nghĩa vụ lãi.

### Rule candidate

```text
Nếu tài khoản thường xuyên âm do sử dụng thấu chi:
    giảm chỉ số free_cash_flow
    tăng cờ LIQUIDITY_STRESS

Nếu thu nhập chuyển vào chỉ đủ bù dư nợ thấu chi:
    không coi toàn bộ khoản ghi Có là disposable income
```

---

## 3.3. “Cần tiền – Có liền thấu chi”

**URL:**  
https://www.shb.com.vn/can-tien-co-lien-thau-chi/

### Nội dung liên quan

Trang chương trình công bố:

- hạn mức thấu chi có thể lên tới 1,5 tỷ đồng tùy điều kiện;
- quy trình online;
- lãi tính theo số tiền và số ngày sử dụng;
- miễn lãi nếu hoàn trả trong ngày theo điều kiện chương trình.

### Ứng dụng

Agent cần phân biệt:

```text
overdraft_limit
overdraft_used_amount
overdraft_days
overdraft_interest
same_day_repayment
```

Khoản tiền chuyển vào để tất toán thấu chi không được tính hai lần vừa là thu nhập vừa là nguồn trả nợ.

---

## 3.4. Vay tiêu dùng không tài sản bảo đảm dành cho cán bộ, công chức, viên chức và lực lượng vũ trang

**URL:**  
https://www.shb.com.vn/vay-tieu-dung-khong-tai-san-bao-dam-danh-cho-can-bo-cong-chuc-vien-chuc-luc-luong-vu-trang/

### Nội dung liên quan

Trang công khai nêu:

- hạn mức có thể lên tới 1,2 tỷ đồng;
- cho vay theo món hoặc hạn mức thấu chi;
- thời gian vay có thể lên tới 60 tháng;
- không yêu cầu tài sản bảo đảm;
- áp dụng cho nhóm hưởng lương khu vực công/lực lượng vũ trang theo điều kiện sản phẩm.

### Ứng dụng

Phải có pipeline riêng cho thu nhập khu vực công:

```text
salary_coefficient
base_salary
position_allowance
seniority_allowance
professional_allowance
service_allowance
bonus
```

### Dataset cần có

- quyết định bổ nhiệm;
- quyết định nâng bậc lương;
- bảng lương theo hệ số;
- truy lĩnh do thay đổi lương cơ sở;
- phụ cấp phát sinh không đều;
- người lao động chuyển đơn vị;
- quyết định hết hiệu lực trong kỳ sao kê.

---

## 3.5. Vay tiêu dùng có tài sản bảo đảm

**URL:**  
https://www.shb.com.vn/vay-tieu-dung/

### Nội dung liên quan

Trang công khai thể hiện:

- tài trợ nhu cầu tiêu dùng;
- thời hạn dài;
- lịch trả nợ linh hoạt;
- có tài sản bảo đảm;
- khả năng trả nợ vẫn là đầu vào quan trọng.

### Ứng dụng

Dù có tài sản bảo đảm, agent vẫn cần phân tích:

```text
recurring_income
monthly_debt_service
income_after_debt
income_volatility
repayment_capacity
```

Không được giả định “có tài sản bảo đảm” thì không cần xác minh thu nhập.

---

## 3.6. “Tiêu dùng phong cách”

**URL:**  
https://www.shb.com.vn/tieu-dung-phong-cach/

### Nội dung liên quan

Trang nêu rõ hồ sơ thủ tục có thể bao gồm:

- đơn đề nghị vay vốn;
- giấy tờ tùy thân;
- giấy tờ tình trạng hôn nhân;
- hồ sơ tài sản bảo đảm;
- hồ sơ chứng minh thu nhập trả nợ;
- hồ sơ chứng minh mục đích vay.

### Ứng dụng

Đây là nguồn web SHB quan trọng để xác lập `document checklist`:

```text
identity_document
marital_status_document
income_proof
collateral_document
loan_purpose_document
```

Income Analysis Agent chỉ chạy khi bộ hồ sơ thu nhập đạt mức tối thiểu. Nếu thiếu:

```text
INCOME_DOCUMENT_MISSING
STATEMENT_MISSING
EMPLOYMENT_PROOF_MISSING
```

---

## 3.7. Giải pháp tài chính dành cho cán bộ nhân viên doanh nghiệp ưu tiên

**URL:**  
https://www.shb.com.vn/giai-phap-tai-chinh-toan-dien-danh-cho-can-bo-nhan-vien-doanh-nghiep-uu-tien-cua-shb/

### Nội dung liên quan

Trang mô tả:

- cấp thẻ qua kênh online;
- hạn mức thẻ cao tùy phân nhóm;
- các giải pháp hỗ trợ tài chính cho cán bộ nhân viên;
- quan hệ giữa employer segment và hạn mức.

### Ứng dụng

Cần đưa employer segmentation vào model dữ liệu, nhưng không để agent tự quyết định phân nhóm:

```text
employer_id
employer_segment
payroll_partnership
employee_position
employment_tenure
```

Employer segment là metadata do hệ thống/policy cung cấp, không nên suy luận chỉ từ tên công ty.

---

## 3.8. Gói tài chính dành cho cán bộ nhân viên Đại học Quốc gia Hà Nội

**URL:**  
https://www.shb.com.vn/goi-giai-phap-tai-chinh-toan-dien-danh-cho-can-bo-nhan-vien-dai-hoc-quoc-gia-ha-noi/

### Nội dung liên quan

Trang công khai nêu:

- hạn mức thấu chi;
- vay tín chấp tùy phân nhóm cán bộ nhân viên;
- ưu đãi lãi suất;
- quy trình online.

### Ứng dụng

Đây là ví dụ về chương trình theo tổ chức đối tác. Dataset cần có:

```text
partner_program
employer_match
employee_group
program_effective_period
```

Agent phải kiểm tra:

- tên đơn vị công tác có thuộc danh sách đối tác;
- thời gian làm việc;
- thu nhập chuyển từ đúng nguồn;
- chương trình còn hiệu lực hay không.

---

## 3.9. Chính sách ưu đãi cho cán bộ nhân viên VEC

**URL:**  
https://www.shb.com.vn/chinh-sach-uu-dai-danh-cho-can-bo-nhan-vien-tong-cong-ty-dau-tu-phat-trien-duong-cao-toc-viet-nam-vec/

### Nội dung liên quan

Trang nêu hạn mức thấu chi/vay món phụ thuộc phân nhóm cán bộ nhân viên và ưu đãi lãi suất.

### Ứng dụng

Cần mô hình hóa:

```text
employer_specific_program
employee_tier
income_multiple
maximum_program_limit
```

Không sử dụng một mức hạn mức chung cho mọi nhân viên cùng doanh nghiệp.

---

## 3.10. SHB cung cấp giải pháp cho đơn vị hành chính sự nghiệp

**URL:**  
https://www.shb.com.vn/shb-cung-cap-giai-phap-tai-chinh-toan-dien-cho-cac-don-vi-hanh-chinh-su-nghiep/

### Nội dung liên quan

Trang công bố các gói:

- tài khoản;
- chi trả lương;
- thấu chi;
- vay tiêu dùng không tài sản bảo đảm;
- ưu đãi cho cán bộ nhân viên đơn vị hành chính sự nghiệp.

### Ứng dụng

Agent cần phân biệt:

```text
government_payroll
public_service_unit_payroll
state_budget_payment
allowance_payment
salary_backpay
```

Tên đơn vị chuyển lương có thể là kho bạc, đơn vị chủ quản hoặc đơn vị chi trả tập trung, không nhất thiết trùng hoàn toàn tên employer trong quyết định.

---

## 3.11. S-Living – giải pháp cho cán bộ nhân viên SHB

**URL:**  
https://www.shb.com.vn/s-living-goi-giai-phap-tai-chinh-toan-dien-2/

### Nội dung liên quan

Trang công khai mô tả hạn mức vay theo số lần lương cho cán bộ nhân viên SHB và người thân.

### Ứng dụng

Nguồn này rất hữu ích để xây:

```text
income_multiple
employee_relationship
related_person_income_reference
```

Nhưng phải phân biệt:

- thu nhập của người vay;
- thu nhập của người đồng trả nợ;
- thu nhập của người thân dùng làm căn cứ chương trình;
- thu nhập không thuộc sở hữu/nghĩa vụ của người vay.

Không cộng thu nhập người thân vào thu nhập khách hàng nếu hồ sơ không xác lập nghĩa vụ đồng trả nợ.

---

## 3.12. Sản phẩm/giải pháp cho hộ kinh doanh

### Nguồn

- https://www.shb.com.vn/shb-cap-han-muc-thau-chi-len-toi-300-trieu-dong-ho-tro-khach-hang-mo-rong-kinh-doanh/
- https://www.shb.com.vn/goi-giai-phap-tai-chinh-toan-dien-cho-khach-hang-tieu-thuong-kinh-doanh-tuyen-pho/
- https://www.shb.com.vn/goi-giai-phap-tai-chinh-toan-dien-linh-hoat-va-tien-loi-danh-cho-khach-hang-tieu-thuong-kinh-doanh-online/
- https://www.shb.com.vn/giai-phap-danh-cho-ho-kinh-doanh-de-chuyen-doi-vung-kinh-doanh/

### Nội dung liên quan

Các trang công khai đề cập:

- hạn mức thấu chi phục vụ sản xuất kinh doanh;
- tài trợ theo tỷ lệ nhu cầu vốn;
- hồ sơ chứng minh doanh thu qua sao kê hoặc tờ khai thuế;
- thời gian hoạt động kinh doanh;
- quan hệ tín dụng hiện hữu;
- doanh thu từ thanh toán/nhận tiền.

### Ứng dụng

Đây là nhóm quan trọng để phân biệt **doanh thu** và **thu nhập ròng**:

```text
business_revenue
cost_of_goods
operating_expense
tax_payment
business_net_income
owner_draw
cash_sales
online_marketplace_settlement
```

### Rule bắt buộc

```text
business_revenue != eligible_personal_income
```

Agent phải có mô hình/logic riêng:

1. xác định doanh thu;
2. loại giao dịch nội bộ;
3. loại khoản vay;
4. ước tính chi phí theo hồ sơ hoặc policy;
5. xác định lợi nhuận/thu nhập khả dụng;
6. chuyển trường hợp thiếu dữ liệu sang review.

### Cờ rủi ro

```text
HIGH_CASH_DEPOSIT_RATIO
REVENUE_CONCENTRATION
MARKETPLACE_SETTLEMENT_VOLATILITY
BUSINESS_PERSONAL_ACCOUNT_MIX
TAX_DECLARATION_MISMATCH
```

---

## 3.13. Vay online cầm cố sổ tiết kiệm

**URL:**  
https://www.shb.com.vn/vay-online-cam-co-so-tiet-kiem/

### Nội dung liên quan

Trang công khai nêu:

- hạn mức dựa trên giá trị sổ tiết kiệm;
- tỷ lệ cho vay trên giá trị sổ;
- kỳ hạn;
- lãi suất vay gắn với lãi suất tiền gửi.

### Ứng dụng

Agent cần phân biệt:

- tiền gửi là tài sản;
- lãi tiền gửi là thu nhập;
- khoản vay cầm cố không phải thu nhập;
- tiền giải ngân từ khoản vay không phải dòng tiền thu nhập.

Nhãn:

```text
DEPOSIT_PRINCIPAL
DEPOSIT_INTEREST
SECURED_LOAN_DISBURSEMENT
DEPOSIT_MATURITY_PROCEEDS
```

---

## 3.14. Công bố lãi suất cho vay bình quân

**URL:**  
https://www.shb.com.vn/cong-bo-lai-suat-binh-quan/

### Nội dung liên quan

SHB định kỳ công bố:

- lãi suất cho vay bình quân;
- lãi suất bình quân cho vay ngắn hạn phục vụ nhu cầu đời sống/tiêu dùng;
- chênh lệch giữa lãi suất cho vay và huy động.

### Ứng dụng

Không dùng trực tiếp để xác định thu nhập, nhưng dùng cho:

- synthetic repayment calculation;
- stress test;
- kiểm tra hợp lý của lãi suất trên hợp đồng;
- ước tính nghĩa vụ nợ khi thiếu lịch trả nợ, với trạng thái `estimated`.

```text
interest_rate_source
rate_month
estimated_payment
estimation_confidence
```

Không thay lãi suất hợp đồng bằng lãi suất bình quân.

---

## 3.15. Các bài viết lịch sử về tín chấp và thấu chi

### Nguồn

- https://www.shb.com.vn/shb-trien-khai-cho-vay-tin-chap-tieu-dung-va-thau-chi-khong-co-tai-san-dam-bao/
- Các bài viết sản phẩm/lãi suất lịch sử khác trên SHB.

### Ứng dụng

Các bài viết cũ cho thấy:

- ngưỡng thu nhập;
- hạn mức;
- thời hạn;
- chính sách có thể thay đổi đáng kể.

Giá trị chính là tạo test cho `policy versioning`.

```text
source_status: historical
usable_for_current_decision: false
```

---

# 4. Các văn bản Chính phủ và cơ quan nhà nước

## 4.1. Luật Các tổ chức tín dụng hiện hành

### Nguồn

- Luật Các tổ chức tín dụng và văn bản hợp nhất hiện hành trên Cổng văn bản Chính phủ.
- Cần tra cứu theo thời điểm production để dùng bản có hiệu lực mới nhất.

### Ứng dụng

Luật là nền tảng cho:

- cấp tín dụng;
- bảo mật thông tin khách hàng;
- quản trị rủi ro;
- trách nhiệm của tổ chức tín dụng;
- lưu trữ và kiểm soát dữ liệu.

### Yêu cầu đối với agent

1. Kết quả phân tích là dữ liệu hỗ trợ.
2. Không tự phê duyệt/từ chối.
3. Mọi truy cập phải có phân quyền.
4. Không xuất sao kê và dữ liệu thu nhập ra ngoài mặc định.
5. Có audit log.
6. Có khả năng tái hiện cách tính.

Schema audit:

```json
{
  "analysis_id": "",
  "customer_id": "",
  "input_document_ids": [],
  "model_version": "",
  "policy_version": "",
  "calculation_version": "",
  "reviewer": null,
  "created_at": "",
  "updated_at": ""
}
```

---

## 4.2. Thông tư 39/2016/TT-NHNN

**Nguồn:**  
https://vanban.chinhphu.vn/?docid=188822&pageid=27160

### Nội dung liên quan

Thông tư quy định hoạt động cho vay của tổ chức tín dụng đối với khách hàng.

Đối với Income Analysis Agent, các khái niệm quan trọng:

- nhu cầu vay vốn;
- mục đích vay;
- khả năng tài chính;
- nguồn trả nợ;
- thời hạn vay;
- phương thức trả nợ;
- lãi suất;
- phí;
- kiểm tra, giám sát sử dụng vốn;
- thỏa thuận cho vay.

### Áp dụng cụ thể

Agent phải tách:

```text
declared_income
document_verified_income
cashflow_verified_income
eligible_income
repayment_source
monthly_debt_obligation
```

Không được sử dụng một trường `income` duy nhất.

### Evidence requirement

Mỗi con số phải chỉ ra:

- tài liệu;
- kỳ;
- giao dịch;
- rule;
- lý do bao gồm/loại trừ.

---

## 4.3. Thông tư 06/2023/TT-NHNN

### Ứng dụng

Đây là văn bản sửa đổi Thông tư 39. Dataset pháp lý phải lưu quan hệ:

```text
amends: 39/2016/TT-NHNN
```

Không trộn nội dung sửa đổi thành một văn bản phẳng mà mất thông tin hiệu lực.

---

## 4.4. Thông tư 10/2023/TT-NHNN

**Nguồn:**  
https://vanban.chinhphu.vn/?classid=1&docid=208559&pageid=27160&typegroupid=6

### Nội dung liên quan

Văn bản ngưng hiệu lực một số nội dung đã được bổ sung vào Thông tư 39.

### Ứng dụng

Policy engine và dataset cần hỗ trợ:

```text
ACTIVE
SUSPENDED
REPEALED
UPCOMING
HISTORICAL
```

Một đoạn quy định xuất hiện trong văn bản chưa chắc đang áp dụng.

---

## 4.5. Thông tư 52/2025/TT-NHNN

**Nguồn:**  
https://vanban.chinhphu.vn/?docid=216369&pageid=27160

### Nội dung liên quan

Văn bản tiếp tục sửa đổi Thông tư 39 và có hiệu lực từ ngày ban hành theo thông tin công bố.

### Ứng dụng

Khi phân tích hồ sơ năm 2026, cần sử dụng policy snapshot đã hợp nhất các thay đổi đến thời điểm xử lý.

---

## 4.6. Thông tư 29/2026/TT-NHNN

**Nguồn:**  
https://vanban.chinhphu.vn/?classid=1&docid=218709&orggroupid=4&pageid=27160

### Nội dung liên quan

- Ban hành ngày 30/06/2026.
- Có hiệu lực từ 15/08/2026.
- Sửa đổi Thông tư 39.

### Ứng dụng

Tại ngày lập tài liệu 18/07/2026:

```yaml
status: upcoming
effective_from: 2026-08-15
```

Không dùng làm rule hiện hành trước ngày hiệu lực, nhưng phải đưa vào test regression và kế hoạch cập nhật production.

---

# 5. Pháp luật lao động và cấu trúc thu nhập

## 5.1. Bộ luật Lao động 2019

### Nội dung cần chuyển thành ontology

Thu nhập từ lao động có thể bao gồm:

```text
base_salary
position_salary
allowance
additional_payment
overtime_pay
night_work_pay
bonus
commission
backpay
```

### Ứng dụng

Agent phải phân biệt:

- lương ghi trong hợp đồng;
- lương thực trả;
- phụ cấp cố định;
- khoản bổ sung xác định được mức tiền;
- khoản biến đổi theo hiệu suất;
- thưởng;
- làm thêm giờ;
- khấu trừ;
- trả chậm/truy lĩnh.

### Rule consistency

```text
net_salary = gross_salary - tax - employee_insurance - other_deductions
```

Chênh lệch giữa lương hợp đồng và tiền về tài khoản không tự động là bất thường.

### Case cần có

- trả lương hai lần/tháng;
- lương và phụ cấp tách giao dịch;
- phụ lục tăng lương giữa tháng;
- truy lĩnh;
- thưởng cuối năm;
- nghỉ không lương;
- khấu trừ tạm ứng.

---

## 5.2. Nghị định 145/2020/NĐ-CP

**Nguồn:**  
https://vanban.chinhphu.vn/?docid=201967&pageid=27160

### Ứng dụng

Nghị định hướng dẫn Bộ luật Lao động về điều kiện lao động và quan hệ lao động.

Dataset nên chứa:

```text
employment_contract
employment_appendix
salary_adjustment
overtime_record
bonus_decision
payroll
termination_document
```

Agent cần xử lý:

- thời giờ làm việc;
- làm thêm;
- thay đổi điều kiện lao động;
- các khoản trả liên quan tới quan hệ lao động;
- hiệu lực của phụ lục.

---

## 5.3. Quy định về lương tối thiểu vùng

### Ứng dụng

Mức lương tối thiểu dùng làm `plausibility check`, không dùng để xác định thu nhập thực tế.

```text
work_region
minimum_wage_effective_period
base_salary_below_minimum_flag
```

Cờ chỉ tạo cảnh báo, vì:

- người lao động có thể làm không trọn thời gian;
- hồ sơ có thể thuộc kỳ cũ;
- số tiền trên sao kê là ròng;
- có sai lệch do OCR;
- có quy chế lương khác theo đối tượng.

---

## 5.4. Nghị định 73/2024/NĐ-CP

**Nguồn:**  
https://vanban.chinhphu.vn/?docid=210537&pageid=27160

### Nội dung liên quan

Quy định về mức lương cơ sở và chế độ tiền thưởng đối với một số đối tượng khu vực công.

### Ứng dụng

```text
calculated_salary = salary_coefficient × base_salary
```

Cần cộng các khoản phụ cấp theo đúng căn cứ và kỳ hiệu lực.

### Không được làm

- dùng mức lương cơ sở hiện tại cho kỳ sao kê quá khứ;
- coi mọi khoản truy lĩnh là thu nhập hàng tháng;
- coi tiền thưởng là thu nhập cố định.

---

# 6. Thuế thu nhập cá nhân

## 6.1. Văn bản hợp nhất Luật Thuế thu nhập cá nhân 112/VBHN-VPQH

**Nguồn:**  
https://vanban.chinhphu.vn/?docid=218215&pageid=27160

### Nội dung liên quan

Văn bản hợp nhất được công bố ngày 20/05/2026.

Thu nhập có thể phát sinh từ:

- tiền lương, tiền công;
- kinh doanh;
- đầu tư vốn;
- chuyển nhượng vốn;
- chuyển nhượng bất động sản;
- bản quyền;
- nhượng quyền;
- trúng thưởng;
- thừa kế;
- quà tặng.

### Ứng dụng

Không phải mọi thu nhập chịu thuế đều là thu nhập ổn định phục vụ trả nợ.

Bộ nhãn:

```text
EMPLOYMENT_INCOME
BUSINESS_INCOME
INVESTMENT_INCOME
CAPITAL_TRANSFER_INCOME
PROPERTY_TRANSFER_INCOME
ROYALTY_INCOME
FRANCHISE_INCOME
PRIZE_INCOME
INHERITANCE
GIFT
```

### Quy tắc

| Loại | Định kỳ | Khả năng tính vào eligible income |
|---|---:|---|
| Lương | thường có | theo policy |
| Kinh doanh | biến động | cần xác định lợi nhuận |
| Lãi đầu tư | tùy loại | cần lịch sử |
| Chuyển nhượng tài sản | thường một lần | thường loại/giảm trọng số |
| Quà tặng | một lần | không coi là thu nhập ổn định |
| Trúng thưởng | một lần | loại khỏi recurring income |

---

## 6.2. Luật Thuế thu nhập cá nhân và luật sửa đổi

### Nguồn

- https://vanban.chinhphu.vn/?docid=51258&pageid=27160
- https://vanban.chinhphu.vn/default.aspx?docid=164952&pageid=27160

### Ứng dụng

Văn bản xác định:

- đối tượng nộp thuế;
- thu nhập chịu thuế;
- thời điểm xác định thu nhập;
- giảm trừ;
- trách nhiệm khấu trừ/kê khai.

Agent có thể đối chiếu:

```text
income_payment_date
tax_withholding_date
taxable_income
tax_withheld
income_payer
```

Không sử dụng mức giảm trừ lịch sử cho kỳ hiện tại.

---

## 6.3. Thông tư 111/2013/TT-BTC và văn bản sửa đổi

### Ứng dụng

Đây là nguồn chi tiết để:

- phân loại thu nhập từ tiền lương, tiền công;
- phân biệt khoản chịu thuế và miễn thuế;
- xử lý khấu trừ;
- hiểu chứng từ khấu trừ thuế;
- đối chiếu thu nhập gross/net.

### Model dữ liệu

```text
gross_income
taxable_income
tax_exempt_component
personal_deduction
dependent_deduction
tax_withheld
net_income
```

### Cảnh báo

Không suy ngược chính xác gross từ net nếu thiếu:

- số người phụ thuộc;
- khoản bảo hiểm;
- khoản miễn thuế;
- thu nhập ở nơi khác;
- quyết toán thuế.

Kết quả suy ngược phải có:

```text
is_estimated: true
assumptions: []
confidence: low_or_medium
```

---

# 7. Bảo hiểm xã hội và thu nhập thay thế

## 7.1. Luật Bảo hiểm xã hội 41/2024/QH15

**Nguồn:**  
https://vanban.chinhphu.vn/?docid=211199&pageid=27160

### Thông tin hiệu lực

- Ban hành 29/06/2024.
- Có hiệu lực 01/07/2025.

### Ứng dụng

Agent phải phân biệt:

```text
salary_income
social_insurance_contribution
pension
maternity_benefit
sickness_benefit
one_time_social_insurance
survivor_benefit
```

### Rule

- lương hưu có thể là thu nhập định kỳ;
- trợ cấp thai sản/ốm đau thường là thu nhập thay thế có thời hạn;
- BHXH một lần không phải recurring income;
- khoản hoàn hoặc trợ cấp bất thường không nên annualize.

---

## 7.2. Nghị định 158/2025/NĐ-CP

**Nguồn:**  
https://vanban.chinhphu.vn/?docid=214189&pageid=27160

### Nội dung liên quan

Quy định chi tiết BHXH bắt buộc.

### Ứng dụng

Hỗ trợ đối chiếu:

- đối tượng tham gia;
- căn cứ đóng;
- các khoản đóng;
- chế độ hưởng;
- thời kỳ áp dụng.

Agent có thể phát hiện:

```text
INSURANCE_DEDUCTION_MISSING
INSURANCE_BENEFIT_MISCLASSIFIED
GROSS_NET_RECONCILIATION_GAP
```

---

## 7.3. Nghị định 157/2025/NĐ-CP

**Nguồn:**  
https://vanban.chinhphu.vn/?docid=214191&pageid=27160

### Ứng dụng

Áp dụng cho một số nhóm quân nhân, công an, dân quân thường trực và người làm công tác cơ yếu.

Đây là nhóm có:

- cấu trúc lương/phụ cấp riêng;
- chứng từ riêng;
- nguồn chi trả đặc thù.

Agent không nên áp dụng một ontology quá đơn giản chỉ gồm `base_salary + bonus`.

---

# 8. Phòng, chống rửa tiền và bất thường dòng tiền

## 8.1. Luật Phòng, chống rửa tiền 2022

### Ứng dụng

Income Analysis Agent chỉ tạo cờ, không kết luận vi phạm.

Cờ gợi ý:

```text
NON_EMPLOYER_SALARY_CREDIT
RAPID_IN_OUT
CIRCULAR_TRANSFER
MULTIPLE_UNRELATED_PAYERS
LARGE_PRE_APPLICATION_CREDIT
INCOME_OCCUPATION_MISMATCH
STRUCTURED_CASH_DEPOSITS
```

### Evidence

```json
{
  "flag": "RAPID_IN_OUT",
  "incoming_transaction": "",
  "outgoing_transactions": [],
  "time_gap_hours": 3,
  "amount_ratio": 0.96,
  "confidence": 0.91
}
```

---

## 8.2. Nghị định 19/2023/NĐ-CP và hướng dẫn NHNN

### Ứng dụng

Các trường cần chuẩn hóa:

```text
occupation
employer
source_of_income
source_of_funds
counterparty
beneficial_owner
transaction_purpose
```

Không được biến `source_of_funds` thành `eligible_income` một cách tự động.

---

# 9. Dữ liệu cá nhân

## 9.1. Nghị định 13/2023/NĐ-CP

### Ứng dụng

Income Analysis Agent xử lý dữ liệu nhạy cảm:

- thu nhập;
- tài khoản;
- giao dịch;
- nợ;
- thuế;
- bảo hiểm;
- nghề nghiệp;
- người phụ thuộc.

### Yêu cầu

```yaml
purpose_limitation: true
data_minimization: true
role_based_access: true
masking: true
audit_log: true
retention_policy: required
training_reuse: prohibited_by_default
```

### Dataset

Không đưa dữ liệu khách hàng production vào train nếu chưa:

1. xác định cơ sở xử lý;
2. được phê duyệt;
3. giả danh hóa/ẩn danh;
4. loại định danh trực tiếp;
5. đánh giá khả năng tái nhận diện;
6. giới hạn truy cập;
7. có quy trình xóa.

---

# 10. Transaction ontology đề xuất

```text
SALARY_REGULAR
SALARY_SPLIT_PAYMENT
SALARY_BACKPAY
BONUS_PERFORMANCE
BONUS_ANNUAL
OVERTIME
FIXED_ALLOWANCE
VARIABLE_ALLOWANCE
COMMISSION
PENSION
SOCIAL_INSURANCE_BENEFIT
RENTAL_INCOME
BUSINESS_REVENUE
BUSINESS_NET_INCOME
DIVIDEND
INTEREST_INCOME
CASH_DEPOSIT
INTERNAL_TRANSFER
FAMILY_TRANSFER
LOAN_DISBURSEMENT
LOAN_REPAYMENT
OVERDRAFT_DRAW
OVERDRAFT_REPAYMENT
REFUND
REVERSAL
ASSET_SALE
GIFT
UNKNOWN_CREDIT
```

---

# 11. Công thức và chỉ tiêu phân tích

## 11.1. Thu nhập bình quân

```text
average_verified_income =
    sum(verified_income_by_month) / number_of_valid_months
```

Không tính tháng thiếu dữ liệu như tháng có thu nhập bằng 0 nếu thiếu do sao kê không đầy đủ.

## 11.2. Thu nhập ổn định

```text
stable_income =
    recurring_salary
  + accepted_fixed_allowances
  + accepted_recurring_other_income
```

## 11.3. Thu nhập đủ điều kiện

```text
eligible_income =
    stable_income
  + accepted_percentage_of_variable_income
  - excluded_income
```

Tỷ lệ chấp nhận phải lấy từ policy version, không suy ra từ nguồn marketing.

## 11.4. DTI

```text
DTI =
    total_monthly_debt_obligation / eligible_monthly_income
```

Cần lưu:

```text
dti_numerator_components
dti_denominator_components
dti_policy_version
```

## 11.5. Độ biến động

```text
income_cv = standard_deviation(monthly_income) / mean(monthly_income)
```

Không dùng CV khi số tháng quá ít hoặc mean gần 0.

---

# 12. Output schema đề xuất

```json
{
  "analysis_id": "",
  "customer_id": "",
  "period": {
    "from": "",
    "to": ""
  },
  "declared_income": 0,
  "verified_income": 0,
  "stable_income": 0,
  "variable_income": 0,
  "one_off_income": 0,
  "excluded_income": 0,
  "eligible_income": 0,
  "monthly_debt_obligation": 0,
  "dti": null,
  "income_sources": [],
  "monthly_breakdown": [],
  "transactions": [],
  "risk_flags": [],
  "assumptions": [],
  "policy_version": "",
  "model_version": "",
  "evidence": [],
  "review_required": false
}
```

---

# 13. Bộ case bắt buộc cho dataset

1. Lương một lần/tháng.
2. Lương chia hai giao dịch.
3. Lương từ công ty mẹ.
4. Tên employer viết tắt.
5. Lương không dấu.
6. Thưởng Tết.
7. Thưởng KPI.
8. Truy lĩnh.
9. Điều chỉnh lương giữa kỳ.
10. Nghỉ không lương.
11. Thai sản.
12. Lương hưu.
13. Tự nộp tiền mặt và khai là lương.
14. Người thân chuyển tiền.
15. Vay tạm rồi chuyển vào.
16. Chuyển giữa tài khoản cùng chủ.
17. Tiền vào rồi chuyển ra ngay.
18. Thu nhập cho thuê nhà.
19. Doanh thu hộ kinh doanh.
20. Thanh toán từ sàn thương mại điện tử.
21. Thu nhập ngoại tệ.
22. Sao kê thiếu tháng.
23. Giao dịch đảo.
24. Khoản hoàn tiền.
25. Giải ngân khoản vay.
26. Tất toán tiền gửi.
27. Lãi tiền gửi.
28. Nhiều employer trong một kỳ.
29. Hợp đồng hết hạn giữa kỳ.
30. Lương khu vực công theo hệ số.

---

# 14. Tiêu chí nghiệm thu

## Phân loại giao dịch

- Accuracy/F1 theo từng nhãn.
- Không chỉ báo macro average; phải có metric cho nhãn hiếm.
- Đặc biệt đo lỗi `LOAN_DISBURSEMENT → SALARY`.

## Tính toán

- Đối chiếu tổng theo tháng.
- Đối chiếu gross/net.
- Đối chiếu DTI.
- Kiểm thử rounding.
- Kiểm thử nhiều đồng tiền.

## Giải thích

Mỗi kết quả phải có:

```text
source_document
transaction_id
source_text
rule
included_or_excluded
reason
confidence
```

## Human review

Bắt buộc review nếu:

- confidence thấp;
- dữ liệu thiếu;
- employer không khớp;
- thu nhập biến động mạnh;
- business income;
- giao dịch tiền mặt chiếm tỷ trọng cao;
- policy không xác định được phiên bản;
- kết quả ảnh hưởng lớn tới DTI.

---

# 15. Danh mục URL SHB web đã rà soát

1. https://www.shb.com.vn/tin-chap-tieu-dung/
2. https://www.shb.com.vn/vay-thau-chi-online-tin-chap/
3. https://www.shb.com.vn/can-tien-co-lien-thau-chi/
4. https://www.shb.com.vn/vay-tieu-dung-khong-tai-san-bao-dam-danh-cho-can-bo-cong-chuc-vien-chuc-luc-luong-vu-trang/
5. https://www.shb.com.vn/vay-tieu-dung/
6. https://www.shb.com.vn/tieu-dung-phong-cach/
7. https://www.shb.com.vn/giai-phap-tai-chinh-toan-dien-danh-cho-can-bo-nhan-vien-doanh-nghiep-uu-tien-cua-shb/
8. https://www.shb.com.vn/goi-giai-phap-tai-chinh-toan-dien-danh-cho-can-bo-nhan-vien-dai-hoc-quoc-gia-ha-noi/
9. https://www.shb.com.vn/chinh-sach-uu-dai-danh-cho-can-bo-nhan-vien-tong-cong-ty-dau-tu-phat-trien-duong-cao-toc-viet-nam-vec/
10. https://www.shb.com.vn/shb-cung-cap-giai-phap-tai-chinh-toan-dien-cho-cac-don-vi-hanh-chinh-su-nghiep/
11. https://www.shb.com.vn/s-living-goi-giai-phap-tai-chinh-toan-dien-2/
12. https://www.shb.com.vn/shb-cap-han-muc-thau-chi-len-toi-300-trieu-dong-ho-tro-khach-hang-mo-rong-kinh-doanh/
13. https://www.shb.com.vn/goi-giai-phap-tai-chinh-toan-dien-cho-khach-hang-tieu-thuong-kinh-doanh-tuyen-pho/
14. https://www.shb.com.vn/goi-giai-phap-tai-chinh-toan-dien-linh-hoat-va-tien-loi-danh-cho-khach-hang-tieu-thuong-kinh-doanh-online/
15. https://www.shb.com.vn/giai-phap-danh-cho-ho-kinh-doanh-de-chuyen-doi-vung-kinh-doanh/
16. https://www.shb.com.vn/vay-online-cam-co-so-tiet-kiem/
17. https://www.shb.com.vn/cong-bo-lai-suat-binh-quan/
18. https://www.shb.com.vn/shb-trien-khai-cho-vay-tin-chap-tieu-dung-va-thau-chi-khong-co-tai-san-dam-bao/
19. https://www.shb.com.vn/category/khach-hang-ca-nhan/tin-dung/cho-vay-tieu-dung/
20. https://www.shb.com.vn/thau-chi-ngay-qua-ve-tay/

---

# 16. Danh mục nguồn Chính phủ trọng yếu

1. Thông tư 39/2016/TT-NHNN  
   https://vanban.chinhphu.vn/?docid=188822&pageid=27160

2. Thông tư 10/2023/TT-NHNN  
   https://vanban.chinhphu.vn/?classid=1&docid=208559&pageid=27160&typegroupid=6

3. Thông tư 52/2025/TT-NHNN  
   https://vanban.chinhphu.vn/?docid=216369&pageid=27160

4. Thông tư 29/2026/TT-NHNN  
   https://vanban.chinhphu.vn/?classid=1&docid=218709&orggroupid=4&pageid=27160

5. Nghị định 145/2020/NĐ-CP  
   https://vanban.chinhphu.vn/?docid=201967&pageid=27160

6. Nghị định 73/2024/NĐ-CP  
   https://vanban.chinhphu.vn/?docid=210537&pageid=27160

7. Văn bản hợp nhất Luật Thuế thu nhập cá nhân 112/VBHN-VPQH  
   https://vanban.chinhphu.vn/?docid=218215&pageid=27160

8. Luật Thuế thu nhập cá nhân  
   https://vanban.chinhphu.vn/?docid=51258&pageid=27160

9. Luật sửa đổi Luật Thuế thu nhập cá nhân  
   https://vanban.chinhphu.vn/default.aspx?docid=164952&pageid=27160

10. Luật Bảo hiểm xã hội 41/2024/QH15  
    https://vanban.chinhphu.vn/?docid=211199&pageid=27160

11. Nghị định 158/2025/NĐ-CP  
    https://vanban.chinhphu.vn/?docid=214189&pageid=27160

12. Nghị định 157/2025/NĐ-CP  
    https://vanban.chinhphu.vn/?docid=214191&pageid=27160

---

# 17. Kết luận

Các nguồn web SHB cho thấy Income Analysis Agent phải hỗ trợ nhiều mô hình thu nhập:

- lương doanh nghiệp;
- lương khu vực công;
- thu nhập hộ kinh doanh;
- lãi tiền gửi;
- lương hưu và trợ cấp;
- thu nhập biến đổi;
- thu nhập của người đồng trả nợ;
- dòng tiền có liên quan đến thấu chi và tín dụng.

Nguồn Chính phủ cung cấp ontology và giới hạn pháp lý để:

- phân biệt các loại thu nhập;
- đối chiếu gross/net;
- hiểu khấu trừ thuế và bảo hiểm;
- quản lý hiệu lực chính sách;
- bảo vệ dữ liệu;
- phát hiện bất thường mà không tự kết luận vi phạm.

MVP nên ưu tiên:

```text
SALARY_REGULAR
SALARY_SPLIT_PAYMENT
BONUS
ALLOWANCE
BACKPAY
PENSION
BUSINESS_REVENUE
INTERNAL_TRANSFER
LOAN_DISBURSEMENT
CASH_DEPOSIT
```

Đồng thời bắt buộc lưu:

```text
value
period
source
evidence
confidence
inclusion_status
exclusion_reason
policy_version
```
