import React from 'react';
import { Finding, FindingSeverity } from '../../types';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card';
import { Badge } from '../ui/Badge';

interface FindingsPanelProps {
  findings: Finding[];
  onEvidenceClick: (evidenceId: string) => void;
}

export function FindingsPanel({ findings, onEvidenceClick }: FindingsPanelProps) {
  if (!findings || findings.length === 0) {
    return null;
  }

  const severityBadge = (severity: FindingSeverity) => {
    switch (severity) {
      case FindingSeverity.CRITICAL: return <Badge variant="destructive">Critical</Badge>;
      case FindingSeverity.WARNING: return <Badge variant="warning">Warning</Badge>;
      default: return <Badge variant="secondary">Info</Badge>;
    }
  };

  return (
    <Card className="border-amber-200">
      <CardHeader className="bg-amber-50 border-b border-amber-100 pb-3">
        <CardTitle className="text-lg text-amber-900 flex items-center">
          <svg className="w-5 h-5 mr-2 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          Cảnh báo & Rủi ro phát hiện
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-4 space-y-3 max-h-64 overflow-y-auto">
        {findings.map(finding => (
          <div key={finding.id} className="p-3 bg-white border rounded-md shadow-sm flex flex-col gap-2">
            <div className="flex items-start justify-between">
              <div className="flex gap-2 items-center">
                {severityBadge(finding.severity)}
                <span className="text-sm font-semibold text-slate-700">{finding.type}</span>
              </div>
            </div>
            <p className="text-sm text-slate-600 leading-relaxed">{finding.message}</p>
            {finding.evidence_id && (
              <button
                onClick={() => onEvidenceClick(finding.evidence_id!)}
                className="text-xs text-blue-600 self-start mt-1 hover:underline"
              >
                👉 Xem vùng bằng chứng
              </button>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
