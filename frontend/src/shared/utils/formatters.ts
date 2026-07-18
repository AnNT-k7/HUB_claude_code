import type {
  AgentId,
  ApprovalDecision,
  AssessmentStatus,
  CaseStatus,
  TaskStatus,
} from "@/shared/types/api";

const DEFAULT_LOCALE = "vi-VN";

export function formatMoney(
  amount: string | number,
  currency = "VND",
): string {
  const numericAmount = typeof amount === "number" ? amount : Number(amount);
  if (!Number.isFinite(numericAmount)) {
    return `${amount} ${currency}`;
  }
  return new Intl.NumberFormat(DEFAULT_LOCALE, {
    style: "currency",
    currency,
    maximumFractionDigits: currency === "VND" ? 0 : 2,
  }).format(numericAmount);
}

export function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(DEFAULT_LOCALE, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function formatFileSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) {
    return "—";
  }
  if (bytes < 1_024) {
    return `${bytes} B`;
  }
  const units = ["KB", "MB", "GB", "TB"];
  let value = bytes / 1_024;
  let unitIndex = 0;
  while (value >= 1_024 && unitIndex < units.length - 1) {
    value /= 1_024;
    unitIndex += 1;
  }
  return `${value.toFixed(value >= 10 ? 1 : 2)} ${units[unitIndex]}`;
}

export function formatRatio(value: number): string {
  return Number.isFinite(value) ? `${value.toFixed(2)}x` : "—";
}

export function formatPercentage(value: number): string {
  if (!Number.isFinite(value)) {
    return "—";
  }
  const normalized = Math.abs(value) <= 1 ? value * 100 : value;
  return `${normalized.toFixed(1)}%`;
}

const CASE_STATUS_LABELS: Record<CaseStatus, string> = {
  INGESTED: "Đã tiếp nhận",
  TIER1_PLANNING: "Đang lập kế hoạch",
  AWAITING_DOCS: "Chờ bổ sung hồ sơ",
  TIER2_DEBATING: "Đang thẩm định",
  TIER3_PENDING_REVIEW: "Chờ phê duyệt",
  REVISION_REQUESTED: "Yêu cầu chỉnh sửa",
  APPROVED: "Đã phê duyệt",
  REJECTED: "Đã từ chối",
  COMPLETED: "Hoàn tất",
};

export function caseStatusLabel(status: CaseStatus): string {
  return CASE_STATUS_LABELS[status] ?? status;
}

const AGENT_LABELS: Record<AgentId, string> = {
  BankingOrchestrator: "Điều phối tín dụng",
  CustomerRelationship: "Quan hệ khách hàng",
  Credit: "Tín dụng",
  RiskManagement: "Quản trị rủi ro",
  LegalCompliance: "Pháp lý & Tuân thủ",
  CollateralAppraisal: "Thẩm định tài sản",
  ReviewerAgent: "Reviewer",
  BankingOperations: "Vận hành ngân hàng",
};

export function agentLabel(agentId: AgentId | string): string {
  return AGENT_LABELS[agentId as AgentId] ?? agentId;
}

const WORK_STATUS_LABELS: Record<TaskStatus | AssessmentStatus, string> = {
  PENDING: "Chờ xử lý",
  RUNNING: "Đang xử lý",
  COMPLETED: "Hoàn thành",
  REFINING: "Đang tinh chỉnh",
  BLOCKED: "Bị chặn",
  SUCCESS: "Hoàn thành",
  REQUIRES_MORE_DATA: "Cần thêm dữ liệu",
  MANUAL_REVIEW: "Cần kiểm tra thủ công",
  ERROR: "Có lỗi",
};

export function workStatusLabel(
  status: TaskStatus | AssessmentStatus,
): string {
  return WORK_STATUS_LABELS[status] ?? status;
}

const RUNTIME_STATUS_LABELS: Record<string, string> = {
  ...WORK_STATUS_LABELS,
  QUEUED: "Đang xếp hàng",
  STOP_REQUESTED: "Yêu cầu dừng",
  PAUSED: "Tạm dừng",
  FAILED: "Thất bại",
  CHALLENGE: "Đang phản biện",
};

export function runtimeStatusLabel(status: string): string {
  return RUNTIME_STATUS_LABELS[status] ?? status;
}

const KYC_STATUS_LABELS: Record<string, string> = {
  VERIFIED: "Đã xác minh",
  UNVERIFIED: "Chưa xác minh",
  FAILED: "Không đạt",
  UNKNOWN: "Chưa xác định",
};

export function kycStatusLabel(status: string): string {
  return KYC_STATUS_LABELS[status] ?? status;
}

const RISK_LEVEL_LABELS: Record<string, string> = {
  LOW: "Thấp",
  MEDIUM: "Trung bình",
  HIGH: "Cao",
  UNASSIGNED: "Chưa xếp hạng",
  UNKNOWN: "Chưa xác định",
};

export function riskLevelLabel(level: string): string {
  return RISK_LEVEL_LABELS[level] ?? level;
}

export function boolLabel(value: boolean | null | undefined, whenTrue: string, whenFalse: string): string {
  if (value === null || value === undefined) return "—";
  return value ? whenTrue : whenFalse;
}

const DECISION_LABELS: Record<ApprovalDecision, string> = {
  APPROVED: "Phê duyệt",
  REJECTED: "Từ chối",
  REVISION_REQUESTED: "Yêu cầu chỉnh sửa",
};

export function decisionLabel(decision: ApprovalDecision): string {
  return DECISION_LABELS[decision];
}
