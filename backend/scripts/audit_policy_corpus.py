"""Classify repository PDFs/Markdown and report duplicates/scanned sources."""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SEARCH_ROOTS = [ROOT / "dataset", ROOT / "backend" / "data" / "mock_policies"]
DIRECT_TERMS = ("income", "salary", "thu-nhap", "thu nhập", "chi-tra-luong", "xac-minh")
INDIRECT_TERMS = ("vay", "loan", "sao-ke", "tai-khoan", "hợp-đồng-lao-động")


def classify(path: Path) -> str:
    normalized = str(path).lower().replace("_", "-")
    if any(term in normalized for term in DIRECT_TERMS):
        return "DIRECT_INCOME_VERIFICATION"
    if any(term in normalized for term in INDIRECT_TERMS):
        return "INDIRECT_REFERENCE"
    return "UNRELATED_TO_RUNTIME_POLICY"


def has_pdf_text(path: Path) -> bool | None:
    if path.suffix.lower() != ".pdf":
        return None
    try:
        import fitz

        with fitz.open(path) as document:
            return any(page.get_text("text").strip() for page in document)
    except Exception:
        return False


def audit() -> tuple[list[dict[str, object]], dict[str, list[str]]]:
    rows: list[dict[str, object]] = []
    checksums: dict[str, list[str]] = defaultdict(list)
    for root in SEARCH_ROOTS:
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".pdf", ".md", ".txt", ".json"}:
                continue
            raw = path.read_bytes()
            checksum = hashlib.sha256(raw).hexdigest()
            relative = path.relative_to(ROOT).as_posix()
            checksums[checksum].append(relative)
            rows.append(
                {
                    "path": relative,
                    "classification": classify(path),
                    "checksum": checksum,
                    "pdf_has_text": has_pdf_text(path),
                }
            )
    duplicates = {checksum: paths for checksum, paths in checksums.items() if len(paths) > 1}
    return rows, duplicates


def markdown(rows: list[dict[str, object]], duplicates: dict[str, list[str]]) -> str:
    counts = Counter(str(row["classification"]) for row in rows)
    scanned = [str(row["path"]) for row in rows if row["pdf_has_text"] is False]
    lines = [
        "# Corpus audit",
        "",
        "Generated inventory for the hackathon MVP. Runtime policy retrieval does not index unrelated sources.",
        "",
        "## Summary",
        "",
        f"- Direct income-verification sources: {counts['DIRECT_INCOME_VERIFICATION']}",
        f"- Indirect references: {counts['INDIRECT_REFERENCE']}",
        f"- Unrelated to runtime policy: {counts['UNRELATED_TO_RUNTIME_POLICY']}",
        f"- Duplicate checksum groups: {len(duplicates)}",
        f"- PDFs without extractable text / unreadable: {len(scanned)}",
        "",
        "Only approved `POLICY_RULE`/`VERIFICATION_PROCEDURE` chunks in the income-verification namespace are eligible for live retrieval. Public/legal/card/collateral files are research or legacy material and do not make the runtime corpus appear larger.",
        "",
        "## Duplicate groups",
        "",
    ]
    if duplicates:
        for checksum, paths in sorted(duplicates.items()):
            lines.append(f"- `{checksum[:12]}`: " + ", ".join(f"`{path}`" for path in paths))
    else:
        lines.append("- None")
    lines.extend(["", "## PDFs requiring OCR/manual review", ""])
    lines.extend(f"- `{path}`" for path in scanned) if scanned else lines.append("- None")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "corpus-audit.md")
    args = parser.parse_args()
    records, duplicate_groups = audit()
    args.output.write_text(markdown(records, duplicate_groups), encoding="utf-8")
    print(f"Audited {len(records)} files; report: {args.output}")
