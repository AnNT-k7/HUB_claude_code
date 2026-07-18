# Ghi chú pháp lý ứng dụng cho Document Extraction Agent trong quy trình xác minh thu nhập

> **Mục đích tài liệu:** Tóm tắt các nội dung pháp lý có tính ứng dụng trực tiếp hoặc gián tiếp đối với **Document Extraction Agent** trong hệ thống đa tác tử hỗ trợ xác minh thu nhập và thẩm định hồ sơ vay.
>
> **Phạm vi:** Các văn bản công khai của Quốc hội, Chính phủ và Ngân hàng Nhà nước đã được rà soát; tập trung vào hồ sơ vay, hợp đồng lao động, bảng lương, sao kê, tài liệu điện tử, chữ ký số, dữ liệu cá nhân và phòng, chống rửa tiền.
>
> **Lưu ý:** Đây là tài liệu phân tích phục vụ thiết kế hệ thống và dataset, không thay thế ý kiến chính thức của pháp chế SHB. Khi triển khai production cần kiểm tra lại hiệu lực, văn bản sửa đổi, văn bản hợp nhất và quy định nội bộ tại thời điểm áp dụng.

---

## 1. Vai trò pháp lý của Document Extraction Agent

Document Extraction Agent không ra quyết định tín dụng. Agent có nhiệm vụ:

1. Nhận diện loại tài liệu.
2. Trích xuất trường dữ liệu, bảng, chữ ký, dấu, checkbox và quan hệ giữa các trường.
3. Chuẩn hóa dữ liệu về định dạng dùng chung.
4. Gắn bằng chứng về trang, vùng tọa độ và đoạn văn bản nguồn.
5. Phát hiện tài liệu thiếu trang, mâu thuẫn hình thức hoặc có dấu hiệu bất thường.
6. Chuyển dữ liệu có cấu trúc cho Income Analysis Agent, Policy Agent và Consistency Agent.
7. Không tự kết luận hồ sơ hợp lệ, thu nhập được chấp nhận hay khoản vay được phê duyệt.

### Nguyên tắc thiết kế cốt lõi

- **Tách extraction khỏi decision:** agent chỉ đọc và chuẩn hóa; rule nghiệp vụ nằm ở Policy/Consistency Agent.
- **Có provenance:** mọi giá trị phải truy ngược được tới tài liệu, trang và vị trí.
- **Không ghi đè dữ liệu nguồn:** bản gốc được bảo toàn; kết quả extraction là lớp dữ liệu dẫn xuất.
- **Không suy diễn khi thiếu bằng chứng:** trường không thấy phải để `null`, không tự điền từ ngữ cảnh.
- **Version-aware:** chính sách và biểu mẫu phải gắn ngày hiệu lực, ngày ban hành và phiên bản.
- **Human-in-the-loop:** trường nhạy cảm hoặc confidence thấp phải đưa sang kiểm tra thủ công.

---

# 2. Nhóm văn bản về hoạt động cho vay

## 2.1. Luật Các tổ chức tín dụng 2024 và văn bản hợp nhất

### Văn bản

- Luật số **32/2024/QH15** về Các tổ chức tín dụng.
- Luật số **43/2024/QH15** sửa đổi một số nội dung liên quan.
- Văn bản hợp nhất số **158/VBHN-VPQH** ngày 09/09/2025.

### Nội dung có tính ứng dụng

Luật xác lập khung pháp lý cho hoạt động ngân hàng, cấp tín dụng, bảo mật thông tin khách hàng, quản trị rủi ro và trách nhiệm của tổ chức tín dụng. Với Document Extraction Agent, các điểm ứng dụng gồm:

1. **Tài liệu tín dụng là dữ liệu nghiệp vụ có kiểm soát.**  
   Không được coi hồ sơ vay, sao kê, chứng từ lương như dữ liệu văn bản thông thường. Việc truy cập, xử lý, lưu trữ và chia sẻ phải tuân theo phân quyền.

2. **Thông tin khách hàng thuộc phạm vi bảo mật cao.**  
   Agent phải hạn chế xuất dữ liệu thô ra ngoài vùng xử lý, đặc biệt là:
   - họ tên;
   - số định danh cá nhân;
   - số tài khoản;
   - số dư;
   - lịch sử giao dịch;
   - thông tin khoản vay;
   - thông tin tài sản bảo đảm.

3. **Kết quả extraction không phải quyết định cấp tín dụng.**  
   Thiết kế giao diện và log cần thể hiện rõ:
   - dữ liệu do AI trích xuất;
   - dữ liệu do chuyên viên xác nhận;
   - quyết định do người/hệ thống có thẩm quyền đưa ra.

