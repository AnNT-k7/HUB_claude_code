import { Alert } from "@/shared/components/ui/alert";
import { Badge } from "@/shared/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";
import type { SharedBoard } from "@/shared/types/api";

interface SynthesisPanelProps {
  board: SharedBoard;
}

export function SynthesisPanel({ board }: SynthesisPanelProps) {
  const synthesis = board.final_synthesis;

  if (!synthesis) {
    if (!board.consensus_reached) return null;
    return (
      <Alert tone="info" title="Đang tổng hợp báo cáo">
        Các chuyên gia đã đồng thuận. Banking Orchestrator đang chuẩn bị bản đánh giá cho chuyên viên.
      </Alert>
    );
  }

  return (
    <Card className="border-primary/20 bg-gradient-to-br from-white to-blue-50/60">
      <CardHeader className="sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="eyebrow">Tier 1 synthesis</p>
          <CardTitle>Đánh giá tổng hợp</CardTitle>
        </div>
        <Badge
          tone={
            synthesis.recommendation === "PROCEED_TO_REVIEW"
              ? "success"
              : synthesis.recommendation === "REQUIRES_MORE_DATA"
                ? "warning"
                : "info"
          }
        >
          {synthesis.recommendation === "PROCEED_TO_REVIEW"
            ? "Sẵn sàng kiểm tra"
            : synthesis.recommendation === "REQUIRES_MORE_DATA"
              ? "Cần thêm dữ liệu"
              : "Cần kiểm tra thủ công"}
        </Badge>
      </CardHeader>
      <CardContent>
        <p className="text-sm leading-7 text-foreground">{synthesis.executive_summary}</p>
        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
            <h3 className="text-sm font-bold text-emerald-900">Điểm mạnh</h3>
            {synthesis.key_strengths.length > 0 ? (
              <ul className="mt-2 space-y-2 text-sm text-emerald-950">
                {synthesis.key_strengths.map((item) => (
                  <li key={item} className="flex gap-2">
                    <span>✓</span><span>{item}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-sm text-emerald-800">Chưa ghi nhận.</p>
            )}
          </div>
          <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
            <h3 className="text-sm font-bold text-amber-950">Rủi ro trọng yếu</h3>
            {synthesis.key_risks.length > 0 ? (
              <ul className="mt-2 space-y-2 text-sm text-amber-950">
                {synthesis.key_risks.map((item) => (
                  <li key={item} className="flex gap-2">
                    <span>!</span><span>{item}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-sm text-amber-800">Không có cờ rủi ro trọng yếu.</p>
            )}
          </div>
        </div>
        {synthesis.conditions && synthesis.conditions.length > 0 ? (
          <div className="mt-4 rounded-xl border border-blue-200 bg-blue-50 p-4">
            <h3 className="text-sm font-bold text-blue-950">Điều kiện đề xuất</h3>
            <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-blue-950">
              {synthesis.conditions.map((condition) => (
                <li key={condition}>{condition}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
