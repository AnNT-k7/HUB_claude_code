# Corpus audit

Generated inventory for the hackathon MVP. Runtime policy retrieval does not index unrelated sources.

## Summary

- Direct income-verification sources: 6
- Indirect references: 6
- Unrelated to runtime policy: 57
- Duplicate checksum groups: 2
- PDFs without extractable text / unreadable: 3

Only approved `POLICY_RULE`/`VERIFICATION_PROCEDURE` chunks in the income-verification namespace are eligible for live retrieval. Public/legal/card/collateral files are research or legacy material and do not make the runtime corpus appear larger.

## Duplicate groups

- `26aa21a7c124`: `dataset/Income_analysis_agent/Goi-chi-tra-luong-up-web.pdf`, `dataset/Policy_agent/Goi-chi-tra-luong-up-web.pdf`
- `a827a169b346`: `dataset/document_extraction_agent/BAN-DIEU-KIEN-DIEU-KHOAN-MO-VA-SU-DUNG-DICH-VU-TKTT-TAI-SHB-1.pdf`, `dataset/Policy_agent/BAN-DIEU-KIEN-DIEU-KHOAN-MO-VA-SU-DUNG-DICH-VU-TKTT-TAI-SHB-1.pdf`

## PDFs requiring OCR/manual review

- `dataset/document_extraction_agent/TBTG-K’Bes-2058.pdf`
- `dataset/document_extraction_agent/Thông-báo-Thu-giữ-6919.pdf`
- `dataset/document_extraction_agent/Thông-báo-thu-giữ-TSBĐ-Nguyễn-Công-Sơn.pdf`