4. **Phải duy trì dấu vết kiểm toán.**  
   Mỗi lần agent đọc hoặc sửa kết quả phải có log:
   - ai/agent nào truy cập;
   - thời điểm;
   - tài liệu nào;
   - trường nào được thay đổi;
   - giá trị cũ/mới;
   - lý do thay đổi.

### Yêu cầu kỹ thuật đề xuất

```yaml
document_access:
  classification: confidential_customer_data
  role_based_access: true
  external_export: prohibited_by_default
  full_audit_log: true
  retention_policy_id: required
```

### Trường dữ liệu nên hỗ trợ

```text
customer_id
loan_application_id
contract_number
credit_product
loan_amount
loan_currency
loan_term
interest_rate
collateral_reference
disbursement_account
repayment_account
signing_date
effective_date
```

### Nguồn chính thức

- https://vanban.chinhphu.vn/?docid=211190&pageid=27160
- https://vanban.chinhphu.vn/?classid=1&docid=211201&orggroupid=1&pageid=27160
- https://vanban.chinhphu.vn/?docid=215312&pageid=27160

---

## 2.2. Thông tư 39/2016/TT-NHNN và các văn bản sửa đổi

### Văn bản

- Thông tư **39/2016/TT-NHNN** về hoạt động cho vay.
- Thông tư **06/2023/TT-NHNN** sửa đổi, bổ sung.
- Thông tư **10/2023/TT-NHNN** ngưng hiệu lực một số nội dung được bổ sung.
- Thông tư **52/2025/TT-NHNN** tiếp tục sửa đổi Thông tư 39.
- Các văn bản sửa đổi hoặc hợp nhất mới hơn phải được kiểm tra trước khi production.

### Nội dung có tính ứng dụng

#### A. Hồ sơ và thông tin khách hàng

Agent phải có khả năng trích xuất dữ liệu phục vụ đánh giá:

- tư cách khách hàng;
- mục đích vay;
- nhu cầu vốn;
- số tiền đề nghị vay;
- thời hạn;
- nguồn trả nợ;
- khả năng tài chính;
- thông tin thu nhập;
- tài liệu chứng minh mục đích sử dụng vốn.

Agent không nên gộp “thu nhập khai báo” và “thu nhập xác minh” thành một trường. Hai khái niệm phải tách riêng:

```json
{
  "declared_income": null,
  "verified_income": null,
  "eligible_income": null
}
```

#### B. Thỏa thuận cho vay

Các trường thường xuất hiện trong hợp đồng/thỏa thuận cho vay:

- thông tin các bên;
- số tiền cho vay;
- mục đích sử dụng vốn;
- đồng tiền cho vay;
- phương thức cho vay;
- thời hạn;
- lãi suất;
- nguyên tắc điều chỉnh lãi suất;
- giải ngân;
- trả nợ gốc;
- trả lãi;
- phí;
- quyền và nghĩa vụ;
- xử lý nợ;
- hiệu lực hợp đồng.

Document Extraction Agent cần phân biệt:

```text
requested_loan_amount
approved_loan_amount
disbursed_amount
outstanding_principal
overdue_principal
```

#### C. Khả năng trả nợ

Agent có thể trích xuất bằng chứng, nhưng không tự kết luận khả năng trả nợ. Các dữ liệu cần cung cấp cho agent phân tích sau:

- thu nhập định kỳ;
- thu nhập bất thường;
- nghĩa vụ nợ hiện hữu;
- dòng tiền vào;
- dòng tiền ra;
- số dư bình quân;
- các khoản khấu trừ;
- kỳ trả lương;
- biến động theo tháng.

#### D. Kiểm soát phiên bản pháp lý

Thông tư 39 đã được sửa đổi nhiều lần. Dataset và rule engine phải lưu:

```yaml
legal_document_number: "39/2016/TT-NHNN"
effective_from: "..."
effective_to: "..."
amended_by:
  - "06/2023/TT-NHNN"
  - "52/2025/TT-NHNN"
suspended_content:
  - reference: "10/2023/TT-NHNN"
```

### Các lỗi extraction cần đặc biệt kiểm soát

- nhầm số tiền đề nghị với số tiền được duyệt;
- nhầm lãi suất ban đầu với lãi suất sau điều chỉnh;
- nhầm ngày ký với ngày giải ngân;
- nhầm thời hạn vay với kỳ trả nợ;
- nhầm mục đích vay với nội dung diễn giải giao dịch;
- bỏ sót phụ lục sửa đổi hợp đồng.

### Nguồn chính thức

- https://vanban.chinhphu.vn/?docid=188822&pageid=27160
- https://vanban.chinhphu.vn/?docid=208185&pageid=27160
- https://vanban.chinhphu.vn/?classid=1&docid=208559&pageid=27160&typegroupid=6
- https://vanban.chinhphu.vn/?docid=216369&pageid=27160

