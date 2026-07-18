# PHIẾU TRÌNH XÁC MINH THU NHẬP

**Kính gửi:** Ban Giám đốc / Trưởng phòng Phê duyệt Tín dụng
**Ngày lập:** {{ date }}

## I. THÔNG TIN HỒ SƠ
- **Mã hồ sơ (Application ID):** {{ case.application_id }}
- **Tên khách hàng:** {{ case.extracted_data.customer_name or 'Chưa xác định' }}
- **Nơi công tác:** {{ case.extracted_data.employer or 'Chưa xác định' }}

## II. KẾT QUẢ ĐÁNH GIÁ THU NHẬP
- **Thu nhập khai báo:** {{ case.extracted_data.declared_income or 0 }} {{ case.extracted_data.currency }}
- **Lương theo Hợp đồng:** {{ case.extracted_data.contract_salary or 0 }} {{ case.extracted_data.currency }}
- **Thu nhập tính toán đủ điều kiện (Qualified Income):** {{ case.calculated_income.qualified_income or 0 }} {{ case.extracted_data.currency }}
- **Thu nhập bình quân 6 tháng:** {{ case.calculated_income.average_6_months or 0 }} {{ case.extracted_data.currency }}
- **Đánh giá mức độ ổn định:** {% if case.calculated_income.is_stable %}Ổn định{% else %}Không ổn định{% endif %}

## III. CÁC ĐIỂM BẤT THƯỜNG / CẢNH BÁO (FINDINGS)
{% if case.findings %}
Các bất thường được AI phát hiện trong quá trình đối chiếu hồ sơ:
{% for finding in case.findings %}
- **[{{ finding.severity.value }}]** {{ finding.message }} (Nguồn: {{ finding.evidence_id }})
{% endfor %}
{% else %}
Không có bất thường nào được phát hiện.
{% endif %}

## IV. TÀI LIỆU CÒN THIẾU
{% if case.extracted_data.missing_documents %}
Khách hàng cần bổ sung các tài liệu sau để hoàn thiện hồ sơ:
{% for doc in case.extracted_data.missing_documents %}
- {{ doc }}
{% endfor %}
{% else %}
Hồ sơ đầy đủ tài liệu.
{% endif %}

## V. ĐỀ XUẤT CỦA CHUYÊN VIÊN
- Các hành động đã thực thi: 
{% for action in case.proposed_actions %}
  {% if action.is_approved %}
  - Đã thực hiện: {{ action.description }}
  {% endif %}
{% endfor %}

---------------------------------------------
*Báo cáo được tạo tự động bởi hệ thống Income Verification Expert.*
