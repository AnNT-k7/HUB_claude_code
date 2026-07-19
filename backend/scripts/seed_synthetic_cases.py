"""Seed the case-management database with the 20 synthetic ground-truth
cases (see scripts/generate_synthetic_cases.py), through the real
CaseService — the same code path the API uses.

Usage (from backend/):
    python scripts/seed_synthetic_cases.py            # create + upload only
    python scripts/seed_synthetic_cases.py --run       # also run the pipeline
    python scripts/seed_synthetic_cases.py --run --only case_08_volatile_income
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

SYNTHETIC_CASES_ROOT = BACKEND_ROOT / "data" / "synthetic_cases"


async def seed(*, run_pipeline: bool, only: str | None) -> None:
    from app.services.case_service import get_case_service

    service = get_case_service()
    print(f"LLM mode: {service.llm.mode_label}")
    print(f"RAG mode: {service.rag_mode}")

    bundle_dirs = sorted(SYNTHETIC_CASES_ROOT.glob("case_*"))
    if only:
        bundle_dirs = [d for d in bundle_dirs if d.name == only]
        if not bundle_dirs:
            raise SystemExit(f"No bundle named {only!r} under {SYNTHETIC_CASES_ROOT}")

    for bundle_dir in bundle_dirs:
        ground_truth = json.loads((bundle_dir / "ground_truth.json").read_text(encoding="utf-8"))
        context = await service.create_case(
            customer_name=ground_truth["customer_name"],
            customer_code=f"SYN-{ground_truth['case_no']:02d}",
            employer=ground_truth["employer"],
            requested_amount=None,
            loan_term_months=None,
        )
        for file_name in ground_truth["documents"]:
            content = (bundle_dir / file_name).read_bytes()
            await service.add_document(
                context.case_id, file_name=file_name, content_type="text/plain", raw_bytes=content
            )
        print(f"[seeded] {bundle_dir.name} -> case_id={context.case_id}")

        if run_pipeline:
            result = await service.run_pipeline(context.case_id)
            match = "OK" if _matches(result.workflow_state.value, ground_truth["expected_status"]) else "MISMATCH"
            print(
                f"          workflow_state={result.workflow_state.value} "
                f"expected={ground_truth['expected_status']} [{match}]"
            )


def _matches(workflow_state: str, expected_status: str) -> bool:
    mapping = {
        "verified": {"HUMAN_REVIEW"},
        "insufficient": {"AWAITING_DOCUMENTS", "MANUAL_REVIEW_REQUIRED"},
        "inconsistent": {"HUMAN_REVIEW", "MANUAL_REVIEW_REQUIRED"},
        "manual_review": {"MANUAL_REVIEW_REQUIRED"},
    }
    return workflow_state in mapping.get(expected_status, set())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Also run the pipeline for each seeded case.")
    parser.add_argument("--only", default=None, help="Seed a single bundle directory name.")
    args = parser.parse_args()
    asyncio.run(seed(run_pipeline=args.run, only=args.only))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
