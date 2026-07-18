"use client";

import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { IconArrowDown, IconClock, IconGavel, IconUsers } from "@/shared/components/ui/icons";
import type {
  AgentId,
  AssessmentEvent,
  AssessmentRuntime,
  SharedBoard,
} from "@/shared/types/api";
import { agentLabel, formatDateTime, runtimeStatusLabel } from "@/shared/utils/formatters";
import { runtimeStatusTone } from "@/shared/utils/status";

const STAGES = [
  ["plan", "Lập kế hoạch"],
  ["rag", "Truy xuất RAG"],
  ["specialists", "Chuyên gia"],
  ["review", "Phản biện"],
  ["synthesize", "Tổng hợp"],
  ["completed", "Human gate"],
] as const;

const ACTIVE_RUNS = new Set(["QUEUED", "RUNNING", "STOP_REQUESTED"]);

function agentStatus(
  agentId: AgentId,
  events: AssessmentEvent[],
  board?: SharedBoard | null,
) {
  const latest = [...events].reverse().find((item) => item.agent_id === agentId);
  const output = board?.specialist_outputs[agentId];
  return latest?.status ?? output?.status ?? "PENDING";
}

interface Props {
  runtime: AssessmentRuntime;
  board?: SharedBoard | null;
  isLive: boolean;
  isLoading: boolean;
  onStop: () => void;
  onResume: () => void;
  isStopping: boolean;
  isResuming: boolean;
}

function PipelineNode({
  label,
  detail,
  status,
  challenged,
}: {
  label: string;
  detail?: string;
  status: string;
  challenged?: boolean;
}) {
  const tone = runtimeStatusTone(status);
  const running = status === "RUNNING" || status === "REFINING" || status === "CHALLENGE";
  return (
    <div
      className={`relative rounded-xl border bg-white px-3 py-2.5 transition-shadow ${
        running ? "border-primary/40 shadow-[0_0_0_4px_rgba(37,99,235,.08)]" : "border-border"
      } ${challenged ? "ring-2 ring-amber-300" : ""}`}
    >
      <div className="flex items-center justify-between gap-2">
        <p className="truncate text-sm font-bold text-foreground">{label}</p>
        {running ? (
          <span className="h-2 w-2 shrink-0 animate-pulse rounded-full bg-primary" />
        ) : null}
      </div>
      {detail ? <p className="mt-0.5 truncate text-xs text-muted-foreground">{detail}</p> : null}
      <Badge tone={tone} className="mt-2" showDot>
        {runtimeStatusLabel(status)}
      </Badge>
      {challenged ? (
        <p className="mt-1.5 text-[11px] font-semibold text-amber-700">
          Đang bị Reviewer phản biện
        </p>
      ) : null}
    </div>
  );
}

function StageConnector() {
  return (
    <div className="flex justify-center py-1 text-slate-300">
      <IconArrowDown className="h-4 w-4" />
    </div>
  );
}

function StageLabel({ eyebrow, title }: { eyebrow: string; title: string }) {
  return (
    <div className="mb-2">
      <p className="text-[11px] font-bold uppercase tracking-wide text-muted-foreground">
        {eyebrow}
      </p>
      <p className="text-sm font-bold text-foreground">{title}</p>
    </div>
  );
}

