# Product Requirements Document — Income Verification Expert

**Tên dự án:** Income Verification Expert — Trợ lý xác minh thu nhập tín chấp

**Phiên bản:** 2.1.0

**Trạng thái:** Approved

**Actor duy nhất:** Chuyên viên thẩm định tín chấp

**Task duy nhất:** Kiểm tra và xác minh thu nhập của khách hàng từ bộ hồ sơ vay

---

## 1. Tóm tắt sản phẩm

Income Verification Expert là hệ thống AI đa tác tử hỗ trợ chuyên viên thẩm định đọc bộ hồ sơ vay tín chấp cá nhân, trích xuất dữ liệu thu nhập, phân tích dòng tiền, đối chiếu chính sách nội bộ, phát hiện thiếu hoặc bất thường và tạo kết quả xác minh có bằng chứng.

Sản phẩm chỉ hỗ trợ bước xác minh thu nhập. Hệ thống không chấm điểm tín dụng, không đánh giá toàn bộ khả năng trả nợ và không phê duyệt hoặc từ chối khoản vay.

## 2. Bài toán

Chuyên viên hiện phải đọc và đối chiếu thủ công nhiều nguồn:

- đơn đề nghị vay hoặc phiếu khai thông tin;
- hợp đồng lao động và phụ lục;
- bảng lương hoặc xác nhận lương;
- sao kê tài khoản ngân hàng;
- chính sách xác minh thu nhập nội bộ.

Quy trình thủ công tốn thời gian và dễ bỏ sót chênh lệch về tên khách hàng, đơn vị công tác, mức lương, nguồn chuyển lương, kỳ sao kê hoặc tài liệu bắt buộc.

## 3. Mục tiêu sản phẩm

Hệ thống phải giúp chuyên viên trả lời nhanh, có căn cứ:

1. Thu nhập khai báo có khớp với chứng từ không?
2. Các khoản nhận nào có đủ căn cứ được nhận diện là thu nhập?
3. Thu nhập bình quân và thu nhập đủ điều kiện theo chính sách là bao nhiêu?
4. Dòng tiền có ổn định và có kỳ bất thường không?
5. Đơn vị trả lương có khớp với hợp đồng lao động không?
6. Hồ sơ còn thiếu tài liệu hoặc có điểm nào cần chuyên viên phán đoán?

## 4. Đầu vào MVP

### 4.1. Hồ sơ khách hàng

- đơn vay/phiếu khai thông tin;
- hợp đồng lao động và phụ lục;
- bảng lương hoặc xác nhận lương;
- sao kê tài khoản theo số kỳ do chính sách áp dụng quy định.

### 4.2. Tri thức nghiệp vụ

- chính sách xác minh thu nhập đã được phê duyệt;
- metadata về phiên bản, ngày hiệu lực, sản phẩm và phạm vi áp dụng;
- quy trình xử lý thiếu hồ sơ hoặc ngoại lệ.

MVP không tự truy xuất dữ liệu CIC, cơ quan thuế, bảo hiểm hoặc nguồn bên ngoài thời gian thực.

## 5. Phạm vi chức năng

### 5.1. Orchestrator

- khởi tạo và quản lý workflow theo `application_id`;
- điều phối các bước, checkpoint state, retry lỗi kỹ thuật và routing;
- kiểm tra output đúng schema;
- không tự tính thu nhập, diễn giải chính sách hoặc gọi API mutation.

### 5.2. Document Agent

- nhận diện loại tài liệu;
- trích xuất tên khách hàng, đơn vị công tác, lương hợp đồng, thời hạn hợp đồng và giao dịch liên quan;
- gắn mỗi fact với `evidence_id`, tài liệu, trang và vùng dữ liệu;
- trả missing/unreadable status thay vì suy đoán.

### 5.3. Income Analysis Agent

- phân loại giao dịch có khả năng là lương;
- loại trừ giao dịch nội bộ hoặc khoản thu không đủ căn cứ;
- gọi deterministic tools để tính trung bình, độ biến động và chênh lệch;
- lưu input, kỳ dữ liệu, currency, công thức, quy tắc làm tròn và calculation version.

### 5.4. Policy Agent

- truy vấn chính sách xác minh thu nhập bằng RAG;
- áp dụng đúng phiên bản/ngày hiệu lực;
- trả citation gồm tài liệu, trang, mục, đoạn trích và ngày hiệu lực;
- chuyển human review nếu không tìm thấy hoặc có policy conflict.

### 5.5. Consistency Agent

- đối chiếu thu nhập khai báo, hợp đồng, bảng lương và sao kê;
- kiểm tra đơn vị công tác với nguồn chuyển lương;
- kiểm tra kỳ dữ liệu, currency và bộ chứng từ bắt buộc;
- tạo findings có severity, evidence và rule version.

### 5.6. Recommendation Builder

- tổng hợp kết quả xác minh sơ bộ;
- trình bày thu nhập khai báo, bình quân và đủ điều kiện;
- liệt kê bất thường, tài liệu thiếu, policy citations và action đề xuất;
- không đưa ra quyết định tín dụng.

### 5.7. Human Review Gate

Chuyên viên được phép:

- chấp thuận kết quả/action của bước xác minh;
- chỉnh sửa dữ liệu hoặc action và ghi lý do;
- từ chối kết quả AI và chuyển xử lý thủ công;
- yêu cầu chạy lại sau khi bổ sung hồ sơ.

