---
dataset_id: REF-POLICY-NOTES-001
dataset_type: REFERENCE_NOTE
target_agent: POLICY_AGENT
domain: INCOME_VERIFICATION
product: UNSECURED_PERSONAL_LOAN
document_name: SHB and Government Web Source Review Notes
document_version: "2026-07-18"
issuer: PROJECT_RESEARCH_NOTES
approval_status: PENDING_REVIEW
effective_date: null
effective_to: null
language: vi
synthetic: false
production_use: prohibited
source_kind: PUBLIC_WEB_RESEARCH
---

# Ghi chú chi tiết nguồn Chính phủ và nguồn web SHB phục vụ Policy Agent

**Dự án:** MAS hỗ trợ thẩm định tín dụng và xác minh thu nhập tại SHB  
**Thành phần chính:** Policy Agent  
**Thành phần liên quan:** Document Extraction Agent, Income Analysis Agent, Consistency Agent, Recommendation Builder  
**Ngày rà soát:** 18/07/2026  
**Phạm vi tài liệu này:**

- Các nguồn chính thức của Quốc hội, Chính phủ và Ngân hàng Nhà nước có liên quan tới điều kiện cấp tín dụng, chính sách sản phẩm, phân loại nợ, tài sản bảo đảm, tài khoản, thẻ, dữ liệu cá nhân, giao dịch điện tử, bảo vệ người tiêu dùng, AML và xác minh thu nhập.
- Các trang web HTML công khai của SHB có liên quan tới chính sách sản phẩm nhưng **không phải file PDF/tệp tải trực tiếp**.
- Tóm tắt nội dung có thể chuyển thành ontology, rule, metadata, test case hoặc dữ liệu RAG cho Policy Agent.

> **Giới hạn tính đầy đủ:** “Tất cả nguồn” được hiểu là rà soát tối đa các nguồn công khai, truy cập được và được công cụ tìm kiếm lập chỉ mục tại thời điểm lập tài liệu. Website có thể tồn tại trang đã gỡ, trang động, nội dung chỉ hiển thị theo phiên đăng nhập hoặc nguồn nội bộ không được công khai.
>
> **Nguyên tắc sử dụng:** Trang sản phẩm và tin bài SHB chỉ là nguồn tham chiếu công khai. Không được hard-code thành chính sách production nếu chưa được chủ sở hữu chính sách SHB xác nhận. Văn bản pháp luật phải được kiểm tra hiệu lực và văn bản sửa đổi tại đúng ngày xử lý hồ sơ.
>
> **Lưu ý thuật ngữ:** Trong yêu cầu có nhắc “document agent”, nhưng theo ngữ cảnh dự án, tài liệu này được tối ưu cho **Policy Agent**. Các phần liên quan đến extraction được ghi rõ để Document Extraction Agent tạo đúng đầu vào cho Policy Agent.

---

# 1. Vai trò của Policy Agent trong kiến trúc MAS

Policy Agent nhận dữ liệu đã chuẩn hóa từ Document Extraction Agent và Income Analysis Agent, sau đó:

1. Xác định đúng sản phẩm, phân khúc khách hàng và phiên bản chính sách.
2. Kiểm tra điều kiện vay, mục đích vay và hồ sơ bắt buộc.
3. Kiểm tra giới hạn hạn mức, thời hạn, tỷ lệ tài trợ, DTI, LTV và nghĩa vụ nợ.
4. Kiểm tra tài sản bảo đảm, chủ sở hữu và hiệu lực giao dịch bảo đảm.
5. Kiểm tra trạng thái nợ hiện hữu và điều kiện escalation.
6. Kiểm tra điều khoản lãi, phí, trả nợ trước hạn và ưu đãi.
7. Kiểm tra yêu cầu KYC, AML, dữ liệu cá nhân và bảo vệ người tiêu dùng.
8. Trả kết quả có điều kiện, căn cứ, ngoại lệ và trích dẫn.
9. Chuyển trường hợp không xác định hoặc cần phán đoán sang chuyên viên.
10. Không tự phê duyệt/từ chối nếu action chưa được cấp thẩm quyền.

## Output tối thiểu

```json
{
  "policy_decision": "PASS | FAIL | REVIEW | NOT_APPLICABLE",
  "rule_id": "",
  "condition_evaluated": {},
  "result": {},
  "reason": "",
  "legal_basis": [],
  "shb_policy_basis": [],
  "effective_date": "",
  "evidence": [],
  "exception": null,
  "human_review_required": false
}
```

---

# 2. Cấu trúc dữ liệu policy nên sử dụng

Không lưu toàn bộ văn bản dưới dạng một đoạn text phẳng. Mỗi policy unit cần có cấu trúc:

```json
{
  "policy_id": "",
  "title": "",
  "issuer": "SHB | NHNN | GOVERNMENT | NATIONAL_ASSEMBLY",
  "document_number": "",
  "document_type": "",
  "product": "",
  "customer_segment": "",
  "jurisdiction": "VN",
  "published_date": null,
  "effective_from": null,
  "effective_to": null,
  "status": "ACTIVE | UPCOMING | SUSPENDED | REPEALED | HISTORICAL",
  "supersedes": [],
  "superseded_by": [],
  "amends": [],
  "conditions": [],
  "exceptions": [],
  "required_documents": [],
  "actions": [],
  "citations": [],
  "source_url": "",
  "source_hash": ""
}
```

