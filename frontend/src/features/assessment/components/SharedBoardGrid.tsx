import { Badge } from "@/shared/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";
import { EmptyState } from "@/shared/components/ui/empty-state";
import { IconMessageChallenge } from "@/shared/components/ui/icons";
import type {
  AgentCitation,
  DebateLog,
  JsonValue,
  SharedBoard,
  SpecialistAssessment,
} from "@/shared/types/api";
import {
  agentLabel,
  boolLabel,
  formatMoney,
  formatPercentage,
  formatRatio,
  kycStatusLabel,
  riskLevelLabel,
  workStatusLabel,
} from "@/shared/utils/formatters";
import { workStatusTone } from "@/shared/utils/status";

interface SharedBoardGridProps {
  board: SharedBoard;
  onCitationClick: (citation: AgentCitation) => void;
  currency?: string;
}

function asRecord(value: unknown): Record<string, JsonValue> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, JsonValue>)
    : {};
}

interface Fact {
  label: string;
  value: string;
}

function fact(label: string, value: string): Fact {
  return { label, value: value || "—" };
}

/** Human-readable key facts per specialist; every field is a known typed shape, never raw JSON. */
function assessmentFacts(assessment: SpecialistAssessment, currency: string): Fact[] {
  switch (assessment.agent_id) {
    case "CustomerRelationship": {
      const profile = asRecord(assessment.borrower_profile);
      const terms = asRecord(assessment.requested_terms);
      const facts: Fact[] = [];
      if (profile.industry) facts.push(fact("Ngành nghề", String(profile.industry)));
      if (profile.years_in_business != null) {
        facts.push(fact("Số năm hoạt động", String(profile.years_in_business)));
      }
      if (terms.maturity_months != null) {
        facts.push(fact("Kỳ hạn vay", `${terms.maturity_months} tháng`));
      }
      if (terms.annual_interest_rate != null) {
        facts.push(fact("Lãi suất đề xuất", formatPercentage(Number(terms.annual_interest_rate))));
      }
      return facts;
    }
    case "Credit": {
      const ratios = assessment.calculated_ratios;
      const facts: Fact[] = [];
      if (ratios?.dscr != null) facts.push(fact("DSCR", formatRatio(Number(ratios.dscr))));
      if (ratios?.current_ratio != null) {
        facts.push(fact("Current ratio", formatRatio(Number(ratios.current_ratio))));
      }
      if (ratios?.debt_to_equity != null) {
        facts.push(fact("Debt / Equity", formatRatio(Number(ratios.debt_to_equity))));
      }
      return facts;
    }
    case "RiskManagement": {
      const concentration = asRecord(assessment.concentration_limit_check);
      const facts: Fact[] = [fact("Xếp hạng rủi ro sơ bộ", riskLevelLabel(assessment.risk_tier))];
      if (concentration.within_limit != null) {
        facts.push(
          fact(
            "Giới hạn tập trung",
            boolLabel(Boolean(concentration.within_limit), "Trong hạn mức", "Vượt hạn mức"),
          ),
        );
      }
      if (concentration.proposed_exposure != null) {
        facts.push(fact("Dư nợ đề xuất", formatMoney(String(concentration.proposed_exposure), currency)));
      }
      if (concentration.policy_limit != null) {
        facts.push(fact("Hạn mức chính sách", formatMoney(String(concentration.policy_limit), currency)));
      }
      return facts;
    }
    case "LegalCompliance": {
      const legal = asRecord(assessment.legal);
      const compliance = asRecord(assessment.compliance);
      const facts: Fact[] = [];
      if (legal.corporate_governance_valid != null) {
        facts.push(
          fact("Hồ sơ pháp lý DN", boolLabel(Boolean(legal.corporate_governance_valid), "Hợp lệ", "Không hợp lệ")),
        );
      }
      if (legal.unresolved_litigation != null) {
        facts.push(
          fact("Tranh chấp chưa xử lý", boolLabel(Boolean(legal.unresolved_litigation), "Có", "Không")),
        );
      }
      if (compliance.kyc_status) facts.push(fact("KYC", kycStatusLabel(String(compliance.kyc_status))));
      if (compliance.aml_risk_level) {
        facts.push(fact("Rủi ro AML", riskLevelLabel(String(compliance.aml_risk_level))));
      }
      if (compliance.sanctions_check_passed != null) {
        facts.push(
          fact("Rà soát cấm vận", boolLabel(Boolean(compliance.sanctions_check_passed), "Đạt", "Không đạt")),
        );
      }
      return facts;
    }
    case "CollateralAppraisal": {
      const facts: Fact[] = [];
      if (assessment.total_eligible_value != null) {
        facts.push(fact("Giá trị TSBĐ hợp lệ", formatMoney(assessment.total_eligible_value, currency)));
      }
      if (assessment.computed_ltv_ratio != null) {
        facts.push(fact("LTV", formatPercentage(Number(assessment.computed_ltv_ratio))));
      }
      return facts;
    }
    default:
      return [];
  }
}

