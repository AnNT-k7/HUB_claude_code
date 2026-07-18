# Product Requirements Document (PRD) - Income Verification Expert

**Version:** 2.0.0  
**Status:** Approved  
**Author:** Senior Software Architect  

---

## 1. Tóm tắt dự án (Project Summary)

> **Xây dựng hệ thống AI đa tác tử hỗ trợ chuyên viên thẩm định tín chấp xác minh thu nhập khách hàng bằng cách đọc và đối chiếu đơn vay, hợp đồng lao động, bảng lương và sao kê; áp dụng chính sách nội bộ; phát hiện sai lệch; và tự động tạo báo cáo có dẫn chứng để chuyên viên xem xét.**

Dự án tập trung vào một phạm vi duy nhất, rõ ràng, có đầu vào/đầu ra đo lường được nhằm đảm bảo tính khả thi, hiệu quả và kiểm soát rủi ro, thay vì làm "AI thẩm định tín chấp từ đầu đến cuối". Tên dự án nội bộ: **Income Verification Expert – Trợ lý xác minh thu nhập tín chấp**.

---

## 2. Bài toán & Mục tiêu (Problem & Goal)

### 2.1. Đối tượng sử dụng (Actor)
**Chuyên viên thẩm định tín chấp**

### 2.2. Nhiệm vụ (Task)
**Kiểm tra và xác minh thu nhập của khách hàng từ bộ hồ sơ vay.**

### 2.3. Vấn đề hiện tại
Hiện chuyên viên phải tự đọc và đối chiếu thủ công các tài liệu:
* Đơn đề nghị vay.
* Hợp đồng lao động.
* Bảng lương.
* Sao kê tài khoản 3–6 tháng.
* Thông tin đơn vị công tác.

Họ phải tự trả lời các câu hỏi:
1. Thu nhập khách hàng khai báo có đúng không?
2. Tiền lương có vào đều không?
3. Đơn vị trả lương có khớp với nơi làm việc không?
4. Thu nhập nào được tính, thu nhập nào không được tính?
5. Hồ sơ có điểm bất thường hoặc thiếu tài liệu không?

---

## 3. Đầu vào & Đầu ra (Inputs & Outputs)

### 3.1. Đầu vào (Inputs)
Một bộ hồ sơ vay gồm:
* Đơn vay (ví dụ: khách hàng khai thu nhập 25 triệu đồng/tháng).
* Hợp đồng lao động.
* Bảng lương.
* Sao kê ngân hàng 6 tháng.
* Chính sách xác minh thu nhập nội bộ.

### 3.2. Đầu ra (Outputs)
Hệ thống tạo ra các đầu ra cụ thể để hỗ trợ chuyên viên:

**1. Báo cáo ngắn tổng hợp kết quả** (ví dụ minh họa):

```text
KẾT QUẢ XÁC MINH THU NHẬP

Thu nhập khách hàng khai báo: 25.000.000 đồng/tháng

Thu nhập lương ghi nhận trên sao kê:
- Tháng 1: 24.800.000
- Tháng 2: 25.100.000
- Tháng 3: 24.900.000
- Tháng 4: 25.200.000
- Tháng 5: 18.000.000
- Tháng 6: 25.000.000

Thu nhập bình quân: 23.833.000 đồng/tháng
Thu nhập đủ điều kiện theo chính sách: 23.000.000 đồng/tháng

Kết quả đối chiếu:
✓ Tên khách hàng khớp
✓ Công ty trả lương khớp hợp đồng lao động
✓ Ngày trả lương tương đối ổn định
⚠ Tháng 5 thấp hơn bình quân 28%
⚠ Thu nhập khai báo cao hơn thu nhập đủ điều kiện 2 triệu đồng

Tài liệu còn thiếu:
- Phụ lục hợp đồng lao động mới nhất

Đề xuất:
Chuyển chuyên viên kiểm tra nguyên nhân thu nhập tháng 5 giảm.
```

**2. Điền phiếu xác minh thu nhập:** Ghi thu nhập khai báo, thu nhập bình quân, thu nhập đủ điều kiện và các tháng bất thường vào checklist trên hệ thống LOS (Loan Origination System).

**3. Tạo yêu cầu bổ sung hồ sơ:** Tự động tạo yêu cầu theo format chuẩn để có thể gửi thẳng cho khách hàng (ví dụ: "Bổ sung sao kê tháng 5" hoặc "Bổ sung phụ lục điều chỉnh lương").

