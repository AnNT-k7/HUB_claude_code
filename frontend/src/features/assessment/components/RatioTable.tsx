import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";
import { EmptyState } from "@/shared/components/ui/empty-state";
import type { SharedBoard } from "@/shared/types/api";
import { formatMoney, formatPercentage, formatRatio } from "@/shared/utils/formatters";

interface RatioTableProps {
  board: SharedBoard;
  currency?: string;
}

interface MetricRow {
  label: string;
  value: string;
  note: string;
}

export function RatioTable({ board, currency = "VND" }: RatioTableProps) {
  const outputs = Object.values(board.specialist_outputs);
  const credit = outputs.find((output) => output.agent_id === "Credit");
  const collateral = outputs.find(
    (output) => output.agent_id === "CollateralAppraisal",
  );
  const rows: MetricRow[] = [];

  if (credit?.agent_id === "Credit") {
    const dscr = credit.calculated_ratios?.dscr;
    const currentRatio = credit.calculated_ratios?.current_ratio;
    const leverage = credit.calculated_ratios?.debt_to_equity;
    if (dscr != null) {
      rows.push({ label: "DSCR", value: formatRatio(Number(dscr)), note: "Khả năng trả nợ" });
    }
    if (currentRatio !== undefined) {
      rows.push({
        label: "Current Ratio",
        value: formatRatio(Number(currentRatio)),
        note: "Thanh khoản ngắn hạn",
      });
    }
    if (leverage !== undefined) {
      rows.push({
        label: "D/E",
        value: formatRatio(Number(leverage)),
        note: "Đòn bẩy tài chính",
      });
    }
  }

  if (collateral?.agent_id === "CollateralAppraisal") {
    if (collateral.computed_ltv_ratio != null) {
      rows.push({
        label: "LTV",
        value: formatPercentage(Number(collateral.computed_ltv_ratio)),
        note: "Tỷ lệ khoản vay / tài sản",
      });
    }
    if (Number(collateral.total_collateral_value ?? 0) > 0) {
      rows.push({
        label: "Giá trị tài sản",
        value: formatMoney(collateral.total_collateral_value ?? "0", currency),
        note: "Tổng giá trị thẩm định",
      });
    }
  }

  return (
    <Card>
      <CardHeader>
        <p className="eyebrow">Calculated metrics</p>
        <CardTitle>Chỉ số trọng yếu</CardTitle>
      </CardHeader>
      <CardContent>
        {rows.length === 0 ? (
          <EmptyState
            compact
            title="Chưa có chỉ số"
            description="Các tỷ lệ tài chính sẽ xuất hiện sau khi Credit và Collateral Agent hoàn tất."
          />
        ) : (
          <div className="overflow-hidden rounded-xl border border-border">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-4 py-3 font-bold">Chỉ số</th>
                  <th className="px-4 py-3 text-right font-bold">Kết quả</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {rows.map((row) => (
                  <tr key={row.label}>
                    <td className="px-4 py-3">
                      <span className="block font-bold">{row.label}</span>
                      <span className="text-xs text-muted-foreground">{row.note}</span>
                    </td>
                    <td className="px-4 py-3 text-right text-base font-black text-primary">
                      {row.value}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