Các lựa chọn này không phải phê duyệt hoặc từ chối khoản vay.

### 5.8. Action Executor

Action Executor là service rule-based, không phải LLM agent. Service kiểm tra schema, quyền, trạng thái, idempotency và audit trước khi gọi Mock LOS/DMS/Workflow/Notification.

## 6. Đầu ra MVP

### 6.1. Báo cáo xác minh

Báo cáo hiển thị:

- thu nhập khách hàng khai báo;
- thu nhập nhận diện theo từng kỳ;
- thu nhập bình quân;
- thu nhập đủ điều kiện theo policy;
- độ ổn định và kỳ bất thường;
- tài liệu thiếu hoặc không đọc được;
- findings và evidence có thể mở lại;
- policy citations;
- action đề xuất.

### 6.2. Draft phiếu xác minh

Hệ thống được tự động điền artifact trạng thái `DRAFT` và đính kèm evidence. Việc ghi nhận thu nhập chính thức vào LOS chỉ diễn ra sau khi chuyên viên xác nhận.

### 6.3. Yêu cầu bổ sung hồ sơ

Hệ thống tạo nội dung nháp theo mẫu. Gửi yêu cầu cho khách hàng hoặc kênh bên ngoài bắt buộc có human approval và được thực thi qua Action Executor.

### 6.4. Exception task

Hệ thống có thể tạo task nội bộ có thể đảo ngược, gắn reason code, mức độ ưu tiên và liên kết tới evidence. Action phải có idempotency key và audit event.

## 7. Luồng người dùng chính

1. Chuyên viên mở hồ sơ và chọn “Xác minh thu nhập”.
2. Hệ thống lấy bộ tài liệu theo quyền.
3. Document Agent trích xuất structured facts và evidence.
4. Income Agent và Policy Agent chạy song song khi đủ input.
5. Consistency Agent đối chiếu dữ liệu và chính sách.
6. Recommendation Builder tạo báo cáo và action đề xuất.
7. Chuyên viên review, chỉnh sửa hoặc chuyển xử lý thủ công.
8. Action Executor thực hiện action thuộc quyền/đã được duyệt.
9. Hệ thống xác minh kết quả, ghi audit và hoàn tất tác vụ.

## 8. Trạng thái kết quả

Các trạng thái nghiệp vụ hợp lệ:

- `READY_FOR_REVIEW`;
- `NEEDS_CLARIFICATION`;
- `MISSING_DOCUMENTS`;
- `POLICY_NOT_FOUND`;
- `MANUAL_REVIEW_REQUIRED`;
- `TECHNICAL_ERROR`;
- `COMPLETED`.

Không dùng `APPROVED` hoặc `REJECTED` làm trạng thái khoản vay trong sản phẩm này.

## 9. Ngoài phạm vi

- chấm điểm tín dụng hoặc tính xác suất vỡ nợ;
- truy vấn CIC;
- KYC/AML và sanctions screening;
- phân tích pháp lý hoặc rủi ro ngành;
- định giá tài sản bảo đảm;
- DSCR, D/E, LTV hoặc phân tích tài chính doanh nghiệp;
- quyết định hạn mức;
- phê duyệt hoặc từ chối khoản vay;
- tạo hợp đồng tín dụng hoặc giải ngân;
- bỏ qua/ghi đè policy;
- sửa hoặc xóa tài liệu nguồn;
- ghi trực tiếp vào production LOS/DMS trong MVP;
- tự động huấn luyện model từ phản hồi chuyên viên.

## 10. Tiêu chí nghiệm thu MVP

### 10.1. Functional acceptance

- hỗ trợ đủ các loại tài liệu đầu vào đã định nghĩa;
- mọi fact và finding quan trọng mở được evidence nguồn;
- mọi policy conclusion có citation đầy đủ;
- mọi phép tính có input và calculation version;
- missing/unreadable evidence không tạo giá trị suy đoán;
- outbound và official write bị chặn nếu thiếu human approval;
- action lặp lại không tạo tác dụng phụ trùng;
- mọi state transition và action có audit event.

### 10.2. Evaluation targets

Các mục tiêu dưới đây chỉ được đo trên benchmark đã được domain owner phê duyệt:

| Tiêu chí | Mục tiêu ban đầu |
| --- | --- |
| Thời gian xử lý | Dưới 3 phút/hồ sơ demo |
| Độ chính xác trường bắt buộc | Từ 95% trở lên |
| Phát hiện hồ sơ thiếu | Từ 90% trở lên |
| Explainability | 100% kết luận trọng yếu có evidence/citation |
| Human correction rate | Theo dõi và giảm qua từng phiên bản, không tự huấn luyện |

## 11. Kịch bản demo

Khách hàng khai thu nhập 25 triệu đồng/tháng. Sáu tháng sao kê có năm tháng khoảng 25 triệu đồng và một tháng 18 triệu đồng. Hợp đồng ghi lương 22 triệu đồng, có thêm khoản hỗ trợ hiệu suất và thiếu phụ lục điều chỉnh lương.

Hệ thống phải:

- trích xuất đúng các giá trị và nguồn;
- tính thu nhập bằng deterministic tool;
- áp dụng policy có citation để xác định mức đủ điều kiện;
- đánh dấu tháng bất thường và phụ lục còn thiếu;
- tạo báo cáo/draft/action đề xuất;
- yêu cầu chuyên viên xác nhận trước mọi outbound hoặc official write.
