'use client';

import React, { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { getCaseDetails, submitHumanReview } from '../../../lib/api';
import { CaseContext, HumanReviewOutcome, WorkflowState } from '../../../types';
import { DocumentViewer } from '../../../components/workspace/DocumentViewer';
import { SummaryWidget } from '../../../components/workspace/SummaryWidget';
import { SalaryTable } from '../../../components/workspace/SalaryTable';
import { FindingsPanel } from '../../../components/workspace/FindingsPanel';
import { ActionPanel } from '../../../components/workspace/ActionPanel';
import { Badge } from '../../../components/ui/Badge';

export default function CaseDetailsPage() {
  const params = useParams();
  const router = useRouter();
  const caseId = params.id as string;

  const [caseData, setCaseData] = useState<CaseContext | null>(null);
  const [error, setError] = useState('');
  const [activeEvidenceId, setActiveEvidenceId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Polling logic
  useEffect(() => {
    let interval: NodeJS.Timeout;

    const fetchCase = async () => {
      try {
        const data = await getCaseDetails(caseId);
        setCaseData(data);
        setError('');

        // Dừng polling nếu đã hoàn thành bước AI và đến bước Human Review hoặc đã xong toàn bộ
        if (
          data.workflow_state === WorkflowState.PENDING_HUMAN_REVIEW ||
          data.workflow_state === WorkflowState.HUMAN_REVIEW ||
          data.workflow_state === WorkflowState.COMPLETED ||
          data.workflow_state === WorkflowState.MANUAL_REVIEW_REQUIRED ||
          data.workflow_state === WorkflowState.TECHNICAL_ERROR
        ) {
          clearInterval(interval);
        }
      } catch (err: any) {
        setError(err.message || 'Lỗi khi tải dữ liệu hồ sơ');
        clearInterval(interval); // Dừng polling nếu lỗi
      }
    };

    fetchCase();
    // Poll mỗi 2 giây
    interval = setInterval(fetchCase, 2000);

    return () => clearInterval(interval);
  }, [caseId]);

  const handleSubmitReview = async (outcome: HumanReviewOutcome, approvedActionIds: string[], reason: string) => {
    setIsSubmitting(true);
    try {
      await submitHumanReview(caseId, { outcome, reason, approved_action_ids: approvedActionIds });
      // Lấy lại data để cập nhật state thành COMPLETED
      const data = await getCaseDetails(caseId);
      setCaseData(data);
      alert('Đã phê duyệt thành công!');
    } catch (err: any) {
      alert(err.message || 'Lỗi phê duyệt');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (error) {
    return (
      <div className="p-6 bg-red-50 text-red-700 rounded-md shadow mt-10 max-w-3xl mx-auto">
        <h3 className="font-bold text-lg mb-2">Lỗi tải dữ liệu</h3>
        <p>{error}</p>
        <button onClick={() => router.push('/')} className="mt-4 text-blue-600 underline">Quay lại Dashboard</button>
      </div>
    );
  }

  if (!caseData) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] space-y-4">
        <div className="w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
        <p className="text-slate-500 font-medium animate-pulse">Đang tải hồ sơ {caseId}...</p>
      </div>
    );
  }

  const isPolling = ![
    WorkflowState.PENDING_HUMAN_REVIEW, 
    WorkflowState.HUMAN_REVIEW, 
    WorkflowState.COMPLETED, 
    WorkflowState.MANUAL_REVIEW_REQUIRED, 
    WorkflowState.TECHNICAL_ERROR
  ].includes(caseData.workflow_state);

  return (
    <div className="flex flex-col h-full gap-4 pb-10">
      <div className="flex justify-between items-end">
        <div>
          <h2 className="text-2xl font-bold text-slate-800">Hồ sơ thẩm định: {caseData.application_id}</h2>
          <p className="text-slate-500 text-sm mt-1">Case ID: {caseId} • Cập nhật: {new Date(caseData.updated_at).toLocaleString()}</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-slate-600 font-medium">Trạng thái hiện tại:</span>
          <Badge variant={isPolling ? 'warning' : 'default'} className="text-sm py-1 px-3">
            {caseData.workflow_state}
            {isPolling && <span className="ml-2 w-2 h-2 inline-block rounded-full bg-white animate-pulse"></span>}
          </Badge>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
        {/* Cột trái: Document Viewer */}
        <div className="sticky top-20">
          <DocumentViewer 
            evidenceList={caseData.evidence_list || []} 
            activeEvidenceId={activeEvidenceId} 
          />
        </div>

        {/* Cột phải: Data & Analysis Widgets */}
        <div className="space-y-6">
          {/* Summary Widget */}
          <SummaryWidget 
            extractedData={caseData.extracted_data} 
            calculatedIncome={caseData.calculated_income} 
          />

          {/* Findings Panel */}
          <FindingsPanel 
            findings={caseData.findings || []} 
            onEvidenceClick={setActiveEvidenceId} 
          />

          {/* Salary Transactions Table */}
          <SalaryTable 
            transactions={caseData.extracted_data?.salary_transactions || []} 
            onEvidenceClick={setActiveEvidenceId} 
          />

          {/* Action Panel / Review UI */}
          <ActionPanel 
            actions={caseData.proposed_actions || []} 
            workflowState={caseData.workflow_state}
            onSubmit={handleSubmitReview}
            isSubmitting={isSubmitting}
          />
        </div>
      </div>
    </div>
  );
}