---

# 3. Nhóm văn bản về hợp đồng lao động và tiền lương

## 3.1. Bộ luật Lao động 2019

### Văn bản

- Luật số **45/2019/QH14**, có hiệu lực từ 01/01/2021.

### Nội dung có tính ứng dụng

#### A. Nhận diện hợp đồng lao động

Agent phải nhận diện được một tài liệu là hợp đồng lao động dựa trên bản chất nội dung, không chỉ dựa vào tiêu đề. Một tài liệu có thể mang tên khác nhưng vẫn thể hiện:

- công việc có trả công;
- tiền lương;
- sự quản lý, điều hành, giám sát;
- quyền và nghĩa vụ của người lao động và người sử dụng lao động.

#### B. Loại hợp đồng

Các trường quan trọng:

```text
employment_contract_type
contract_start_date
contract_end_date
probation_start_date
probation_end_date
```

Cần phân biệt:

- hợp đồng không xác định thời hạn;
- hợp đồng xác định thời hạn;
- thỏa thuận thử việc;
- phụ lục hợp đồng;
- quyết định điều chuyển;
- quyết định tăng lương.

#### C. Nội dung chủ yếu cần trích xuất

```text
employee_name
employee_date_of_birth
employee_id_number
employee_address
employer_name
employer_address
legal_representative
job_title
job_description
work_location
contract_type
contract_start_date
contract_end_date
base_salary
salary_payment_method
salary_payment_frequency
allowances
additional_payments
salary_review_terms
working_time
signing_date
employee_signature
employer_signature
```

#### D. Tiền lương

Agent cần tách tối thiểu:

```json
{
  "base_salary": null,
  "position_allowance": null,
  "responsibility_allowance": null,
  "meal_allowance": null,
  "transport_allowance": null,
  "phone_allowance": null,
  "performance_bonus": null,
  "other_fixed_additions": null,
  "other_variable_additions": null,
  "gross_salary": null,
  "net_salary": null
}
```

Không được mặc định mọi khoản xuất hiện trên bảng lương đều là thu nhập đủ điều kiện tín dụng.

#### E. Kỳ hạn và phương thức trả lương

Agent phải trích xuất:

- trả theo giờ/ngày/tuần/tháng/sản phẩm;
- trả bằng tiền mặt/chuyển khoản;
- ngày trả lương;
- kỳ lương;
- số tài khoản nhận lương nếu có;
- khoản trả chậm hoặc truy lĩnh.

### Rule hỗ trợ consistency

```text
Nếu contract_end_date < statement_period_end:
    đánh dấu "hợp đồng có thể đã hết hạn trong kỳ sao kê"

Nếu salary_payment_method = bank_transfer:
    yêu cầu đối chiếu employer_name / payroll_narrative / account_credit

Nếu phụ lục có signing_date mới hơn hợp đồng:
    ưu tiên giá trị lương mới từ ngày hiệu lực của phụ lục
```

### Nguồn chính thức

- https://vanban.chinhphu.vn/?docid=198540&pageid=27160

---

## 3.2. Nghị định 145/2020/NĐ-CP

### Nội dung có tính ứng dụng

Nghị định hướng dẫn Bộ luật Lao động về điều kiện lao động và quan hệ lao động. Đối với Document Extraction Agent, giá trị lớn nhất là làm rõ bối cảnh của:

- nội dung hợp đồng lao động;
- thông báo, thỏa thuận và hồ sơ lao động;
- tiền lương;
- kỳ hạn trả lương;
- làm thêm giờ;
- thời giờ làm việc;
- các khoản liên quan đến quan hệ lao động.

### Ứng dụng vào dataset

Nên tạo các mẫu/nhãn cho:

```text
employment_contract
employment_contract_appendix
salary_adjustment_decision
job_transfer_decision
probation_agreement
payroll
overtime_statement
bonus_decision
employment_confirmation
income_confirmation
termination_decision
```

### Các tình huống dễ nhầm

- thưởng hiệu suất được ghi trong quyết định riêng;
- phụ cấp được quy định trong phụ lục;
- thay đổi mức lương nhưng hợp đồng gốc chưa sửa;
- truy lĩnh lương nhiều tháng trong một giao dịch;
- khoản làm thêm giờ làm tăng đột biến thu nhập tháng.

### Nguồn chính thức

- https://vanban.chinhphu.vn/?docid=201967&pageid=27160

---

## 3.3. Nghị định 73/2024/NĐ-CP về mức lương cơ sở và chế độ tiền thưởng

### Nội dung có tính ứng dụng