---

# 3. Nguồn web SHB không phải file tải trực tiếp

## 3.1. Vay thấu chi online tín chấp

**URL:**  
https://www.shb.com.vn/vay-thau-chi-online-tin-chap/

### Nội dung công khai

Trang sản phẩm nêu:

- đăng ký online trên SHB Mobile;
- không yêu cầu tài sản bảo đảm;
- mục đích vay tiêu dùng;
- hạn mức thấu chi công khai tối đa theo chương trình;
- thời gian duy trì hạn mức 12 tháng;
- gốc trả linh hoạt;
- lãi tính trên số tiền thực tế sử dụng;
- ưu đãi miễn lãi khi trả trong ngày theo điều kiện sản phẩm.

### Ứng dụng Policy Agent

Rule group:

```text
PRODUCT_ELIGIBILITY
OVERDRAFT_LIMIT
OVERDRAFT_TENOR
UNSECURED_PRODUCT
CONSUMER_PURPOSE
DIGITAL_CHANNEL
```

Các biến:

```text
customer_segment
channel
requested_overdraft_limit
approved_overdraft_limit
overdraft_expiry_date
secured
loan_purpose
```

### Điều cần kiểm tra

- Trang sản phẩm có thể thay đổi theo chiến dịch.
- Hạn mức “tối đa” không phải hạn mức đương nhiên.
- Điều kiện thực tế phải lấy từ chính sách nội bộ và điều khoản hợp đồng.
- Không dùng giá trị trên trang nếu ngày hiệu lực không khớp ngày phê duyệt.

### Đầu vào Document Extraction Agent cần cung cấp

```text
application_date
product_code
requested_limit
loan_purpose
customer_id
employment_information
income_information
existing_credit_obligations
```

---

## 3.2. “Cần tiền – Có liền thấu chi”

**URL:**  
https://www.shb.com.vn/can-tien-co-lien-thau-chi/

### Nội dung công khai

Trang chương trình mô tả:

- hạn mức thấu chi có thể lên đến mức cao tùy điều kiện;
- thực hiện online;
- lãi theo số tiền và thời gian sử dụng;
- có ưu đãi khi hoàn trả trong ngày;
- áp dụng cho nhóm khách hàng đủ điều kiện của SHB.

### Ứng dụng

Phân biệt:

```text
campaign_limit
standard_product_limit
promotional_interest
standard_interest
same_day_repayment
promotion_period
```

### Quy tắc ưu tiên nguồn

```text
general_terms > approved_internal_policy > product_page > campaign_article
```

Trang chiến dịch không được dùng để vượt giới hạn được quy định trong điều khoản hoặc policy nội bộ.

---

## 3.3. Vay tiêu dùng không tài sản bảo đảm

**URL:**  
https://www.shb.com.vn/tin-chap-tieu-dung/

### Nội dung công khai

Trang nêu:

- vay tiêu dùng không có tài sản bảo đảm;
- hạn mức và thời hạn tối đa theo sản phẩm;
- có thể cấp theo món hoặc hạn mức;
- khả năng trả nợ dựa trên thu nhập và hồ sơ khách hàng.

### Policy concepts

```text
unsecured_loan
loan_method
loan_limit
loan_tenor
income_based_repayment
consumer_purpose
```

### Rule candidate

```text
Nếu secured = false:
    áp dụng policy tín chấp
    kiểm tra tổng dư nợ tín chấp
    kiểm tra DTI
    kiểm tra lịch sử tín dụng
```

### Không được suy luận

- Trang không thể hiện đầy đủ khẩu vị rủi ro.
- Hạn mức công khai không thay thế hạn mức theo income multiple.
- “Đủ điều kiện sản phẩm” không đồng nghĩa “được phê duyệt”.

---

## 3.4. Tin lịch sử về vay tín chấp và thấu chi

**URL:**  
https://www.shb.com.vn/shb-trien-khai-cho-vay-tin-chap-tieu-dung-va-thau-chi-khong-co-tai-san-dam-bao/

### Nội dung công khai

Tin lịch sử mô tả:

- nhóm cán bộ nhân viên tại tổ chức nhà nước, tổ chức tài chính, bệnh viện, trường học và doanh nghiệp;
- ngưỡng thu nhập tối thiểu tại thời điểm chương trình cũ;
- hạn mức và thời gian vay lịch sử;
- nguồn trả nợ từ lương, trợ cấp và thu nhập hợp pháp.

### Ứng dụng

Nguồn này đặc biệt có giá trị cho kiểm thử policy drift:

```yaml
source_status: historical
usable_for_current_decision: false
```

### Test case

- Hồ sơ năm 2014 không được đánh giá bằng policy năm 2026.
- Search/RAG không được chọn đoạn lịch sử chỉ vì khớp từ khóa hơn.
- Agent phải ưu tiên nguồn có hiệu lực đúng thời điểm.

