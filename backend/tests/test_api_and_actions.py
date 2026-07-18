"""MVP API, human gate and action-executor contract tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app  # noqa: E402


class ApiAndActionTests(unittest.TestCase):
    def test_api_requires_underwriter_identity(self) -> None:
        client = TestClient(app)
        response = client.post(
            "/api/v1/applications/SYN-SHB-2026-0001/income-verification",
            json={},
        )
        self.assertEqual(response.status_code, 403)

    def test_api_runs_review_and_verified_actions(self) -> None:
        client = TestClient(app)
        headers = {"X-Role": "UNDERWRITER", "X-Reviewer-Id": "underwriter-001"}
        start = client.post(
            "/api/v1/applications/SYN-SHB-2026-0001/income-verification",
            json={},
            headers=headers,
        )
        self.assertEqual(start.status_code, 200)
        case_id = start.json()["case_id"]

        case = client.get(
            f"/api/v1/income-verifications/{case_id}",
            headers=headers,
        )
        self.assertEqual(case.status_code, 200)
        self.assertEqual(case.json()["workflow_state"], "HUMAN_REVIEW")
        selected = [
            action["action_id"]
            for action in case.json()["proposed_actions"]
            if action["permission"] == "HUMAN_REQUIRED"
        ]

        review = client.post(
            f"/api/v1/income-verifications/{case_id}/review",
            json={
                "outcome": "ACCEPT_ACTIONS",
                "reason": "Đã kiểm tra evidence và policy citation.",
                "approved_action_ids": selected,
            },
            headers=headers,
        )
        self.assertEqual(review.status_code, 200)
        self.assertEqual(review.json()["workflow_state"], "COMPLETED")

        completed = client.get(
            f"/api/v1/income-verifications/{case_id}",
            headers=headers,
        ).json()
        self.assertEqual(completed["workflow_state"], "COMPLETED")
        self.assertTrue(all(item["verified"] for item in completed["execution_results"]))
        self.assertEqual(len(completed["execution_results"]), 4)

        duplicate_review = client.post(
            f"/api/v1/income-verifications/{case_id}/review",
            json={
                "outcome": "ACCEPT_ACTIONS",
                "reason": "duplicate",
                "approved_action_ids": selected,
            },
            headers=headers,
        )
        self.assertEqual(duplicate_review.status_code, 409)

        audit = client.get(
            f"/api/v1/income-verifications/{case_id}/audit",
            headers=headers,
        )
        self.assertEqual(audit.status_code, 200)
        event_types = {event["event_type"] for event in audit.json()["audit_events"]}
        self.assertIn("HUMAN_REVIEW_RECORDED", event_types)
        self.assertIn("EXECUTION_VERIFIED", event_types)


if __name__ == "__main__":
    unittest.main()