Văn bản hữu ích khi xử lý hồ sơ của người hưởng lương từ khu vực công. Thu nhập có thể không được ghi trực tiếp bằng một số tiền cố định trong hợp đồng mà được xác định từ:

- hệ số lương;
- mức lương cơ sở;
- phụ cấp chức vụ;
- phụ cấp thâm niên;
- phụ cấp trách nhiệm;
- khoản thưởng theo chế độ.

### Yêu cầu extraction

```text
salary_coefficient
base_salary_reference
position_allowance_coefficient
seniority_allowance_rate
other_allowance_rate
effective_date
issuing_authority
decision_number
```

### Lưu ý triển khai

Document Extraction Agent chỉ trích xuất hệ số và căn cứ. Việc tính thành số tiền phải thực hiện tại Income Analysis/Policy Agent theo mức lương cơ sở có hiệu lực tại từng thời kỳ.

### Nguồn chính thức

- https://vanban.chinhphu.vn/?docid=210537&pageid=27160

---

## 3.4. Nghị định về xử phạt trong lĩnh vực lao động

### Văn bản đã rà soát

- Nghị định **12/2022/NĐ-CP** và văn bản thay thế/sửa đổi nếu có tại thời điểm triển khai.

### Ứng dụng

Không dùng để tính thu nhập trực tiếp. Giá trị đối với agent là giúp xây các cờ chất lượng dữ liệu:

- hợp đồng thiếu nội dung chủ yếu;
- trả lương không đúng kỳ;
- tài liệu lao động không nhất quán;
- tài liệu không có chữ ký/xác nhận cần thiết;
- thông tin người sử dụng lao động không đầy đủ.

### Nguồn chính thức

- https://vanban.chinhphu.vn/?docid=205182&pageid=27160

---

# 4. Nhóm văn bản về dữ liệu cá nhân và bảo mật

## 4.1. Nghị định 13/2023/NĐ-CP về bảo vệ dữ liệu cá nhân

### Nội dung có tính ứng dụng trực tiếp

Document Extraction Agent xử lý tập hợp dữ liệu có mức độ nhạy cảm cao:

- thông tin định danh;
- thông tin liên hệ;
- tài khoản ngân hàng;
- lịch sử giao dịch;
- thu nhập;
- nghĩa vụ nợ;
- dữ liệu việc làm;
- chữ ký;
- hình ảnh giấy tờ;
- thông tin gia đình/người phụ thuộc.

### Yêu cầu hệ thống

#### A. Giới hạn mục đích

Dữ liệu chỉ được dùng cho mục đích đã được xác định, ví dụ:

```text
income_verification
credit_underwriting_support
fraud_check
regulatory_audit
```

Không được tự động tái sử dụng dataset production cho huấn luyện nếu chưa có cơ sở pháp lý và phê duyệt phù hợp.

#### B. Tối thiểu hóa dữ liệu

Agent chỉ trích xuất trường cần thiết. Ví dụ, nếu mục tiêu là xác minh thu nhập thì không cần trích xuất toàn bộ nội dung tin nhắn cá nhân xuất hiện trong ảnh chụp màn hình.

#### C. Phân quyền

Tối thiểu phải có:

```text
document_reader
extraction_reviewer
underwriter
policy_admin
model_operator
auditor
data_protection_officer
```

#### D. Ẩn/mặt nạ dữ liệu

Trong giao diện và log:

```text
CCCD: ******1234
account_number: ******5678
phone: ******789
```

#### E. Quản lý vòng đời dữ liệu

Cần định nghĩa:

- thời gian giữ bản gốc;
- thời gian giữ bản OCR;
- thời gian giữ embedding;
- thời gian giữ log;
- quy trình xóa;
- quy trình đáp ứng yêu cầu của chủ thể dữ liệu.

#### F. Dataset huấn luyện

Dữ liệu nội bộ dùng huấn luyện phải:

1. được phê duyệt mục đích;
2. ẩn danh hoặc giả danh hóa;
3. loại bỏ khóa tái nhận diện;
4. hạn chế quyền tải xuống;
5. có watermark và truy vết;
6. tách khỏi dữ liệu production;
7. có quy trình xóa khỏi dataset và model pipeline khi cần.

### Trường metadata cần bổ sung

```yaml
personal_data_classification: sensitive
processing_purpose: income_verification
consent_or_legal_basis_ref: required
retention_expiry: required
masking_policy: required
training_use_allowed: false
cross_border_transfer_allowed: false
```

### Nguồn chính thức

- Tra cứu tại Cổng văn bản Chính phủ theo số **13/2023/NĐ-CP**.

---

# 5. Nhóm văn bản về tài liệu điện tử và chữ ký số