function AssessmentCard({
  assessment,
  onCitationClick,
  debates,
  currency,
}: {
  assessment: SpecialistAssessment;
  onCitationClick: (citation: AgentCitation) => void;
  debates: readonly DebateLog[];
  currency: string;
}) {
  const summary = assessment.rationale_summary || null;
  const keyFindings = assessmentFacts(assessment, currency).slice(0, 4);
  const targetedDebates = debates.filter((item) => item.issue.target_agent === assessment.agent_id);
  const openIssues = targetedDebates.filter((item) => item.status === "OPEN");
  const resolvedCount = targetedDebates.length - openIssues.length;

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
          {keyFindings.map((item) => (
            <div key={item.label} className="rounded-lg bg-slate-50 p-2.5">
              <dt className="truncate text-[11px] font-bold uppercase tracking-wide text-muted-foreground">
                {item.label}
              </dt>
              <dd className="mt-1 truncate text-sm font-bold">{item.value}</dd>
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
              <li key={flag.code} className="flex gap-2">
                <span aria-hidden="true">•</span>
                <span><strong>{flag.severity}:</strong> {flag.summary}</span>
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
              <li key={request.code}>
                <span className="font-bold">{request.description}</span>
                {request.requested_document_types.length > 0 ? ` · ${request.requested_document_types.join(", ")}` : ""}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {targetedDebates.length > 0 ? (
        <div
          className={`mt-4 rounded-xl border p-3 ${
            openIssues.length > 0 ? "border-amber-300 bg-amber-50/70" : "border-emerald-200 bg-emerald-50/70"
          }`}
        >
          <p className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-foreground">
            <IconMessageChallenge className="h-3.5 w-3.5" />
            Phản biện từ Reviewer
          </p>
          {openIssues.length > 0 ? (
            <ul className="mt-2 space-y-1.5 text-sm text-amber-950">
              {openIssues.map((issue) => (
                <li key={issue.issue.code}>{issue.issue.description}</li>
              ))}
            </ul>
          ) : (
            <p className="mt-1.5 text-sm text-emerald-900">
              Đã giải quyết {resolvedCount} phản biện trước đó.
            </p>
          )}
        </div>
      ) : null}

      <div className="mt-4 flex items-center justify-between border-t border-border pt-3">
        <span className="text-xs font-semibold text-muted-foreground">
          {assessment.policy_citations.length} trích dẫn chính sách
        </span>
        {assessment.policy_citations.length > 0 ? (
          <button
            type="button"
            className="text-xs font-bold text-primary hover:underline"
            onClick={() => onCitationClick(assessment.policy_citations[0])}
          >
            Xem căn cứ
          </button>
        ) : null}
      </div>
    </article>
  );
}

export function SharedBoardGrid({ board, onCitationClick, currency = "VND" }: SharedBoardGridProps) {
  const tasks = Object.entries(board.tasks);
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
                      {task.detail || taskId.replaceAll("_", " ")}
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
                  debates={board.debate_log}
                  currency={currency}
                />
              ))}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
