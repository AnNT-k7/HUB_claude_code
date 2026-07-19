import React from 'react';
import { ExtractedData, CalculatedIncome } from '../../types';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card';
import { formatVnd } from '../../lib/utils';
import { Badge } from '../ui/Badge';

interface SummaryWidgetProps {
  extractedData: ExtractedData;
  calculatedIncome: CalculatedIncome;
}

export function SummaryWidget({ extractedData, calculatedIncome }: SummaryWidgetProps) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-xl">Tổng quan Thu nhập</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1">
            <p className="text-sm text-slate-500">Khách hàng</p>
            <p className="font-medium text-lg">{extractedData.customer_name || 'N/A'}</p>
          </div>
          <div className="space-y-1">
            <p className="text-sm text-slate-500">Nơi công tác (HĐLĐ)</p>
            <p className="font-medium">{extractedData.employer || 'N/A'}</p>
          </div>
          <div className="space-y-1">
            <p className="text-sm text-slate-500">Thu nhập khai báo</p>
            <p className="font-medium text-slate-700">{formatVnd(extractedData.declared_income)}</p>
          </div>
          <div className="space-y-1">
            <p className="text-sm text-slate-500">Lương HĐLĐ</p>
            <p className="font-medium text-slate-700">{formatVnd(extractedData.contract_salary)}</p>
          </div>
          <div className="col-span-2 mt-4 p-4 rounded-lg bg-slate-50 border flex justify-between items-center">
            <div>
              <p className="text-sm text-slate-500 font-semibold mb-1">Thu nhập tính toán (AI)</p>
              <p className="text-2xl font-bold text-blue-700">
                {formatVnd(calculatedIncome.qualified_income)}
              </p>
            </div>
            <div>
              {calculatedIncome.is_stable ? (
                <Badge variant="success" className="text-sm py-1">Ổn định</Badge>
              ) : (
                <Badge variant="warning" className="text-sm py-1">Biến động</Badge>
              )}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