## 5.1. Luật Giao dịch điện tử 2023

### Nội dung có tính ứng dụng

Agent phải hỗ trợ cả:

- PDF scan;
- PDF có text layer;
- tài liệu ký số;
- hợp đồng điện tử;
- dữ liệu sinh từ LOS/DMS;
- bản chụp màn hình;
- thông điệp dữ liệu có metadata.

### Nguyên tắc áp dụng

1. Không hạ thấp giá trị tài liệu chỉ vì tài liệu ở dạng điện tử.
2. Phải bảo toàn tính toàn vẹn và khả năng truy cập.
3. Không tách nội dung khỏi metadata cần thiết để xác minh nguồn gốc.
4. Khi chuyển đổi định dạng phải lưu checksum và lịch sử chuyển đổi.
5. Bản render dùng OCR không được thay thế bản gốc.

### Metadata bắt buộc

```text
source_system
original_filename
mime_type
file_size
sha256
created_at
received_at
converted_at
conversion_tool
page_count
digital_signature_present
timestamp_present
```

### Nguồn chính thức

- https://vanban.chinhphu.vn/?docid=208421&pageid=27160

---

## 5.2. Nghị định 130/2018/NĐ-CP và Nghị định 48/2024/NĐ-CP về chữ ký số

### Nội dung có tính ứng dụng

Agent không nên chỉ nhận diện hình ảnh chữ ký. Với tài liệu ký số phải trích xuất và/hoặc kiểm tra:

- tên chủ thể ký;
- tổ chức cấp chứng thư;
- số sê-ri chứng thư;
- thời gian ký;
- thuật toán;
- trạng thái chữ ký;
- trạng thái chứng thư tại thời điểm kiểm tra;
- chuỗi chứng thư;
- timestamp;
- phần nội dung được ký.

### Schema đề xuất

```json
{
  "digital_signatures": [
    {
      "signer_name": "",
      "signer_organization": "",
      "certificate_serial": "",
      "issuer": "",
      "signing_time": "",
      "timestamp_time": "",
      "validation_status": "",
      "covers_entire_document": null
    }
  ]
}
```

### Human review trigger

- chữ ký không hợp lệ;
- chứng thư hết hạn;
- nội dung bị thay đổi sau khi ký;
- chữ ký chỉ bao phủ một phần tài liệu;
- thời gian ký bất thường;
- tên người ký không khớp người có thẩm quyền;
- tài liệu chỉ chứa ảnh chữ ký nhưng không có chữ ký số.

### Nguồn chính thức

- Tra cứu Nghị định **130/2018/NĐ-CP** tại Cổng văn bản Chính phủ.
- https://vanban.chinhphu.vn/?docid=210212&pageid=27160

---

# 6. Nhóm văn bản về phòng, chống rửa tiền

## 6.1. Luật Phòng, chống rửa tiền 2022

### Nội dung có tính ứng dụng

Document Extraction Agent không thực hiện kết luận AML, nhưng cần trích xuất dữ liệu làm đầu vào cho KYC/AML:

- thông tin khách hàng;
- thông tin người đại diện;
- chủ sở hữu hưởng lợi;
- nghề nghiệp;
- chức vụ;
- nơi làm việc;
- nguồn thu nhập;
- nguồn tiền;
- mục đích giao dịch;
- bên chuyển tiền;
- bên nhận tiền;
- nội dung giao dịch;
- quốc gia/vùng lãnh thổ liên quan.

### Schema liên quan

```text
customer_name
customer_id_number
nationality
occupation
employer
job_title
beneficial_owner
source_of_income
source_of_funds
counterparty_name
counterparty_account
transaction_description
transaction_country
```

### Cờ chuyển Consistency/AML Agent

- nhiều khoản tiền vào từ bên không liên quan tới đơn vị sử dụng lao động;
- nội dung giao dịch không phù hợp với mô tả “lương”;
- dòng tiền vào được chuyển ra ngay;
- giao dịch vòng tròn;
- tiền vào từ nhiều tài khoản cá nhân;
- tên người trả lương không khớp employer;
- khoản tiền lớn bất thường so với hồ sơ nghề nghiệp.

Agent chỉ nên gắn cờ bằng chứng, không gắn nhãn “rửa tiền”.

### Nguồn chính thức

- https://vanban.chinhphu.vn/?classid=1&docid=207710&pageid=27160&typegroupid=3

---

## 6.2. Nghị định 19/2023/NĐ-CP

### Ứng dụng

Nghị định chi tiết một số nội dung của Luật Phòng, chống rửa tiền. Đối với Document Extraction Agent:

- chuẩn hóa thông tin nhận biết khách hàng;
- hỗ trợ xác định chủ sở hữu hưởng lợi;
- trích xuất thông tin nghề nghiệp, chức vụ và nguồn thu nhập;
- giữ bằng chứng phục vụ báo cáo/kiểm tra;
- đảm bảo dữ liệu có thể truy xuất lại.

### Nguồn chính thức

- https://vanban.chinhphu.vn/?classid=1&docid=207830&pageid=27160&typegroupid=4

---

## 6.3. Thông tư 09/2023/TT-NHNN

### Ứng dụng

Thông tư hướng dẫn thực hiện một số điều của pháp luật AML. Agent cần:

- chuẩn hóa trường định danh;
- phát hiện trường thiếu;
- phân biệt cá nhân với tổ chức;
- trích xuất thông tin người đại diện;
- trích xuất thông tin chủ sở hữu hưởng lợi nếu tài liệu có;
- tạo output có thể dùng trong hệ thống cảnh báo nhưng không tự báo cáo giao dịch đáng ngờ.

### Nguồn chính thức

- https://vanban.chinhphu.vn/?classid=1&docid=208451&orggroupid=4&pageid=27160

---

# 7. Mapping pháp lý sang loại tài liệu agent phải xử lý

| Loại tài liệu | Trường quan trọng | Văn bản liên quan | Rủi ro chính |
|---|---|---|---|
| Đơn vay | khách hàng, mục đích vay, số tiền, thời hạn, thu nhập khai báo | Luật TCTD; TT39 | nhầm khai báo với xác minh |
| Hợp đồng tín dụng | số hợp đồng, số tiền, lãi suất, kỳ hạn, trả nợ | TT39 | nhầm phiên bản/phụ lục |
| Hợp đồng lao động | employer, chức danh, loại HĐ, thời hạn, lương | BLLĐ; NĐ145 | hợp đồng hết hạn, thiếu phụ lục |
| Phụ lục tăng lương | mức cũ, mức mới, ngày hiệu lực | BLLĐ; NĐ145 | áp dụng sai giai đoạn |
| Bảng lương | gross, net, phụ cấp, khấu trừ, kỳ lương | BLLĐ; NĐ145 | coi thưởng một lần là thu nhập ổn định |
| Quyết định lương khu vực công | hệ số, phụ cấp, ngày hiệu lực | NĐ73 | tính sai mức theo thời kỳ |
| Sao kê tài khoản | ngày, số tiền, đối tác, nội dung, số dư | Luật TCTD; AML; NĐ13 | dữ liệu nhạy cảm, giao dịch giả lương |
| Hợp đồng điện tử | nội dung, metadata, chữ ký số | Luật GĐĐT; NĐ130; NĐ48 | mất metadata, chữ ký không hợp lệ |
| CCCD/hộ chiếu | định danh, ngày sinh, ngày cấp | AML; NĐ13 | lộ dữ liệu, OCR sai số |
| Giấy xác nhận thu nhập | employer, chức danh, mức thu nhập, kỳ xác nhận | BLLĐ; TT39 | giả mạo, thiếu thẩm quyền ký |

---

# 8. Schema output đề xuất

```json
{
  "document_id": "",
  "document_type": "",
  "document_subtype": "",
  "source_system": "",
  "source_filename": "",
  "sha256": "",
  "language": "vi",
  "page_count": 0,
  "document_date": null,
  "effective_date": null,
  "expiry_date": null,
  "parties": [],
  "fields": {
    "customer_name": null,
    "customer_id_number": null,
    "employer_name": null,
    "job_title": null,
    "employment_contract_type": null,
    "employment_start_date": null,
    "employment_end_date": null,
    "base_salary": null,
    "allowances": [],
    "bonus": null,
    "gross_income": null,
    "net_income": null,
    "salary_period": null,
    "account_number": null,
    "statement_from": null,
    "statement_to": null
  },
  "tables": [],
  "signatures": [],
  "digital_signatures": [],
  "quality_flags": [],
  "evidence": [],
  "personal_data_classification": "sensitive",
  "model_version": "",
  "extracted_at": ""
}
```

---

# 9. Chuẩn bằng chứng và confidence

Mỗi trường phải có:

```json
{
  "field_name": "base_salary",
  "raw_value": "25.000.000 VNĐ/tháng",
  "normalized_value": 25000000,
  "currency": "VND",
  "page": 2,
  "bounding_box": [112, 420, 502, 468],
  "source_text": "Mức lương cơ bản: 25.000.000 VNĐ/tháng",
  "confidence": 0.97,
  "normalization_rule": "vn_currency_v2"
}
```

### Ngưỡng gợi ý

