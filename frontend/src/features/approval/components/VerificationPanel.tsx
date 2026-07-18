"use client";

import { useMemo, useState, type FormEvent } from "react";

import { useApproveAndExecute } from "@/features/approval/hooks/useApproveAndExecute";
import { Alert } from "@/shared/components/ui/alert";
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";
import { Dialog } from "@/shared/components/ui/dialog";
import type {
  ApprovalDecision,
  ApprovalRecord,
  CaseStatus,
  DecisionRequest,
} from "@/shared/types/api";
import { decisionLabel, formatDateTime } from "@/shared/utils/formatters";
import { decisionTone } from "@/shared/utils/status";

interface VerificationPanelProps {
  caseId: string;
  caseStatus: CaseStatus;
  existingApproval?: ApprovalRecord | null;
  consensusReached: boolean;
  onStateChanged: () => void;
}

const DECISION_OPTIONS: ReadonlyArray<{
  value: ApprovalDecision;
  title: string;
  description: string;
}> = [
  {
    value: "APPROVED",
    title: "Phê duyệt",
    description: "Cho phép chuyển sang bước vận hành sau một xác nhận riêng biệt.",
  },
  {
    value: "REVISION_REQUESTED",
    title: "Yêu cầu chỉnh sửa",
    description: "Trả hồ sơ về luồng bổ sung hoặc đánh giá lại với phản hồi cụ thể.",
  },
  {
    value: "REJECTED",
    title: "Từ chối",
    description: "Kết thúc hồ sơ tại cổng kiểm soát của chuyên viên.",
  },
];

