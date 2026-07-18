import { Badge } from "@/shared/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";
import { EmptyState } from "@/shared/components/ui/empty-state";
import type { DebateLog } from "@/shared/types/api";
import { agentLabel, formatDateTime } from "@/shared/utils/formatters";

interface DebateLogViewerProps {
  debates: readonly DebateLog[];
  currentRound?: number;
  maxRounds?: number;
}

export function DebateLogViewer({
  debates,
  currentRound = 0,
  maxRounds = 3,
}: DebateLogViewerProps) {
  const orderedDebates = [...debates].sort(
    (left, right) => left.round_number - right.round_number,
  );

  return (
    <Card>
      <CardHeader className="sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="eyebrow">Quality challenge</p>
          <CardTitle>Nhật ký phản biện</CardTitle>
        </div>
        <Badge tone={debates.length > 0 ? "purple" : "neutral"}>
          Vòng {currentRound}/{maxRounds}
        </Badge>
      </CardHeader>
      <CardContent>
        {orderedDebates.length === 0 ? (
          <EmptyState
            compact
            title="Chưa phát sinh phản biện"
            description="Reviewer Agent sẽ ghi lại mâu thuẫn, yêu cầu hiệu chỉnh và cách chuyên gia giải quyết tại đây."
          />
        ) : (
          <ol className="relative ml-2 space-y-5 border-l border-slate-200">
            {orderedDebates.map((debate) => (
              <li key={debate.id} className="relative pl-6">
                <span className="absolute -left-[7px] top-1.5 h-3 w-3 rounded-full bg-violet-500 ring-4 ring-violet-50" />
                <div className="rounded-xl border border-border bg-slate-50/70 p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone="purple">Vòng {debate.round_number}</Badge>
                    <span className="text-xs font-semibold text-muted-foreground">
                      {agentLabel(debate.critic_agent)} → {agentLabel(debate.target_agent)}
                    </span>
                    <span className="ml-auto text-xs text-muted-foreground">
                      {formatDateTime(debate.logged_at)}
                    </span>
                  </div>
                  <div className="mt-3">
                    <p className="text-xs font-bold uppercase tracking-wide text-danger">
                      Vấn đề phát hiện
                    </p>
                    <p className="mt-1 text-sm leading-6 text-foreground">
                      {debate.error_identified}
                    </p>
                  </div>
                  <div className="mt-3 border-t border-border pt-3">
                    <p className="text-xs font-bold uppercase tracking-wide text-success">
                      Phản hồi / khắc phục
                    </p>
                    <p className="mt-1 text-sm leading-6 text-muted-foreground">
                      {debate.resolution_applied ?? "Đang chờ chuyên gia phản hồi."}
                    </p>
                  </div>
                </div>
              </li>
            ))}
          </ol>
        )}
      </CardContent>
    </Card>
  );
}