| Confidence | Hành động |
|---:|---|
| `>= 0.95` | tự động ghi draft |
| `0.80–0.95` | ghi draft và highlight |
| `0.60–0.80` | yêu cầu chuyên viên xác nhận |
| `< 0.60` | không điền; tạo trường cần review |

Các trường sau nên có ngưỡng cao hơn:

- số CCCD;
- số tài khoản;
- số tiền;
- ngày hiệu lực;
- ngày hết hạn;
- chữ ký số;
- tên người sử dụng lao động;
- số hợp đồng.

---

# 10. Bộ cờ chất lượng và bất thường

```text
MISSING_PAGE
DUPLICATE_PAGE
ROTATED_PAGE
LOW_RESOLUTION
OCR_UNCERTAIN
HANDWRITING_PRESENT
STAMP_OVER_TEXT
SIGNATURE_MISSING
DIGITAL_SIGNATURE_INVALID
DOCUMENT_EXPIRED
CONTRACT_END_DATE_PASSED
APPENDIX_NOT_FOUND
SALARY_VALUE_CONFLICT
EMPLOYER_NAME_CONFLICT
ACCOUNT_HOLDER_CONFLICT
STATEMENT_PERIOD_INCOMPLETE
TRANSACTION_GAP
UNUSUAL_CREDIT_SPIKE
POSSIBLE_CIRCULAR_TRANSFER
PERSONAL_DATA_EXPOSURE_RISK
```

Agent chỉ gắn cờ; việc kết luận thuộc Consistency Agent, Policy Agent hoặc chuyên viên.

---

# 11. Yêu cầu dataset phát sinh từ các văn bản

## 11.1. Dataset classification

Cần tối thiểu các lớp:

```text
loan_application
loan_agreement
loan_appendix
employment_contract
employment_appendix
salary_adjustment_decision
payslip
payroll
income_confirmation
bank_statement
credit_card_statement
identity_document
digital_contract
government_salary_decision
legal_document
unknown
```

## 11.2. Dataset extraction

Mỗi loại tài liệu cần đủ biến thể:

- bản điện tử chuẩn;
- PDF scan;
- ảnh điện thoại;
- tài liệu nhiều trang;
- song ngữ;
- có dấu/chữ ký;
- có handwriting;
- có phụ lục;
- có trường bị gạch sửa;
- có checkbox;
- có bảng nhiều dòng;
- có text layer lỗi;
- có chữ ký số.

## 11.3. Dataset consistency

Cần các case có chủ đích:

- hợp đồng ghi 20 triệu, bảng lương ghi 25 triệu;
- phụ lục tăng lương có hiệu lực giữa kỳ sao kê;
- employer trên hợp đồng khác tên đơn vị chuyển khoản;
- thiếu sao kê một tháng;
- lương được trả thành hai giao dịch;
- truy lĩnh ba tháng trong một giao dịch;
- thưởng Tết làm tăng đột biến;
- tài liệu hết hạn;
- chữ ký số không hợp lệ;
- số CCCD khác giữa các tài liệu.

## 11.4. Quy tắc chia tập

Không chia ngẫu nhiên theo trang. Phải chia theo:

```text
customer
document_template
employer
time_period
source_system
```

Mục tiêu là tránh cùng một mẫu hoặc cùng một khách hàng xuất hiện ở cả train và test.

---

# 12. Các giới hạn pháp lý cần đưa vào thiết kế

1. **Không tự động từ chối hoặc phê duyệt khoản vay chỉ dựa trên extraction.**
2. **Không sử dụng dữ liệu production để huấn luyện mặc định.**
3. **Không gửi tài liệu khách hàng sang dịch vụ ngoài khi chưa được phê duyệt.**
4. **Không hiển thị toàn bộ số CCCD/số tài khoản trong log.**
5. **Không xóa hoặc thay thế bản gốc bằng bản OCR.**
6. **Không coi ảnh chữ ký là chữ ký số hợp lệ.**
7. **Không suy luận thu nhập nếu không có bằng chứng tài liệu.**
8. **Không coi mọi giao dịch ghi “lương” là thu nhập đã xác minh.**
9. **Không bỏ qua ngày hiệu lực của phụ lục/quyết định lương.**
10. **Không dùng một phiên bản chính sách cho mọi thời kỳ.**

---

# 13. Checklist nghiệm thu Document Extraction Agent

## Chức năng

- [ ] Nhận diện đúng loại tài liệu.
- [ ] Trích xuất được trường bắt buộc.
- [ ] Trích xuất được bảng.
- [ ] Trích xuất được checkbox.
- [ ] Nhận diện chữ ký/dấu.
- [ ] Đọc metadata chữ ký số.
- [ ] Gắn page + bounding box.
- [ ] Chuẩn hóa tiền tệ, ngày tháng và số định danh.
- [ ] Không tự điền trường thiếu.
- [ ] Phát hiện phụ lục và quan hệ giữa tài liệu.