---

## 3.5. Vay dành cho cán bộ, công chức, viên chức và lực lượng vũ trang

**URL:**  
https://www.shb.com.vn/vay-tieu-dung-khong-tai-san-bao-dam-danh-cho-can-bo-cong-chuc-vien-chuc-luc-luong-vu-trang/

### Nội dung công khai

Trang nêu:

- đối tượng khách hàng đặc thù;
- vay tín chấp;
- thời hạn và hạn mức theo sản phẩm;
- nguồn trả nợ từ lương khu vực công;
- phương thức vay theo món hoặc thấu chi.

### Policy concepts

```text
public_sector_employee
civil_servant
public_employee
armed_forces
salary_coefficient
base_salary
position_allowance
employment_status
```

### Rule cần có

- Kiểm tra quyết định tuyển dụng/bổ nhiệm.
- Kiểm tra đơn vị trả lương.
- Kiểm tra hiệu lực quyết định lương.
- Kiểm tra thời gian còn lại của quan hệ công tác.
- Không coi truy lĩnh là thu nhập cố định.
- Không áp dụng policy lương doanh nghiệp tư nhân một cách máy móc.

---

## 3.6. Vay tiêu dùng có tài sản bảo đảm

**URL:**  
https://www.shb.com.vn/vay-tieu-dung/

### Nội dung công khai

Trang sản phẩm mô tả:

- tài trợ nhu cầu tiêu dùng;
- có tài sản bảo đảm;
- thời hạn dài;
- phương thức trả nợ linh hoạt;
- hạn mức phụ thuộc hồ sơ và tài sản.

### Policy concepts

```text
secured_consumer_loan
collateral_type
collateral_value
ltv
loan_tenor
repayment_method
```

### Rule

```text
approved_loan_amount <= accepted_collateral_value × maximum_ltv
```

Đồng thời vẫn phải kiểm tra:

```text
financial_capability
repayment_source
monthly_debt_service
```

Có tài sản bảo đảm không loại bỏ yêu cầu đánh giá khả năng trả nợ.

---

## 3.7. “Tiêu dùng phong cách”

**URL:**  
https://www.shb.com.vn/tieu-dung-phong-cach/

### Nội dung công khai

Trang liệt kê hồ sơ:

- đơn đề nghị vay;
- giấy tờ định danh;
- hồ sơ tình trạng hôn nhân;
- hồ sơ tài sản bảo đảm;
- hồ sơ chứng minh thu nhập;
- hồ sơ chứng minh mục đích vay.

### Ứng dụng

Xây checklist:

```text
IDENTITY_COMPLETE
MARITAL_STATUS_COMPLETE
INCOME_DOCUMENT_COMPLETE
COLLATERAL_DOCUMENT_COMPLETE
LOAN_PURPOSE_DOCUMENT_COMPLETE
```

### Dependency rule

Policy Agent chỉ đánh giá rule thu nhập khi:

```text
income_documents_status != MISSING
```

Nếu thiếu hồ sơ:

```text
decision = REVIEW
action = REQUEST_ADDITIONAL_DOCUMENT
```

---

## 3.8. Gói vay mua nhà cho người trẻ

**URL:**  
https://www.shb.com.vn/tin-vui-cho-gioi-tre-khi-vay-mua-nha-shb-tung-goi-vay-lai-suat-chi-tu-ai-suat-chi-tu-399-nam/

### Nội dung công khai

Trang công bố tại thời điểm chương trình:

- tỷ lệ tài trợ có thể lên tới mức cao trên giá trị tài sản;
- lãi suất ưu đãi ban đầu;
- thời gian ân hạn trả gốc;
- nhiều nguồn thu nhập có thể được xem xét: lương, hộ kinh doanh, doanh nghiệp do khách hàng làm chủ và nguồn khác;
- chương trình có thời hạn áp dụng.

### Policy concepts

```text
mortgage
maximum_ltv
promotional_rate
grace_period
income_source_type
program_end_date
```

### Rule quan trọng

- Không áp dụng lãi suất ưu đãi cho toàn thời hạn.
- Không coi doanh thu hộ kinh doanh là thu nhập ròng.
- Không cộng thu nhập doanh nghiệp vào thu nhập cá nhân nếu chưa xác định quyền hưởng.
- Khi chương trình hết hạn, policy phải chuyển `HISTORICAL`.

---

## 3.9. Chương trình vay mua nhà lãi suất ưu đãi 2024

**URL:**  
https://www.shb.com.vn/mua-nha-de-dang-hon-voi-lai-suat-uu-dai-chi-tu-579-tai-shb/

### Nội dung công khai

Trang công bố:

- thời gian chương trình;
- lãi suất từ mức ưu đãi;
- tỷ lệ tài trợ tối đa;
- phạm vi áp dụng toàn quốc;
- mục đích mua nhà dân cư hoặc dự án.

### Ứng dụng

Kiểm thử:

```text
promotion_period
minimum_advertised_rate
actual_contract_rate
post_promotion_rate
property_type
ltv
```