export function VerificationPanel({
  caseId,
  caseStatus,
  existingApproval,
  consensusReached,
  onStateChanged,
}: VerificationPanelProps) {
  const workflow = useApproveAndExecute(caseId);
  const [decision, setDecision] = useState<ApprovalDecision | null>(null);
  const [feedback, setFeedback] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const approval = workflow.approval ?? existingApproval ?? null;
  const canDecide = caseStatus === "TIER3_PENDING_REVIEW" && consensusReached && !approval;
  const isApproved = approval?.decision === "APPROVED" || caseStatus === "APPROVED";

  const gateMessage = useMemo(() => {
    if (approval) return null;
    if (!consensusReached) return "Reviewer Agent chưa xác nhận đồng thuận.";
    if (caseStatus !== "TIER3_PENDING_REVIEW") {
      return "Hồ sơ chưa ở trạng thái chờ chuyên viên phê duyệt.";
    }
    return null;
  }, [approval, caseStatus, consensusReached]);

  const prepareDecision = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!decision) {
      setValidationError("Vui lòng chọn một quyết định.");
      return;
    }
    if (decision === "REVISION_REQUESTED" && feedback.trim().length < 5) {
      setValidationError("Vui lòng nhập phản hồi chỉnh sửa cụ thể.");
      return;
    }
    setValidationError(null);
    setConfirmOpen(true);
  };

  const confirmDecision = async () => {
    if (!decision) return;
    const input: DecisionRequest = {
      decision,
      feedback: feedback.trim() || null,
    };
    try {
      await workflow.decide(input);
      setConfirmOpen(false);
      onStateChanged();
    } catch {
      setConfirmOpen(false);
    }
  };

  const handleExecute = async () => {
    try {
      await workflow.execute();
      onStateChanged();
    } catch {
      // A user-safe error is rendered below.
    }
  };

  return (
    <Card className="overflow-hidden border-slate-900/10">
      <CardHeader className="bg-slate-950 text-white">
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-blue-300">
          Tier 3 · Human verification
        </p>
        <CardTitle className="text-white">Quyết định của chuyên viên</CardTitle>
        <p className="text-sm leading-6 text-slate-300">
          AI chỉ hỗ trợ phân tích. Không có thao tác vận hành nào được chạy trước quyết định của con người.
        </p>
      </CardHeader>
      <CardContent className="pt-6">
        {workflow.error ? (
          <Alert tone="danger" className="mb-4">
            {workflow.error}
          </Alert>
        ) : null}

        {approval ? (
          <div className="rounded-2xl border border-border bg-slate-50 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">
                  Quyết định đã ghi nhận
                </p>
                <p className="mt-1 text-sm font-semibold">
                  {approval.verified_by} · {formatDateTime(approval.decided_at)}
                </p>
              </div>
              <Badge tone={decisionTone(approval.decision)} showDot>
                {decisionLabel(approval.decision)}
              </Badge>
            </div>
            {approval.feedback ? (
              <p className="mt-3 border-t border-border pt-3 text-sm leading-6 text-muted-foreground">
                {approval.feedback}
              </p>
            ) : null}
          </div>
        ) : (
          <form onSubmit={prepareDecision}>
            {gateMessage ? (
              <Alert tone="warning" className="mb-4">
                {gateMessage}
              </Alert>
            ) : null}
            <fieldset disabled={!canDecide || workflow.isSubmittingDecision}>
              <legend className="form-label">Chọn quyết định</legend>
              <div className="grid gap-3">
                {DECISION_OPTIONS.map((option) => (
                  <label
                    key={option.value}
                    className={`cursor-pointer rounded-xl border p-4 transition ${
                      decision === option.value
                        ? "border-primary bg-primary/5 ring-2 ring-primary/10"
                        : "border-border hover:border-primary/30"
                    }`}
                  >
                    <span className="flex items-start gap-3">
                      <input
                        className="mt-1 h-4 w-4 accent-primary"
                        type="radio"
                        name="decision"
                        value={option.value}
                        checked={decision === option.value}
                        onChange={() => setDecision(option.value)}
                      />
                      <span>
                        <span className="block text-sm font-bold">{option.title}</span>
                        <span className="mt-1 block text-xs leading-5 text-muted-foreground">
                          {option.description}
                        </span>
                      </span>
                    </span>
                  </label>
                ))}
              </div>

              <div className="mt-4">
                <label htmlFor="decision-feedback" className="form-label">
                  Phản hồi {decision === "REVISION_REQUESTED" ? "(bắt buộc)" : "(tùy chọn)"}
                </label>
                <textarea
                  id="decision-feedback"
                  className="form-input min-h-24 resize-y py-3"
                  value={feedback}
                  placeholder="Ghi rõ căn cứ hoặc nội dung cần bổ sung…"
                  onChange={(event) => setFeedback(event.target.value)}
                />
              </div>
            </fieldset>

            {validationError ? (
              <p role="alert" className="mt-3 text-sm font-semibold text-danger">
                {validationError}
              </p>
            ) : null}

            <div className="mt-4 flex items-center justify-between gap-3">
              <p className="text-xs text-muted-foreground">
                Chuyên viên: <span className="font-bold">{workflow.officerId}</span>
              </p>
              <Button type="submit" disabled={!canDecide}>
                Xem lại & xác nhận
              </Button>
            </div>
          </form>
        )}

        {isApproved ? (
          <div className="mt-6 border-t border-border pt-6">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="font-bold">Tác vụ vận hành sau phê duyệt</p>
                <p className="mt-1 text-sm leading-5 text-muted-foreground">
                  Tạo bản nháp thỏa thuận và payload onboarding qua Mock SHB API.
                </p>
              </div>
              <Button
                variant="success"
                isLoading={workflow.isExecuting}
                disabled={workflow.execution?.status === "COMPLETED"}
                onClick={handleExecute}
              >
                {workflow.execution?.status === "COMPLETED"
                  ? "Đã thực thi"
                  : "Thực thi vận hành"}
              </Button>
            </div>

            {workflow.execution ? (
              <Alert
                tone={workflow.execution.status === "COMPLETED" ? "success" : "info"}
                className="mt-4"
                title={`Operations: ${workflow.execution.status}`}
              >
                <p>Audit trace: {workflow.execution.audit_trace_id || "Đang tạo"}</p>
                {workflow.execution.generated_agreement_url ? (
                  <a
                    className="mt-2 inline-block font-bold underline"
                    href={workflow.execution.generated_agreement_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Mở Draft Credit Agreement ↗
                  </a>
                ) : null}
              </Alert>
            ) : null}
          </div>
        ) : null}
      </CardContent>

      <Dialog
        open={confirmOpen}
        onClose={workflow.isSubmittingDecision ? () => undefined : () => setConfirmOpen(false)}
        title="Xác nhận quyết định"
        description="Hành động sẽ được ghi vào audit log và thay đổi trạng thái hồ sơ."
        footer={
          <>
            <Button
              variant="ghost"
              disabled={workflow.isSubmittingDecision}
              onClick={() => setConfirmOpen(false)}
            >
              Quay lại
            </Button>
            <Button
              variant={decision === "APPROVED" ? "success" : decision === "REJECTED" ? "danger" : "primary"}
              isLoading={workflow.isSubmittingDecision}
              onClick={confirmDecision}
            >
              Xác nhận {decision ? decisionLabel(decision).toLocaleLowerCase("vi") : ""}
            </Button>
          </>
        }
      >
        <Alert tone={decision === "APPROVED" ? "success" : "warning"}>
          Bạn đang chọn <strong>{decision ? decisionLabel(decision) : "—"}</strong> cho hồ sơ này.
          {decision === "APPROVED"
            ? " Operations vẫn cần một thao tác kích hoạt riêng sau đó."
            : ""}
        </Alert>
      </Dialog>
    </Card>
  );
}