export function LiveAssessmentPanel({
  runtime,
  board,
  isLive,
  isLoading,
  onStop,
  onResume,
  isStopping,
  isResuming,
}: Props) {
  const run = runtime.run;
  if (isLoading && !run) return null;
  const activeStage = run?.current_stage ?? "queued";
  const activeIndex = STAGES.findIndex(([stage]) => stage === activeStage);
  const recentEvents = runtime.events.slice(-8).reverse();
  const canStop = run ? ACTIVE_RUNS.has(run.status) : false;
  const canResume = run?.status === "PAUSED" || run?.status === "FAILED";

  const openChallenges = (board?.debate_log ?? []).filter((item) => item.status === "OPEN");
  const challengedAgents = new Set(openChallenges.map((item) => item.issue.target_agent));

  const orchestratorStatus = (stage: string) => {
    if (!run) return "PENDING";
    if (activeStage === stage) return "RUNNING";
    const stageIndex = STAGES.findIndex(([value]) => value === stage);
    if (stageIndex >= 0 && activeIndex > stageIndex) return "COMPLETED";
    if (activeStage === "completed" && stage !== "completed") return "COMPLETED";
    return "PENDING";
  };

  const reviewerStatus = openChallenges.length > 0
    ? "CHALLENGE"
    : orchestratorStatus("review");

  return (
    <section className="overflow-hidden rounded-2xl border border-border bg-white shadow-card">
      <div className="border-b border-border bg-slate-50/70 px-5 py-4 sm:px-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary">
              <IconUsers className="h-5 w-5" />
            </span>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-black text-foreground">Bộ điều phối đa tác nhân</h2>
                <span className={`h-2 w-2 rounded-full ${isLive ? "animate-pulse bg-emerald-500" : "bg-slate-300"}`} />
              </div>
              <p className="text-xs text-muted-foreground">
                {run
                  ? `${runtimeStatusLabel(run.status)} · checkpoint ${run.checkpoint_stage}`
                  : "Chưa có lượt chạy"}
              </p>
            </div>
          </div>
          <div className="flex gap-2">
            {canStop ? (
              <Button variant="outline" size="sm" isLoading={isStopping} onClick={onStop}>
                Dừng an toàn
              </Button>
            ) : null}
            {canResume ? (
              <Button size="sm" isLoading={isResuming} onClick={onResume}>
                Tiếp tục từ checkpoint
              </Button>
            ) : null}
          </div>
        </div>
      </div>

      <div className="grid gap-6 p-5 sm:p-6 xl:grid-cols-[minmax(0,1fr)_300px]">
        <div>
          <ol className="space-y-0">
            <li>
              <StageLabel eyebrow="Bước 1" title="Điều phối viên lập kế hoạch" />
              <PipelineNode
                label="Banking Orchestrator"
                detail="Đọc hồ sơ, xác định trọng tâm phân tích"
                status={orchestratorStatus("plan")}
              />
            </li>

            <StageConnector />

            <li>
              <StageLabel eyebrow="Bước 2" title="Chuyên gia phân tích theo phụ thuộc" />
              <div className="space-y-2">
                <PipelineNode
                  label={agentLabel("CustomerRelationship")}
                  detail="Tiếp nhận hồ sơ (chạy trước)"
                  status={agentStatus("CustomerRelationship", runtime.events, board)}
                  challenged={challengedAgents.has("CustomerRelationship")}
                />
                <div className="pl-4 text-slate-300">
                  <IconArrowDown className="h-3.5 w-3.5" />
                </div>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                  <PipelineNode
                    label={agentLabel("Credit")}
                    detail="Chạy song song"
                    status={agentStatus("Credit", runtime.events, board)}
                    challenged={challengedAgents.has("Credit")}
                  />
                  <PipelineNode
                    label={agentLabel("LegalCompliance")}
                    detail="Chạy song song"
                    status={agentStatus("LegalCompliance", runtime.events, board)}
                    challenged={challengedAgents.has("LegalCompliance")}
                  />
                  <PipelineNode
                    label={agentLabel("CollateralAppraisal")}
                    detail="Chạy song song"
                    status={agentStatus("CollateralAppraisal", runtime.events, board)}
                    challenged={challengedAgents.has("CollateralAppraisal")}
                  />
                </div>
                <div className="pl-4 text-slate-300">
                  <IconArrowDown className="h-3.5 w-3.5" />
                </div>
                <PipelineNode
                  label={agentLabel("RiskManagement")}
                  detail="Tổng hợp rủi ro chéo (chạy sau cùng)"
                  status={agentStatus("RiskManagement", runtime.events, board)}
                  challenged={challengedAgents.has("RiskManagement")}
                />
              </div>
            </li>

            <StageConnector />

            <li>
              <StageLabel eyebrow="Bước 3" title="Reviewer kiểm tra chéo bằng chứng" />
              <div className="rounded-xl border border-border bg-white px-3 py-2.5">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <IconGavel className="h-4 w-4 text-muted-foreground" />
                    <p className="text-sm font-bold text-foreground">Reviewer Agent</p>
                  </div>
                  <Badge tone="purple">
                    Vòng {board?.current_debate_round ?? 0}/{board?.max_debate_rounds ?? 3}
                  </Badge>
                </div>
                <Badge tone={runtimeStatusTone(reviewerStatus)} className="mt-2" showDot>
                  {runtimeStatusLabel(reviewerStatus)}
                </Badge>
                {openChallenges.length > 0 ? (
                  <p className="mt-2 text-xs leading-5 text-amber-700">
                    Đang phản biện: {[...challengedAgents].map((agent) => agentLabel(agent)).join(", ")}
                  </p>
                ) : (
                  <p className="mt-2 text-xs text-muted-foreground">
                    Không có phản biện đang mở.
                  </p>
                )}
              </div>
            </li>

            <StageConnector />

            <li>
              <StageLabel eyebrow="Bước 4" title="Tổng hợp và bàn giao" />
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                <PipelineNode
                  label="Tổng hợp kết luận"
                  detail="Banking Orchestrator"
                  status={orchestratorStatus("synthesize")}
                />
                <div className="rounded-xl border border-dashed border-border bg-slate-50/70 px-3 py-2.5">
                  <p className="text-sm font-bold text-foreground">Chuyên viên xác minh</p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    Con người quyết định — xem mục xác minh bên dưới
                  </p>
                </div>
              </div>
            </li>
          </ol>

          <div className="mt-5 rounded-xl border border-blue-100 bg-blue-50/60 px-4 py-3 text-xs leading-5 text-blue-900">
            Dashboard chỉ hiển thị trạng thái vận hành, bằng chứng và kết quả có cấu trúc; không hiển thị chain-of-thought riêng tư của model.
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between">
            <p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">
              Nhật ký hoạt động
            </p>
            <span className="text-xs text-muted-foreground">{runtime.events.length} sự kiện</span>
          </div>
          <div className="mt-3 max-h-[520px] space-y-2.5 overflow-y-auto pr-1">
            {recentEvents.length ? recentEvents.map((event) => (
              <article key={event.id} className="rounded-xl border border-border bg-white p-3">
                <div className="flex items-start justify-between gap-2">
                  <p className="text-sm font-bold text-foreground">{event.title}</p>
                  <Badge tone={runtimeStatusTone(event.status)} className="shrink-0">
                    {runtimeStatusLabel(event.status)}
                  </Badge>
                </div>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">{event.message}</p>
                <div className="mt-2 flex items-center gap-1.5 text-[11px] text-muted-foreground">
                  <IconClock className="h-3 w-3" />
                  {formatDateTime(event.created_at)}
                </div>
              </article>
            )) : (
              <p className="rounded-xl border border-dashed border-border p-4 text-sm text-muted-foreground">
                Sự kiện sẽ xuất hiện ngay khi Orchestrator bắt đầu.
              </p>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
