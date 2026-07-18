import { Badge } from "@/shared/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";
import { EmptyState } from "@/shared/components/ui/empty-state";
import type {
  AgentCitation,
  JsonValue,
  SharedBoard,
  SpecialistAssessment,
} from "@/shared/types/api";
import { agentLabel, workStatusLabel } from "@/shared/utils/formatters";
import { workStatusTone } from "@/shared/utils/status";

interface SharedBoardGridProps {
  board: SharedBoard;
  onCitationClick: (citation: AgentCitation) => void;
}

function summarizeAssessment(assessment: SpecialistAssessment): string | null {
  switch (assessment.agent_id) {
    case "CustomerRelationship":
      return assessment.business_model_summary || null;
    case "Credit":
      return assessment.cash_flow_viability || null;
    case "RiskManagement":
      return assessment.industry_risk_analysis || `Risk tier: ${assessment.risk_tier}`;
    case "Legal":
      return assessment.litigation_risk_summary || null;
    case "LegalCompliance":
      return assessment.litigation_risk_summary ?? null;
    case "CollateralAppraisal":
      return assessment.total_collateral_value > 0
        ? "Đã tổng hợp tài sản bảo đảm và tính toán tỷ lệ LTV."
        : null;
    case "Compliance":
      return `KYC: ${assessment.kyc_status} · AML: ${assessment.aml_risk_level}`;
  }
}

function displayJsonValue(value: JsonValue): string {
  if (value === null) return "—";
  if (typeof value === "boolean") return value ? "Có" : "Không";
  if (typeof value === "string" || typeof value === "number") return String(value);
  return JSON.stringify(value);
}

function AssessmentCard({
  assessment,
  onCitationClick,
}: {
  assessment: SpecialistAssessment;
  onCitationClick: (citation: AgentCitation) => void;
}) {
  const summary = assessment.rationale_summary ?? summarizeAssessment(assessment);
  const keyFindings = Object.entries(assessment.key_findings ?? {}).slice(0, 4);

  return (
    <article className="rounded-2xl border border-border bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-slate-900 text-xs font-black text-white">
            {assessment.agent_id.slice(0, 2).toUpperCase()}
          </span>
          <div>
            <h3 className="font-bold">{agentLabel(assessment.agent_id)}</h3>
            <p className="text-xs text-muted-foreground">Specialist Agent</p>
          </div>
        </div>
        <Badge tone={workStatusTone(assessment.status)} showDot>
          {workStatusLabel(assessment.status)}
        </Badge>
      </div>

      {summary ? (
        <p className="mt-4 text-sm leading-6 text-muted-foreground">{summary}</p>
      ) : null}

      {keyFindings.length > 0 ? (
        <dl className="mt-4 grid grid-cols-2 gap-2">
          {keyFindings.map(([key, value]) => (
            <div key={key} className="rounded-lg bg-slate-50 p-2.5">
              <dt className="truncate text-[11px] font-bold uppercase tracking-wide text-muted-foreground">
                {key.replaceAll("_", " ")}
              </dt>
              <dd className="mt-1 truncate text-sm font-bold">{displayJsonValue(value)}</dd>
            </div>
          ))}
        </dl>
      ) : null}

      {assessment.risk_flags.length > 0 ? (
        <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3">
          <p className="text-xs font-bold uppercase tracking-wide text-amber-900">
            Cờ rủi ro
          </p>
          <ul className="mt-2 space-y-1.5 text-sm text-amber-950">
            {assessment.risk_flags.map((flag) => (
              <li key={flag} className="flex gap-2">
                <span aria-hidden="true">•</span>
                <span>{flag}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {assessment.missing_data && assessment.missing_data.length > 0 ? (
        <div className="mt-4 rounded-xl border border-blue-200 bg-blue-50 p-3">
          <p className="text-xs font-bold uppercase tracking-wide text-blue-900">
            Dữ liệu cần bổ sung
          </p>
          <ul className="mt-2 space-y-2 text-sm text-blue-950">
            {assessment.missing_data.map((request) => (
              <li key={`${request.document_type}:${request.reason}`}>
                <span className="font-bold">{request.document_type}:</span>{" "}
                {request.reason}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="mt-4 flex items-center justify-between border-t border-border pt-3">
        <span className="text-xs font-semibold text-muted-foreground">
          {assessment.evidence.length} trích dẫn chính sách
        </span>
        {assessment.evidence.length > 0 ? (
          <button
            type="button"
            className="text-xs font-bold text-primary hover:underline"
            onClick={() => onCitationClick(assessment.evidence[0])}
          >
            Xem căn cứ
          </button>
        ) : null}
      </div>
    </article>
  );
}

export function SharedBoardGrid({ board, onCitationClick }: SharedBoardGridProps) {
  const tasks = Object.entries(board.task_breakdown);
  const outputs = Object.values(board.specialist_outputs);

  return (
    <Card>
      <CardHeader className="sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="eyebrow">Persistent collaboration state</p>
          <CardTitle>Shared Board</CardTitle>
        </div>
        <Badge tone={board.consensus_reached ? "success" : "purple"} showDot>
          {board.consensus_reached ? "Đã đồng thuận" : "Đang cộng tác"}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-6">
        {tasks.length > 0 ? (
          <div>
            <h3 className="mb-3 text-sm font-bold">Tiến độ nhiệm vụ</h3>
            <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
              {tasks.map(([taskId, task]) => (
                <div
                  key={taskId}
                  className="flex items-center justify-between gap-3 rounded-xl border border-border bg-slate-50 px-3 py-3"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-bold">
                      {task.description ?? taskId.replaceAll("_", " ")}
                    </p>
                    <p className="truncate text-xs text-muted-foreground">
                      {agentLabel(task.assigned_to)}
                    </p>
                  </div>
                  <Badge tone={workStatusTone(task.status)}>{workStatusLabel(task.status)}</Badge>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        <div>
          <h3 className="mb-3 text-sm font-bold">Kết quả chuyên gia</h3>
          {outputs.length === 0 ? (
            <EmptyState
              compact
              title="Các chuyên gia đang chuẩn bị"
              description="Kết quả có cấu trúc, cờ rủi ro và trích dẫn chính sách sẽ được đăng lên Shared Board."
            />
          ) : (
            <div className="grid gap-4 lg:grid-cols-2">
              {outputs.map((assessment) => (
                <AssessmentCard
                  key={assessment.agent_id}
                  assessment={assessment}
                  onCitationClick={onCitationClick}
                />
              ))}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
