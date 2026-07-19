import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card';
import { DocumentEvidence } from '../../types';

interface DocumentViewerProps {
  evidenceList: DocumentEvidence[];
  activeEvidenceId?: string | null;
}

export function DocumentViewer({ evidenceList, activeEvidenceId }: DocumentViewerProps) {
  const activeEvidence = evidenceList.find(e => e.evidence_id === activeEvidenceId);

  return (
    <Card className="h-[85vh] flex flex-col">
      <CardHeader className="border-b pb-4">
        <CardTitle>Bằng chứng & Hồ sơ</CardTitle>
      </CardHeader>
      <CardContent className="flex-1 p-0 flex flex-col items-center justify-center bg-slate-100 overflow-y-auto relative">
        {activeEvidence ? (
          <div className="w-full h-full flex flex-col items-center p-6 space-y-4">
            <div className="bg-white p-4 rounded shadow w-full max-w-2xl border-l-4 border-blue-500">
              <h4 className="font-bold text-lg mb-2">{activeEvidence.document_name} - Trang {activeEvidence.page_number}</h4>
              <p className="text-slate-700 bg-yellow-100 p-2 rounded">
                "{activeEvidence.raw_text}"
              </p>
            </div>
            {/* Placeholder for actual PDF Viewer */}
            <div className="flex-1 w-full bg-white border shadow-sm flex items-center justify-center text-slate-400 rounded">
              [PDF Viewer / Image Viewer would render here]
              <br/>
              URL: {activeEvidence.snippet_url || 'N/A'}
            </div>
          </div>
        ) : (
          <div className="text-slate-400 text-center">
            <svg className="w-16 h-16 mx-auto text-slate-300 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <p>Chọn một bằng chứng bên phải để xem chi tiết</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
