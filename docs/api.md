# API

Tất cả endpoint demo yêu cầu:

```text
X-Role: UNDERWRITER
X-Reviewer-Id: <identity>
```

Case APIs: create/list/detail, multipart upload (`document_type`, `file`), run, status, result, evidence, audit và download. Workflow APIs tương thích target docs: start theo application, get context, review, retry actions.

Errors: 403 thiếu role; 404 case/document; 409 duplicate/review state; 413 file lớn; 415 suffix không hỗ trợ; 422 input/extraction contract. Pipeline lưu lỗi trong CaseContext/audit và dừng ở business-safe state.
