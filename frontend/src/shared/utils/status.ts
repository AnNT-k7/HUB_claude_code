import type { BadgeTone } from "@/shared/components/ui/badge";
import type {
  ApprovalDecision,
  AssessmentStatus,
  CaseStatus,
  TaskStatus,
} from "@/shared/types/api";

export function caseStatusTone(status: CaseStatus): BadgeTone {
  switch (status) {
    case "APPROVED":
    case "COMPLETED":
      return "success";
    case "REJECTED":
    case "FAILED":
      return "danger";
    case "AWAITING_DOCS":
    case "REVISION_REQUESTED":
      return "warning";
    case "TIER1_PLANNING":
    case "TIER2_DEBATING":
      return "purple";
    case "TIER3_PENDING_REVIEW":
      return "info";
    default:
      return "neutral";
  }
}

export function workStatusTone(
  status: TaskStatus | AssessmentStatus,
): BadgeTone {
  switch (status) {
    case "SUCCESS":
    case "COMPLETED":
      return "success";
    case "ERROR":
      return "danger";
    case "REQUIRES_MORE_DATA":
    case "MANUAL_REVIEW":
    case "BLOCKED":
      return "warning";
    case "RUNNING":
    case "REFINING":
      return "purple";
    default:
      return "neutral";
  }
}

export function decisionTone(decision: ApprovalDecision): BadgeTone {
  if (decision === "APPROVED") return "success";
  if (decision === "REJECTED") return "danger";
  return "warning";
}
