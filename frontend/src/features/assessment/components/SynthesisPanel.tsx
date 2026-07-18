import { Alert } from "@/shared/components/ui/alert";
import { Badge } from "@/shared/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";
import { IconAlertTriangle, IconCheckCircle } from "@/shared/components/ui/icons";
import type { SharedBoard } from "@/shared/types/api";

interface SynthesisPanelProps {
  board: SharedBoard;
}

export function SynthesisPanel({ board }: SynthesisPanelProps) {
  const synthesis = board.final_summary;

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
        <Badge tone={synthesis.status === "AWAITING_DOCS" ? "warning" : synthesis.overall_risk_level === "LOW" ? "success" : "info"}>
          {synthesis.status === "AWAITING_DOCS" ? "Cần thêm dữ liệu" : `Rủi ro ${synthesis.overall_risk_level ?? "chưa xác định"}`}
        </Badge>
      </CardHeader>
      <CardContent>
        <p className="text-sm leading-7 text-foreground">{synthesis.executive_summary ?? synthesis.message}</p>
        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
            <h3 className="text-sm font-bold text-emerald-900">Điểm mạnh</h3>
            {(synthesis.key_strengths?.length ?? 0) > 0 ? (
              <ul className="mt-2 space-y-2 text-sm text-emerald-950">
                {synthesis.key_strengths?.map((item) => (
                  <li key={item} className="flex gap-2">
                    <IconCheckCircle className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-sm text-emerald-800">Chưa ghi nhận.</p>
            )}
          </div>
          <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
            <h3 className="text-sm font-bold text-amber-950">Rủi ro trọng yếu</h3>
            {(synthesis.key_risks?.length ?? 0) > 0 ? (
              <ul className="mt-2 space-y-2 text-sm text-amber-950">
                {synthesis.key_risks?.map((item) => (
                  <li key={item} className="flex gap-2">
                    <IconAlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-sm text-amber-800">Không có cờ rủi ro trọng yếu.</p>
            )}
          </div>
        </div>
        {synthesis.officer_attention_items && synthesis.officer_attention_items.length > 0 ? (
          <div className="mt-4 rounded-xl border border-blue-200 bg-blue-50 p-4">
            <h3 className="text-sm font-bold text-blue-950">Điều kiện đề xuất</h3>
            <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-blue-950">
              {synthesis.officer_attention_items.map((condition) => (
                <li key={condition}>{condition}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