`minimum_advertised_rate` không phải `actual_contract_rate`.

---

## 3.10. Giải pháp dành cho hộ kinh doanh

**URL:**  
https://www.shb.com.vn/giai-phap-danh-cho-ho-kinh-doanh-de-chuyen-doi-vung-kinh-doanh/

### Nội dung công khai

Trang năm 2026 mô tả:

- mở tài khoản hộ/cá nhân kinh doanh;
- phần mềm quản lý bán hàng;
- kiểm soát doanh thu và hàng hóa;
- kê khai thuế;
- liên kết tài khoản SHB;
- điều kiện và thời gian chương trình.

### Ứng dụng

Policy Agent cần phân biệt:

```text
business_account
business_revenue
business_net_income
tax_declaration
sales_management_data
account_link_status
```

### Rule

```text
business_revenue != personal_eligible_income
```

Chỉ xác định thu nhập sau khi:

1. loại giao dịch vay/chuyển nội bộ;
2. xác định chi phí;
3. đối chiếu thuế;
4. xác định tỷ lệ sở hữu;
5. áp dụng policy income haircut.

---

## 3.11. Các chương trình hộ kinh doanh/tiểu thương

### URLs

- https://www.shb.com.vn/shb-cap-han-muc-thau-chi-len-toi-300-trieu-dong-ho-tro-khach-hang-mo-rong-kinh-doanh/
- https://www.shb.com.vn/goi-giai-phap-tai-chinh-toan-dien-cho-khach-hang-tieu-thuong-kinh-doanh-tuyen-pho/
- https://www.shb.com.vn/goi-giai-phap-tai-chinh-toan-dien-linh-hoat-va-tien-loi-danh-cho-khach-hang-tieu-thuong-kinh-doanh-online/

### Nội dung có thể ứng dụng

- hạn mức theo chương trình;
- mục đích vốn;
- thời gian hoạt động kinh doanh;
- doanh thu qua tài khoản;
- hồ sơ thuế;
- dòng tiền sàn thương mại điện tử;
- thấu chi phục vụ vốn lưu động.

### Policy flags

```text
BUSINESS_HISTORY_INSUFFICIENT
REVENUE_NOT_VERIFIED
TAX_DECLARATION_MISMATCH
BUSINESS_PERSONAL_ACCOUNT_MIX
MARKETPLACE_SETTLEMENT_UNSTABLE
```

---

## 3.12. Vay online cầm cố sổ tiết kiệm

**URL:**  
https://www.shb.com.vn/vay-online-cam-co-so-tiet-kiem/

### Nội dung công khai

Trang nêu:

- vay có bảo đảm bằng sổ tiết kiệm;
- hạn mức tính theo giá trị tiền gửi;
- lãi suất vay liên quan lãi suất tiền gửi;
- quy trình online;
- điều kiện đối với sổ tiết kiệm.

### Policy concepts

```text
deposit_owner
deposit_principal
deposit_currency
deposit_maturity
loan_to_deposit_ratio
blocked_deposit
loan_interest_spread
```

### Rule

- Kiểm tra chủ sở hữu sổ.
- Kiểm tra sổ đang có hiệu lực.
- Kiểm tra tình trạng phong tỏa/cầm cố.
- Không coi tiền giải ngân là thu nhập.
- Không dùng lãi tiền gửi dự kiến như thu nhập đã thực nhận.

---

## 3.13. Công bố lãi suất cho vay bình quân

**URL:**  
https://www.shb.com.vn/cong-bo-lai-suat-binh-quan/

### Nội dung công khai

Trang tập hợp công bố định kỳ về:

- lãi suất cho vay bình quân;
- lãi suất bình quân cho vay ngắn hạn phục vụ đời sống/tiêu dùng;
- chênh lệch giữa lãi suất cho vay và huy động.

### Ứng dụng

- Benchmark lãi suất.
- Kiểm tra mức lãi trên hợp đồng có bất thường.
- Tạo synthetic repayment case.
- Không thay thế lãi suất hợp đồng.

### Output

```text
benchmark_rate
contract_rate
rate_difference
benchmark_period
```

---

## 3.14. Các trang giải pháp cho đối tác/doanh nghiệp ưu tiên

### URLs tiêu biểu

- https://www.shb.com.vn/giai-phap-tai-chinh-toan-dien-danh-cho-can-bo-nhan-vien-doanh-nghiep-uu-tien-cua-shb/
- https://www.shb.com.vn/goi-giai-phap-tai-chinh-toan-dien-danh-cho-can-bo-nhan-vien-dai-hoc-quoc-gia-ha-noi/
- https://www.shb.com.vn/chinh-sach-uu-dai-danh-cho-can-bo-nhan-vien-tong-cong-ty-dau-tu-phat-trien-duong-cao-toc-viet-nam-vec/
- https://www.shb.com.vn/shb-cung-cap-giai-phap-tai-chinh-toan-dien-cho-cac-don-vi-hanh-chinh-su-nghiep/

### Ứng dụng

Mô hình hóa:

