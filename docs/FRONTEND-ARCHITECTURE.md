# Frontend Architecture & Design Specification

Tài liệu này mô tả chi tiết kiến trúc, công nghệ và thiết kế giao diện (Frontend) cho dự án **Income Verification Expert**. Giao diện này phục vụ cho duy nhất một nhóm người dùng: **Chuyên viên thẩm định (Underwriter)**.

## 1. Tổng quan Kiến trúc (Tech Stack)

Frontend được xây dựng tách biệt hoàn toàn với Backend (Decoupled Architecture) thông qua REST API, sử dụng các công nghệ hiện đại nhất:
- **Framework:** Next.js (App Router) - Hỗ trợ Server-side Rendering (SSR) giúp tải trang cực nhanh và tối ưu SEO (nếu cần).
- **Ngôn ngữ:** TypeScript - Đảm bảo an toàn kiểu dữ liệu (Type-safety), đặc biệt quan trọng khi map với các interface phức tạp từ Backend (như `CaseContext`).
- **Giao diện (Styling):** Tailwind CSS kết hợp với Shadcn/UI - Tạo ra các component bóng bẩy, hiện đại, mang lại cảm giác của một phần mềm nội bộ cao cấp (Premium Enterprise App).
- **State Management:** React Hooks (`useState`, `useEffect`) kết hợp với thư viện fetch data (như SWR hoặc React Query) để tự động polling trạng thái từ Backend.

## 2. Tổ chức Thư mục (Directory Structure)

```text
frontend/
├── src/
│   ├── app/                    # Routing chính của Next.js
│   │   ├── layout.tsx          # Layout tổng thể (Sidebar, Header)
│   │   ├── page.tsx            # Màn hình Dashboard (Danh sách hồ sơ)
│   │   └── cases/[id]/page.tsx # Màn hình chi tiết một hồ sơ thẩm định
│   ├── components/             # Reusable UI Components
│   │   ├── ui/                 # Nút bấm, Card, Modal (từ shadcn)
│   │   ├── CaseOverview.tsx    # Component tóm tắt hồ sơ
│   │   ├── SalaryTable.tsx     # Bảng giao dịch lương
│   │   ├── FindingsPanel.tsx   # Danh sách cảnh báo/anomalies
│   │   └── ActionApproval.tsx  # Checklist các hành động cần duyệt
│   ├── lib/
│   │   ├── api.ts              # Các hàm fetch kết nối tới FastAPI Backend
│   │   └── utils.ts            # Các hàm format tiền tệ, thời gian
│   └── types/
│       └── index.ts            # Chứa các TypeScript Interfaces (CaseContext, WorkflowState...)
```

## 3. Các Màn hình Chính (Key Screens)

### 3.1. Màn hình Dashboard (Danh sách Hồ sơ)
- **Mục đích:** Hiển thị danh sách các khoản vay/hồ sơ đang chờ xử lý.
- **Tính năng:**
  - Bảng danh sách các `application_id`.
  - Trạng thái hiện tại của AI (`EXTRACTING_DATA`, `PENDING_HUMAN_REVIEW`, `COMPLETED`).
  - Nút bấm **"Khởi tạo AI Thẩm định"** để đẩy một hồ sơ mới vào luồng xử lý.

### 3.2. Màn hình Chi tiết Thẩm định (Workspace View)
Đây là màn hình cốt lõi của ứng dụng, được thiết kế theo dạng **Split View (Chia đôi màn hình)** để tối ưu trải nghiệm đọc đối chiếu của chuyên viên.

#### Nửa bên trái: Document Viewer & Bằng chứng
- Hiển thị file PDF của khách hàng (Sao kê ngân hàng, Hợp đồng lao động).
- Hỗ trợ tính năng **Evidence Highlighting**: Khi chuyên viên bấm vào một giao dịch lương ở bên phải, màn hình bên trái tự động cuộn đến đúng trang PDF và bôi đậm vùng (snippet) chứa thông tin đó.

#### Nửa bên phải: AI Analysis & Action Panel
Chia thành các Widget dạng thẻ (Cards) hiện đại:
1. **Summary Widget:** Tóm tắt Tên khách hàng, Mức lương khai báo, Mức lương AI tính toán (có màu xanh nếu đạt, đỏ nếu rủi ro).
2. **Salary Transactions Widget:** Bảng danh sách các dòng tiền lương đổ về hàng tháng, được bóc tách từ OCR.
3. **Findings & Anomalies Widget:** Danh sách các bất thường mà Policy Agent và Consistency Agent phát hiện (Ví dụ: Lương tháng 5 bị rớt đột ngột, Tên công ty không khớp HĐLĐ). Cảnh báo được phân loại màu (Vàng = Warning, Đỏ = Critical).
4. **Recommendation & Action Panel:** Khối UI quan trọng nhất nằm dưới cùng.
   - Hiển thị kết luận của AI.
   - Danh sách các Checklist Actions (vd: Cập nhật hệ thống LOS, Gửi email xin thêm hồ sơ).
   - Có 2 nút bấm to: **"Phê duyệt & Thực thi"** (Màu xanh) và **"Trả về xử lý thủ công"** (Màu xám).

## 4. Cơ chế Data Flow & Tương tác

1. **Polling Trạng thái (Loading State):**
   - Khi hồ sơ ở trạng thái `EXTRACTING_DATA` hoặc `CROSS_CHECKING`, Frontend sẽ tự động gọi API `GET /cases/{id}` mỗi 2 giây.
   - Màn hình sẽ hiển thị các Skeleton Loading hoặc Progress Bar bóng bẩy để thông báo cho user biết Agent nào đang làm việc.
2. **Dừng Polling (Human Review State):**
   - Khi API trả về trạng thái `PENDING_HUMAN_REVIEW`, tính năng polling dừng lại. Giao diện hiển thị toàn bộ dữ liệu đã phân tích.
3. **Gửi Phê duyệt (Submission):**
   - User tick chọn các hành động muốn duyệt, bấm "Phê duyệt".
   - Frontend gửi payload `POST /review` kèm danh sách action ID.
   - Giao diện chuyển sang màn hình thành công, hiển thị các log Audit (Dấu vết kiểm toán) trả về từ Backend.

## 5. Nguyên tắc Thẩm mỹ (Aesthetics Rules)
- **Premium Feel:** Giao diện không được giống các bảng biểu Excel khô khan. Cần sử dụng Glassmorphism nhẹ, bo góc, bóng đổ (drop-shadows) tinh tế.
- **Micro-animations:** Khi AI đang phân tích, hiển thị các hiệu ứng pulse (nhịp đập) mượt mà để báo hiệu hệ thống đang tư duy.
- **Màu sắc (Color Palette):**
  - Nền tổng thể: Xám nhạt hiện đại (Slate-50) hoặc Dark Mode.
  - Success/Approved: Emerald Green.
  - Anomalies/Warnings: Amber/Orange (Không dùng màu đỏ chót gây chói mắt, trừ khi Critical).
