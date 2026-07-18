# Trợ lý xác minh thu nhập tín chấp — Frontend Prototype

Dependency-free prototype mô phỏng kiến trúc đa tác tử cho quy trình xác minh thu nhập tín chấp.

## Run

Open `index.html` directly in a browser, or serve the folder:

```bash
python3 -m http.server 8080
```

Then open `http://localhost:8080`.

## Main demo path

1. Mở **Hồ sơ tín chấp** và chọn **Create New Case** để nhập số tiền, kỳ hạn, thông tin thu nhập và file liên quan.
2. Chọn **Bắt đầu xác minh**; Underwriter UI mở hồ sơ và Orchestrator lập workflow.
3. Document Agent, Income Agent và Policy Agent xử lý song song.
4. Consistency Agent đối chiếu kết quả; Recommendation Builder tạo đề xuất có bằng chứng.
5. Chuyên viên chọn chấp thuận, yêu cầu chỉnh sửa hoặc từ chối tại Human Review Gate.
6. Chỉ sau khi chấp thuận, Action Executor mới cập nhật LOS, DMS, Workflow, Notification và Audit.

## Views

- **Command Center:** pipeline điều phối, phân tích song song, consistency check, recommendation, Human Review và Action Executor.
- **Hồ sơ tín chấp:** tạo hồ sơ mới, tải tài liệu và quản lý danh sách hồ sơ.

## Files

- `index.html`: semantic UI structure and all views.
- `styles.css`: responsive visual system, layout, motion, and component states.
- `app.js`: mock workflow engine and interactive UI state transitions.
- `BACKEND-CONTRACT.md`: suggested FastAPI endpoints, WebSocket events, and state model inferred from the UI.

## Design direction

- Dark navy banking operations command center với trạng thái realtime dễ đọc.
- Lưới pipeline co giãn, dùng toàn bộ chiều ngang và không chồng node/nhãn cạnh.
- Agent chuyên môn không ghi trực tiếp vào hệ thống nghiệp vụ.
- Action Executor luôn bị khóa cho đến khi có quyết định của con người.