```text
partner_program_id
employer_id
employee_group
program_effective_period
maximum_limit
income_multiple
special_rate
```

### Không được suy luận

Employer segment phải được lấy từ hệ thống master data hoặc policy approved list; không suy ra chỉ từ tên đơn vị.

---

## 3.15. S-Living cho cán bộ nhân viên SHB

**URL:**  
https://www.shb.com.vn/s-living-goi-giai-phap-tai-chinh-toan-dien-2/

### Nội dung công khai

Trang mô tả giải pháp vay/hạn mức dựa trên số lần lương cho cán bộ nhân viên và một số người liên quan.

### Ứng dụng

```text
employee_income
co_borrower_income
related_person_income
income_multiple
relationship_type
```

### Rule

Không cộng thu nhập người thân nếu:

- người đó không phải đồng vay;
- không có nghĩa vụ đồng trả nợ;
- hồ sơ không có căn cứ pháp lý cho việc gộp thu nhập.

---

# 4. Nguồn Chính phủ/NHNN về hoạt động cho vay

## 4.1. Luật Các tổ chức tín dụng 2024

### Nội dung liên quan

Khung nền tảng về:

- hoạt động ngân hàng;
- cấp tín dụng;
- quản trị rủi ro;
- bảo mật thông tin khách hàng;
- giới hạn và thẩm quyền;
- trách nhiệm của tổ chức tín dụng.

### Ứng dụng

Policy Agent phải phân biệt các hình thức:

```text
loan
overdraft
credit_card
guarantee
discount
factoring
other_credit
```

### Control requirements

```text
ROLE_AUTHORIZED
CREDIT_PRODUCT_VALID
CUSTOMER_INFORMATION_PROTECTED
AUDIT_LOG_REQUIRED
```

---

## 4.2. Thông tư 39/2016/TT-NHNN

**URL:**  
https://vanban.chinhphu.vn/?docid=188822&pageid=27160

### Nội dung ứng dụng

- điều kiện vay vốn;
- mục đích sử dụng vốn;
- phương án sử dụng vốn;
- khả năng tài chính;
- thỏa thuận cho vay;
- lãi suất;
- phí;
- trả nợ;
- cơ cấu lại thời hạn trả nợ;
- chấm dứt cho vay;
- thu hồi nợ trước hạn;
- kiểm tra sử dụng vốn.

### Rule groups

```text
BORROWER_ELIGIBILITY
LAWFUL_PURPOSE
FINANCIAL_CAPABILITY
REPAYMENT_SOURCE
LOAN_AGREEMENT_COMPLETE
INTEREST_DISCLOSED
FEE_DISCLOSED
EARLY_RECALL_CONDITION
```

---

## 4.3. Thông tư 06/2023/TT-NHNN và Thông tư 10/2023/TT-NHNN

### Ứng dụng

Hai văn bản tạo case điển hình cho:

- sửa đổi;
- ngưng hiệu lực một phần;
- quản lý trạng thái rule;
- không chỉ tìm đoạn phù hợp mà phải xác định đoạn có hiệu lực.

```text
ACTIVE
SUSPENDED
REPEALED
UPCOMING
HISTORICAL
```

---

## 4.4. Thông tư 52/2025/TT-NHNN

**URL:**  
https://vanban.chinhphu.vn/?docid=216369&pageid=27160

### Metadata chính thức

- Ban hành: 25/12/2025.
- Có hiệu lực: 25/12/2025.
- Sửa đổi Thông tư 39/2016/TT-NHNN.

### Ứng dụng

Hồ sơ xử lý sau ngày hiệu lực phải được đánh giá bằng snapshot policy đã cập nhật nội dung sửa đổi.

---

## 4.5. Thông tư 29/2026/TT-NHNN

**URL:**  
https://vanban.chinhphu.vn/?classid=1&docid=218709&orggroupid=4&pageid=27160

### Nội dung liên quan

Văn bản sửa đổi Thông tư 39, ban hành ngày 30/06/2026.

### Yêu cầu

Phải đọc ngày hiệu lực trên bản chính thức và quản lý:

```yaml
status: UPCOMING_OR_ACTIVE_BY_DATE
activation_rule: effective_date <= case_date
```

Không kích hoạt dựa trên ngày ban hành.

---

# 5. Phân loại nợ và risk policy

## 5.1. Thông tư 31/2024/TT-NHNN

**URL:**  
https://vanban.chinhphu.vn/?docid=210625&pageid=27160

### Metadata

- Ban hành 30/06/2024.
- Hiệu lực 01/07/2024.
- Quy định phân loại tài sản có.

### Ứng dụng

```text
debt_group
days_past_due
restructured_debt
credit_quality
classification_date
```

Policy Agent phải:

- kiểm tra nợ quá hạn;
- kiểm tra khoản nợ cơ cấu;
- xác định escalation;
- không chỉ dựa vào DTI nếu lịch sử tín dụng không đáp ứng.

---

## 5.2. Thông tư 37/2025/TT-NHNN

**URL:**  
https://vanban.chinhphu.vn/?docid=215867&pageid=27160

### Metadata

