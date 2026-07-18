# Backend API Contracts & Data Models

Tài liệu này định nghĩa rõ ràng cấu trúc dữ liệu và API Contracts từ Backend để Frontend (hoặc hệ thống tạo code Frontend) có thể sử dụng làm nguồn chân lý (source of truth) để sinh giao diện cho **Income Verification Expert**.

---

## 1. Domain Data Models (TypeScript Interfaces)

Frontend cần định nghĩa các interface sau để đồng bộ với cấu trúc `CaseContext` (Context trạng thái chung của hồ sơ) trả về từ Backend.

### 1.1. Core Enums
```typescript
export enum WorkflowState {
  INIT = "INIT",
  FETCHING_DOCUMENTS = "FETCHING_DOCUMENTS",
  EXTRACTING_DATA = "EXTRACTING_DATA",
  ANALYZING_INCOME_AND_POLICY = "ANALYZING_INCOME_AND_POLICY",
  CHECKING_CONSISTENCY = "CHECKING_CONSISTENCY",
  PENDING_HUMAN_REVIEW = "PENDING_HUMAN_REVIEW",
  EXECUTING_ACTIONS = "EXECUTING_ACTIONS",
  COMPLETED = "COMPLETED"
}

export enum HumanReviewOutcome {
  APPROVED = "APPROVED",
  REJECTED = "REJECTED",
  REVISION_REQUESTED = "REVISION_REQUESTED"
}

export enum FindingSeverity {
  INFO = "INFO",
  WARNING = "WARNING",
  CRITICAL = "CRITICAL"
}
```

### 1.2. Core Interfaces
```typescript
export interface SalaryTransaction {
  month: string; // Định dạng YYYY-MM
  amount: number;
  source: string; // Tên đơn vị chuyển tiền
  evidence_id: string; // Tham chiếu đến dòng chứng từ
}

export interface ExtractedData {
  customer_name: string | null;
  declared_income: number | null;
  contract_salary: number | null;
  currency: string;
  employer: string | null;
  salary_transactions: SalaryTransaction[];
  missing_documents: string[]; // VD: ["Phụ lục HĐLĐ"]
}

export interface CalculatedIncome {
  average_3_months: number | null;
  average_6_months: number | null;
  qualified_income: number | null;
  is_stable: boolean;
}

export interface Finding {
  id: string;
  type: string; // VD: "INCOME_DROP", "EMPLOYER_MISMATCH"
  severity: FindingSeverity;
  message: string;
  evidence_id: string | null; // Bằng chứng cho finding này
}

export interface ProposedAction {
  action_id: string;
  action_type: string; // VD: "REQUEST_DOCUMENTS", "UPDATE_LOS"
  description: string;
  parameters: Record<string, any>; // VD: { missing_doc: "Sao kê tháng 5" }
  requires_approval: boolean;
  is_approved?: boolean;
}

export interface DocumentEvidence {
  evidence_id: string;
  document_name: string;
  page_number: number;
  snippet_url?: string;
  raw_text?: string;
}
```

### 1.3. Case Context (Trạng thái tổng thể)
Đây là schema chính mà API `GET /income-verifications/{case_id}` sẽ trả về cho Frontend, là bản tổng hợp của tất cả các Specialist Agents (Document, Income, Policy, Consistency).

```typescript
export interface CaseContext {
  case_id: string;
  application_id: string;
  workflow_state: WorkflowState;
  extracted_data: ExtractedData;
  calculated_income: CalculatedIncome;
  findings: Finding[];
  proposed_actions: ProposedAction[];
  evidence_list: DocumentEvidence[];
  created_at: string;
  updated_at: string;
}
```

---

## 2. API Endpoints

Mọi request từ Frontend đều cần gắn header Authorization. Backend trả về chuẩn JSON.