**4. Tạo exception task:** Tạo một tác vụ cho chuyên viên, gắn mức độ ưu tiên và cung cấp liên kết dẫn đến đúng giao dịch hoặc điểm dữ liệu bất thường.

*Lưu ý: AI không phê duyệt hay từ chối khoản vay. Nó chỉ chuẩn bị kết quả xác minh để chuyên viên quyết định.*

---

## 4. Thiết kế hệ thống Đa tác tử (Multi-Agent Architecture)

Hệ thống được thiết kế tối giản phục vụ 1 actor và 1 task nhưng vẫn thể hiện đầy đủ năng lực phối hợp đa tác tử (multi-agent collaboration). Không cần xây dựng agent CIC, pháp lý, AML trong phiên bản đầu.

### 4.1. Document Extraction Agent
* **Nhiệm vụ:** Nhận diện loại tài liệu; trích xuất tên, công ty, mức lương, thời hạn hợp đồng, giao dịch lương từ sao kê.
* **Đầu ra:** Dữ liệu có cấu trúc và vị trí bằng chứng.

### 4.2. Income Analysis Agent
* **Nhiệm vụ:** Nhận diện các khoản có khả năng là lương, tính thu nhập bình quân, đánh giá mức độ ổn định. Phát hiện tháng thiếu lương/thu nhập giảm bất thường. Loại bỏ chuyển khoản nội bộ hoặc khoản thu không được tính.

### 4.3. Policy Checking Agent
* **Nhiệm vụ:** Tra cứu chính sách nội bộ bằng RAG. Xác định số tháng sao kê cần kiểm tra, áp dụng quy tắc tính thu nhập đủ điều kiện, kiểm tra điều kiện về thời gian làm việc và HĐLĐ. Trích dẫn đúng điều khoản chính sách.

### 4.4. Report Agent
* **Nhiệm vụ:** Tổng hợp kết quả, hiển thị các điểm đạt/không đạt/cần kiểm tra. Tạo báo cáo theo mẫu của chuyên viên, đính kèm bằng chứng cho từng kết luận.

---

## 5. Phạm vi KHÔNG làm (Out of Scope)

Cần ghi rõ những nội dung ngoài phạm vi nhằm giữ ranh giới rõ ràng cho dự án:
* Không chấm điểm tín dụng.
* Không truy vấn CIC.
* Không quyết định hạn mức vay.
* Không phê duyệt hoặc từ chối khách hàng.
* Không thực hiện AML/KYC.
* Không đánh giá toàn bộ khả năng trả nợ.
* Không tự động giải ngân.

---

## 6. Tiêu chí đánh giá (Evaluation Criteria)

| Tiêu chí | Cách đo lường |
| :--- | :--- |
| **Thời gian xử lý** | Từ 15–20 phút xuống dưới 3 phút/hồ sơ |
| **Độ chính xác trích xuất** | Trên 95% đối với trường dữ liệu bắt buộc |
| **Độ chính xác nhận diện lương** | So sánh với kết quả của chuyên viên |
| **Tỷ lệ phát hiện hồ sơ thiếu** | Trên 90% |
| **Khả năng giải thích** | Mỗi kết luận có tài liệu và dòng dữ liệu làm bằng chứng |
| **Mức độ chấp nhận** | Chuyên viên đồng ý với kết quả hoặc chỉ chỉnh sửa nhỏ |
| **Giảm thao tác** | Số trường chuyên viên không còn phải nhập thủ công |

---

## 7. Kịch bản Demo tốt (Demo Scenario)

* **Đầu vào:** Khách hàng khai thu nhập 25 triệu đồng/tháng.
* **Xử lý AI:** Đọc 6 tháng sao kê và phát hiện:
  * 5 tháng nhận khoảng 25 triệu đồng.
  * 1 tháng chỉ nhận 18 triệu đồng.
  * Hợp đồng lao động ghi mức lương 22 triệu đồng.
  * Có thêm khoản “hỗ trợ hiệu suất” nhưng chính sách không cho tính toàn bộ.
  * Thu nhập đủ điều kiện chỉ là 23 triệu đồng.
  * Hồ sơ thiếu phụ lục điều chỉnh lương.
* **Đầu ra:** Chuyên viên nhận ngay báo cáo, mở đúng giao dịch bất thường và quyết định yêu cầu khách hàng bổ sung tài liệu.