- Ban hành 31/10/2025.
- Hiệu lực 15/12/2025.
- Sửa đổi Thông tư 31/2024.

### Ứng dụng

Policy dataset phải mapping:

```text
amends: 31/2024/TT-NHNN
```

Không sử dụng bản Thông tư 31 nguyên gốc cho hồ sơ sau ngày sửa đổi nếu phần liên quan đã thay đổi.

---

# 6. Tài sản bảo đảm

## 6.1. Bộ luật Dân sự

### Các khái niệm cần đưa vào ontology

- nghĩa vụ;
- cầm cố;
- thế chấp;
- bảo lãnh;
- tài sản của bên thứ ba;
- xử lý tài sản;
- thứ tự ưu tiên;
- hiệu lực đối kháng.

### Entity

```text
borrower
secured_party
security_provider
asset_owner
co_owner
guarantor
secured_obligation
```

---

## 6.2. Nghị định 21/2021/NĐ-CP

### Ứng dụng

Rule groups:

```text
COLLATERAL_OWNER_VALID
SECURED_OBLIGATION_IDENTIFIED
ASSET_DESCRIPTION_SUFFICIENT
THIRD_PARTY_SECURITY_VALID
ENFORCEMENT_TRIGGER
```

### Document Extraction input

- hợp đồng thế chấp/cầm cố;
- giấy tờ sở hữu;
- giấy ủy quyền;
- chữ ký đồng sở hữu;
- số đăng ký biện pháp bảo đảm;
- tài sản và nghĩa vụ được bảo đảm.

---

# 7. Tài khoản thanh toán và thẻ

## 7.1. Thông tư 17/2024/TT-NHNN

### Nội dung ứng dụng

- mở và sử dụng tài khoản;
- nhận biết khách hàng;
- tài khoản chung;
- ủy quyền;
- phong tỏa;
- đóng tài khoản;
- giao dịch thanh toán.

### Policy rule

```text
ACCOUNT_OWNER_MATCH
ACCOUNT_STATUS_ACTIVE
ACCOUNT_NOT_BLOCKED
AUTHORIZED_USER_VALID
```

Sao kê chỉ có giá trị phù hợp khi xác định đúng chủ tài khoản và kỳ.

---

## 7.2. Quy định về thẻ ngân hàng

### Nội dung cần đưa vào policy corpus

- phát hành thẻ tín dụng;
- hạn mức;
- sao kê;
- thanh toán tối thiểu;
- lãi;
- phí;
- giao dịch trả góp;
- trách nhiệm chủ thẻ;
- giao dịch tranh chấp.

### DTI mapping

```text
credit_card_minimum_payment
installment_payment
cash_advance_balance
overlimit_amount
past_due_card_amount
```

---

# 8. Bảo vệ người tiêu dùng

## 8.1. Luật Bảo vệ quyền lợi người tiêu dùng 2023

### Rule groups

```text
PRODUCT_INFORMATION_DISCLOSED
INTEREST_RATE_DISCLOSED
FEE_DISCLOSED
STANDARD_TERMS_AVAILABLE
COMPLAINT_PROCESS_AVAILABLE
VULNERABLE_CUSTOMER_PROTECTION
```

Policy Agent không chỉ kiểm tra khách hàng; còn kiểm tra action đề xuất có bảo đảm quyền thông tin và quyền khiếu nại.

---

## 8.2. Nghị định 55/2024/NĐ-CP

**URL:**  
https://vanban.chinhphu.vn/?docid=210254&pageid=27160

### Metadata

- Ban hành 16/05/2024.
- Hiệu lực 01/07/2024.
- Hướng dẫn Luật Bảo vệ quyền lợi người tiêu dùng.

### Ứng dụng

- hợp đồng theo mẫu;
- điều kiện giao dịch chung;
- công khai thông tin;
- trách nhiệm của tổ chức kinh doanh;
- bảo vệ nhóm dễ bị tổn thương.

---

# 9. Dữ liệu cá nhân và bảo mật

## 9.1. Nghị định 13/2023/NĐ-CP

### Rule trước khi agent xử lý

```text
PURPOSE_VALID
ACCESS_ROLE_VALID
DATA_SCOPE_MINIMIZED
MASKING_REQUIRED
RETENTION_NOT_EXPIRED
EXTERNAL_TRANSFER_ALLOWED
TRAINING_USE_ALLOWED
```

### Không được mặc định

- Dữ liệu hồ sơ tín dụng được phép dùng để train.
- Dữ liệu có thể gửi tới endpoint ngoài ngân hàng.
- Log có thể ghi đầy đủ CCCD/số tài khoản.

---

# 10. Giao dịch điện tử và chữ ký

## 10.1. Luật Giao dịch điện tử 2023

### Ứng dụng

Policy Agent phải chấp nhận tài liệu điện tử khi đáp ứng điều kiện pháp lý, đồng thời kiểm tra:

```text
document_integrity
source_system
timestamp
electronic_signature
digital_signature
conversion_history
```

## 10.2. Chữ ký số

Phân biệt:

```text
signature_image
electronic_signature
digital_signature
trusted_timestamp
```