### 2.1. Lấy thông tin hồ sơ (Fetch Case)
- **Endpoint:** `GET /api/v1/income-verifications/{case_id}`
- **Mục đích:** Load toàn bộ dữ liệu hồ sơ để render UI. Frontend sẽ dựa vào `workflow_state` để quyết định hiển thị màn hình loading (nếu agent đang chạy) hay màn hình review (PENDING_HUMAN_REVIEW).
- **Ví dụ Response (JSON):**
```json
{
  "case_id": "case-1234",
  "application_id": "app-5678",
  "workflow_state": "PENDING_HUMAN_REVIEW",
  "extracted_data": {
    "customer_name": "Nguyen Van A",
    "declared_income": 25000000,
    "contract_salary": 22000000,
    "currency": "VND",
    "employer": "Công ty ABC",
    "salary_transactions": [
      { "month": "2026-05", "amount": 18000000, "source": "CONG TY ABC", "evidence_id": "ev-1" }
    ],
    "missing_documents": ["Phụ lục điều chỉnh lương"]
  },
  "calculated_income": {
    "average_3_months": 22000000,
    "average_6_months": 23833000,
    "qualified_income": 23000000,
    "is_stable": false
  },
  "findings": [
    {
      "id": "f1",
      "type": "INCOME_DROP",
      "severity": "WARNING",
      "message": "Tháng 5 thu nhập giảm 28% so với bình quân",
      "evidence_id": "ev-1"
    }
  ],
  "proposed_actions": [
    {
      "action_id": "act1",
      "action_type": "REQUEST_DOCUMENTS",
      "description": "Yêu cầu bổ sung sao kê tháng 5",
      "parameters": {},
      "requires_approval": true
    }
  ],
  "evidence_list": [
    {
      "evidence_id": "ev-1",
      "document_name": "Sao kê TCB.pdf",
      "page_number": 2,
      "raw_text": "Giao dich: 18,000,000 VND"
    }
  ],
  "created_at": "2026-07-18T10:00:00Z",
  "updated_at": "2026-07-18T10:05:00Z"
}
```

### 2.2. Gửi quyết định phê duyệt (Submit Human Review)
- **Endpoint:** `POST /api/v1/income-verifications/{case_id}/review`
- **Mục đích:** Gửi quyết định của chuyên viên sau khi kiểm tra màn hình `PENDING_HUMAN_REVIEW`.
- **Request Payload Schema:**
```typescript
interface ReviewRequest {
  outcome: HumanReviewOutcome; // APPROVED, REJECTED, REVISION_REQUESTED
  reason: string; // Ghi chú của chuyên viên
  approved_action_ids: string[]; // Danh sách ID các action mà user chọn cho phép thực thi
  edited_qualified_income?: number; // (Tùy chọn) Ghi đè nếu kết quả tính của AI chưa đúng
}
```
- **Ví dụ Request:**
```json
{
  "outcome": "APPROVED",
  "reason": "Đã kiểm tra bất thường, đồng ý gửi yêu cầu bổ sung",
  "approved_action_ids": ["act1"]
}
```
- **Response Payload:**
```json
{
  "message": "Review submitted successfully",
  "next_state": "EXECUTING_ACTIONS"
}
```

### 2.3. Khởi tạo quy trình mới (Start Workflow)
- **Endpoint:** `POST /api/v1/applications/{application_id}/income-verification`
- **Mục đích:** Kích hoạt quá trình Orchestrator gọi các Agent chạy nền.
- **Request Payload:** `{}`
- **Response Payload:**
```json
{
  "case_id": "case-1234",
  "workflow_state": "FETCHING_DOCUMENTS"
}
```

---

## 3. Hướng dẫn tích hợp cho Frontend

Khi Frontend Developer (hoặc Generator Agent) đọc file này để sinh UI, hãy tuân theo các UX Pattern sau:

1. **Dashboard Tách Biệt Khối Thông Tin:** 
   Hiển thị `extracted_data` (Thông tin khai báo/trích xuất) cạnh `calculated_income` (Kết quả tính toán) để dễ đối chiếu.

2. **Evidence Linking (Click to Show):** 
   Mỗi dòng giao dịch lương (`SalaryTransaction`) hoặc cảnh báo (`Finding`) đều có trường `evidence_id`. UI nên render dưới dạng clickable link/icon. Khi bấm vào, tìm trong mảng `evidence_list` và popup hiển thị `document_name` và `raw_text`.

3. **Action Approval List:** 
   Trong trạng thái `PENDING_HUMAN_REVIEW`, duyệt mảng `proposed_actions`. Hiển thị dưới dạng một danh sách Checklist (Checkbox). Chuyên viên tick chọn những action nào họ đồng ý, và mảng ID đó sẽ được truyền vào `approved_action_ids` khi gọi API `/review`.

4. **Polling Loading State:**
   Nếu API GET case trả về `workflow_state` không phải là `PENDING_HUMAN_REVIEW` hoặc `COMPLETED` (ví dụ `EXTRACTING_DATA`), Frontend hiển thị màn hình Loading Spinner / Progress Bar thể hiện AI đang làm việc.
