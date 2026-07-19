# Synthetic test cases

`dataset/synthetic_cases.json` chứa 20 scenario có ground truth. `backend/scripts/seed_synthetic_cases.py` tạo case và bốn loại tài liệu text/CSV để pipeline xử lý, bỏ/sửa tài liệu theo từng scenario.

Automated gates kiểm tra schema/calculator/RAG isolation/workflow/review/action, FPT HTTP structured call, create/upload/run/reload/evidence và completeness của 20 ground truths. Tests mặc định offline và không tiêu thụ competition API quota.