Ảnh chữ ký không tự động tương đương chữ ký số hợp lệ.

---

# 11. AML/KYC

## 11.1. Luật Phòng, chống rửa tiền 2022

### Policy output phù hợp

```text
AML_ESCALATION_REQUIRED
SOURCE_OF_FUNDS_UNCLEAR
BENEFICIAL_OWNER_UNRESOLVED
CUSTOMER_INFORMATION_INCOMPLETE
```

Không trả kết luận “rửa tiền”.

## 11.2. Nghị định 19/2023/NĐ-CP và hướng dẫn NHNN

### Entity

```text
occupation
employer
source_of_income
source_of_funds
beneficial_owner
counterparty
transaction_purpose
```

---

# 12. Thu nhập, lao động, thuế và bảo hiểm

Các nguồn này hỗ trợ Policy Agent xác định loại thu nhập có thể được xem xét:

- Bộ luật Lao động 2019.
- Nghị định 145/2020/NĐ-CP.
- Quy định lương tối thiểu.
- Nghị định 73/2024/NĐ-CP.
- Luật Thuế thu nhập cá nhân và văn bản hợp nhất.
- Thông tư 111/2013/TT-BTC.
- Luật Bảo hiểm xã hội 2024.

### Ontology

```text
fixed_salary
variable_salary
allowance
bonus
overtime
pension
social_insurance_benefit
business_revenue
business_net_income
investment_income
one_off_income
```

### Policy principle

```text
declared_income != verified_income != eligible_income
```

---

# 13. Phân cấp độ tin cậy của nguồn

1. Luật, nghị định, thông tư có hiệu lực.
2. Văn bản hợp nhất chính thức.
3. Quy định/quyết định nội bộ SHB được phê duyệt.
4. Điều khoản và hợp đồng SHB.
5. Biểu phí chính thức SHB.
6. Trang sản phẩm SHB.
7. Chương trình marketing.
8. Tin bài lịch sử.

Khi có xung đột:

```text
mandatory_law
    > approved_internal_policy
    > applicable_contract_terms
    > official_fee_schedule
    > product_page
    > campaign_article
```

Thứ tự chính thức phải được pháp chế SHB phê duyệt.

---

# 14. Các rule family cần xây

```text
CUSTOMER_ELIGIBILITY
PRODUCT_ELIGIBILITY
DOCUMENT_COMPLETENESS
LOAN_PURPOSE
INCOME_ELIGIBILITY
DTI
LTV
CREDIT_HISTORY
COLLATERAL
INTEREST_RATE
FEES
REPAYMENT
EARLY_REPAYMENT
DEBT_RESTRUCTURING
ACCOUNT_STATUS
CARD_OBLIGATION
AML_KYC
DATA_PRIVACY
CONSUMER_PROTECTION
DIGITAL_SIGNATURE
EXCEPTION_AUTHORITY
```

---

# 15. Bộ test bắt buộc

1. Văn bản mới ban hành nhưng chưa hiệu lực.
2. Văn bản bị ngưng hiệu lực một phần.
3. Trang sản phẩm mâu thuẫn điều khoản.
4. Chương trình đã hết hạn.
5. Hồ sơ ký trước ngày đổi biểu phí.
6. Hồ sơ đủ DTI nhưng có nợ quá hạn.
7. Tài sản thuộc bên thứ ba.
8. Tài sản đồng sở hữu thiếu chữ ký.
9. Chữ ký chỉ là ảnh.
10. Policy không xác định được phiên bản.
11. Employer nằm trong chương trình đối tác nhưng chương trình hết hiệu lực.
12. Thu nhập người thân không có nghĩa vụ đồng trả nợ.
13. Doanh thu hộ kinh doanh bị nhầm thành thu nhập ròng.
14. Lãi suất ưu đãi bị áp cho toàn thời hạn.
15. Hạn mức quảng cáo bị hiểu thành hạn mức được duyệt.
16. Rule pháp luật và policy nội bộ mâu thuẫn.
17. Hồ sơ thiếu bằng chứng nhưng agent vẫn PASS.
18. Dữ liệu đã hết thời hạn retention.
19. Customer data bị gửi ra endpoint chưa được phép.
20. Exception vượt cấp thẩm quyền.

---

# 16. Danh mục nguồn web SHB đã rà soát