## Pháp lý và bảo mật

- [ ] Có phân loại dữ liệu cá nhân.
- [ ] Có masking.
- [ ] Có RBAC.
- [ ] Có audit log.
- [ ] Có retention policy.
- [ ] Có cơ chế xóa dữ liệu.
- [ ] Có kiểm soát export.
- [ ] Dataset train tách khỏi production.
- [ ] Có phê duyệt khi sử dụng dữ liệu thật.
- [ ] Có kiểm tra hiệu lực văn bản và policy version.

## Chất lượng

- [ ] Có benchmark theo từng document type.
- [ ] Có test scan xấu.
- [ ] Có test tài liệu song ngữ.
- [ ] Có test bảng nhiều trang.
- [ ] Có test phụ lục sửa đổi.
- [ ] Có test chữ ký số lỗi.
- [ ] Có test sai lệch giữa hợp đồng, bảng lương và sao kê.
- [ ] Có human review cho confidence thấp.

---

# 14. Danh mục nguồn chính thức

1. Luật Các tổ chức tín dụng 2024  
   https://vanban.chinhphu.vn/?docid=211190&pageid=27160

2. Luật sửa đổi liên quan đến Luật Các tổ chức tín dụng  
   https://vanban.chinhphu.vn/?classid=1&docid=211201&orggroupid=1&pageid=27160

3. Văn bản hợp nhất Luật Các tổ chức tín dụng  
   https://vanban.chinhphu.vn/?docid=215312&pageid=27160

4. Thông tư 39/2016/TT-NHNN  
   https://vanban.chinhphu.vn/?docid=188822&pageid=27160

5. Thông tư 06/2023/TT-NHNN  
   https://vanban.chinhphu.vn/?docid=208185&pageid=27160

6. Thông tư 10/2023/TT-NHNN  
   https://vanban.chinhphu.vn/?classid=1&docid=208559&pageid=27160&typegroupid=6

7. Thông tư 52/2025/TT-NHNN  
   https://vanban.chinhphu.vn/?docid=216369&pageid=27160

8. Bộ luật Lao động 2019  
   https://vanban.chinhphu.vn/?docid=198540&pageid=27160

9. Nghị định 145/2020/NĐ-CP  
   https://vanban.chinhphu.vn/?docid=201967&pageid=27160

10. Nghị định 73/2024/NĐ-CP  
    https://vanban.chinhphu.vn/?docid=210537&pageid=27160

11. Nghị định 12/2022/NĐ-CP  
    https://vanban.chinhphu.vn/?docid=205182&pageid=27160

12. Luật Giao dịch điện tử 2023  
    https://vanban.chinhphu.vn/?docid=208421&pageid=27160

13. Nghị định 48/2024/NĐ-CP  
    https://vanban.chinhphu.vn/?docid=210212&pageid=27160

14. Luật Phòng, chống rửa tiền 2022  
    https://vanban.chinhphu.vn/?classid=1&docid=207710&pageid=27160&typegroupid=3

15. Nghị định 19/2023/NĐ-CP  
    https://vanban.chinhphu.vn/?classid=1&docid=207830&pageid=27160&typegroupid=4

16. Thông tư 09/2023/TT-NHNN  
    https://vanban.chinhphu.vn/?classid=1&docid=208451&orggroupid=4&pageid=27160

---

## 15. Kết luận triển khai

Các văn bản pháp luật cho thấy Document Extraction Agent phải được xây dựng như một **thành phần xử lý dữ liệu ngân hàng có kiểm soát**, không chỉ là một module OCR.

Ba yêu cầu quan trọng nhất là:

1. **Extraction có bằng chứng:** mọi giá trị phải truy ngược được về tài liệu gốc.
2. **Quản trị dữ liệu chặt chẽ:** dữ liệu thu nhập, sao kê và định danh phải được bảo vệ theo cấp độ nhạy cảm cao.
3. **Không tự đưa ra quyết định nghiệp vụ:** agent chỉ tạo dữ liệu có cấu trúc và cờ bất thường để các agent khác hoặc chuyên viên xử lý.

Trong MVP, phạm vi ưu tiên nên là:

```text
Hợp đồng lao động
Phụ lục điều chỉnh lương
Bảng lương
Giấy xác nhận thu nhập
Sao kê tài khoản
Đơn vay
Hợp đồng tín dụng
```

Đầu ra tối thiểu phải gồm:

```text
document_type
field_value
normalized_value
page
bounding_box
source_text
confidence
quality_flags
legal/policy_version
```