1. https://www.shb.com.vn/vay-thau-chi-online-tin-chap/
2. https://www.shb.com.vn/can-tien-co-lien-thau-chi/
3. https://www.shb.com.vn/tin-chap-tieu-dung/
4. https://www.shb.com.vn/shb-trien-khai-cho-vay-tin-chap-tieu-dung-va-thau-chi-khong-co-tai-san-dam-bao/
5. https://www.shb.com.vn/vay-tieu-dung-khong-tai-san-bao-dam-danh-cho-can-bo-cong-chuc-vien-chuc-luc-luong-vu-trang/
6. https://www.shb.com.vn/vay-tieu-dung/
7. https://www.shb.com.vn/tieu-dung-phong-cach/
8. https://www.shb.com.vn/tin-vui-cho-gioi-tre-khi-vay-mua-nha-shb-tung-goi-vay-lai-suat-chi-tu-ai-suat-chi-tu-399-nam/
9. https://www.shb.com.vn/mua-nha-de-dang-hon-voi-lai-suat-uu-dai-chi-tu-579-tai-shb/
10. https://www.shb.com.vn/giai-phap-danh-cho-ho-kinh-doanh-de-chuyen-doi-vung-kinh-doanh/
11. https://www.shb.com.vn/shb-cap-han-muc-thau-chi-len-toi-300-trieu-dong-ho-tro-khach-hang-mo-rong-kinh-doanh/
12. https://www.shb.com.vn/goi-giai-phap-tai-chinh-toan-dien-cho-khach-hang-tieu-thuong-kinh-doanh-tuyen-pho/
13. https://www.shb.com.vn/goi-giai-phap-tai-chinh-toan-dien-linh-hoat-va-tien-loi-danh-cho-khach-hang-tieu-thuong-kinh-doanh-online/
14. https://www.shb.com.vn/vay-online-cam-co-so-tiet-kiem/
15. https://www.shb.com.vn/cong-bo-lai-suat-binh-quan/
16. https://www.shb.com.vn/giai-phap-tai-chinh-toan-dien-danh-cho-can-bo-nhan-vien-doanh-nghiep-uu-tien-cua-shb/
17. https://www.shb.com.vn/goi-giai-phap-tai-chinh-toan-dien-danh-cho-can-bo-nhan-vien-dai-hoc-quoc-gia-ha-noi/
18. https://www.shb.com.vn/chinh-sach-uu-dai-danh-cho-can-bo-nhan-vien-tong-cong-ty-dau-tu-phat-trien-duong-cao-toc-viet-nam-vec/
19. https://www.shb.com.vn/shb-cung-cap-giai-phap-tai-chinh-toan-dien-cho-cac-don-vi-hanh-chinh-su-nghiep/
20. https://www.shb.com.vn/s-living-goi-giai-phap-tai-chinh-toan-dien-2/

---

# 17. Danh mục nguồn Chính phủ/NHNN trọng yếu

1. Thông tư 39/2016/TT-NHNN  
   https://vanban.chinhphu.vn/?docid=188822&pageid=27160

2. Thông tư 52/2025/TT-NHNN  
   https://vanban.chinhphu.vn/?docid=216369&pageid=27160

3. Thông tư 29/2026/TT-NHNN  
   https://vanban.chinhphu.vn/?classid=1&docid=218709&orggroupid=4&pageid=27160

4. Thông tư 31/2024/TT-NHNN  
   https://vanban.chinhphu.vn/?docid=210625&pageid=27160

5. Thông tư 37/2025/TT-NHNN  
   https://vanban.chinhphu.vn/?docid=215867&pageid=27160

6. Nghị định 55/2024/NĐ-CP  
   https://vanban.chinhphu.vn/?docid=210254&pageid=27160

7. Nghị định 21/2021/NĐ-CP  
   Tra cứu theo số văn bản tại Cổng văn bản Chính phủ.

8. Thông tư 17/2024/TT-NHNN  
   Tra cứu theo số văn bản tại Cổng văn bản Chính phủ.

9. Luật Các tổ chức tín dụng 2024  
   Tra cứu bản luật và văn bản hợp nhất hiện hành tại Cổng văn bản Chính phủ.

10. Luật Bảo vệ quyền lợi người tiêu dùng 2023  
    Tra cứu tại Cổng văn bản Chính phủ.

11. Nghị định 13/2023/NĐ-CP  
    Tra cứu tại Cổng văn bản Chính phủ.

12. Luật Giao dịch điện tử 2023  
    Tra cứu tại Cổng văn bản Chính phủ.

13. Luật Phòng, chống rửa tiền 2022  
    Tra cứu tại Cổng văn bản Chính phủ.

14. Nghị định 19/2023/NĐ-CP  
    Tra cứu tại Cổng văn bản Chính phủ.

---

# 18. Kết luận triển khai

Nguồn công khai đủ để xây:

- ontology;
- RAG prototype;
- policy versioning;
- source hierarchy;
- rule candidate;
- benchmark;
- regression test.

Nguồn công khai **chưa đủ để production**, vì thiếu:

- khẩu vị rủi ro nội bộ;
- cách tính thu nhập đủ điều kiện;
- DTI theo phân khúc;
- income haircut;
- ma trận hạn mức;
- danh sách employer/partner;
- exception matrix;
- cấp thẩm quyền;
- SLA và quy trình phê duyệt;
- danh mục hồ sơ nội bộ;
- các điều kiện chống gian lận nội bộ.

MVP Policy Agent nên bắt đầu với các rule có tính xác định cao:

```text
policy_version
document_completeness
product_eligibility
program_effective_period
loan_purpose
maximum_limit
loan_tenor
ltv
dti
credit_history
interest_and_fee_disclosure
data_access
```

Mỗi kết quả phải có:

```text
rule_id
condition
input_value
result
source
effective_date
evidence
confidence
exception
review_required
```
