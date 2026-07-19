import React, { useState } from 'react';
import { ProposedAction, HumanReviewOutcome, WorkflowState } from '../../types';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card';
import { Button } from '../ui/Button';

interface ActionPanelProps {
  actions: ProposedAction[];
  workflowState: WorkflowState;
  onSubmit: (outcome: HumanReviewOutcome, approvedActionIds: string[], reason: string) => void;
  isSubmitting: boolean;
}

export function ActionPanel({ actions, workflowState, onSubmit, isSubmitting }: ActionPanelProps) {
  const [selectedActions, setSelectedActions] = useState<Set<string>>(new Set(actions.map(a => a.action_id)));
  const [reason, setReason] = useState("");

  const handleToggle = (id: string) => {
    const newSet = new Set(selectedActions);
    if (newSet.has(id)) newSet.delete(id);
    else newSet.add(id);
    setSelectedActions(newSet);
  };

  const isPendingReview = workflowState === WorkflowState.PENDING_HUMAN_REVIEW || workflowState === WorkflowState.HUMAN_REVIEW;
  const isCompleted = workflowState === WorkflowState.COMPLETED;

  if (!isPendingReview && !isCompleted && actions.length === 0) {
    return null; // Don't show if empty and not in review
  }

  return (
    <Card className="border-blue-200 shadow-md">
      <CardHeader className="bg-blue-50 border-b border-blue-100">
        <CardTitle className="text-lg text-blue-900">Đề xuất Thực thi & Phê duyệt</CardTitle>
      </CardHeader>
      <CardContent className="pt-6 space-y-6">
        <div className="space-y-3">
          <h4 className="font-semibold text-sm text-slate-700 uppercase tracking-wider">Danh sách hành động đề xuất</h4>
          {actions.length === 0 ? (
            <p className="text-sm text-slate-500 italic">Hệ thống không đề xuất hành động nào.</p>
          ) : (
            <ul className="space-y-2">
              {actions.map(action => (
                <li key={action.action_id} className="flex items-start gap-3 p-3 border rounded-md bg-white hover:bg-slate-50 transition-colors">
                  <input
                    type="checkbox"
                    id={`action-${action.action_id}`}
                    className="mt-1 w-4 h-4 text-blue-600 rounded border-slate-300 focus:ring-blue-500 cursor-pointer disabled:opacity-50"
                    checked={isCompleted ? !!action.is_approved : selectedActions.has(action.action_id)}
                    onChange={() => handleToggle(action.action_id)}
                    disabled={!isPendingReview || isSubmitting}
                  />
                  <div className="flex-1">
                    <label htmlFor={`action-${action.action_id}`} className="font-medium text-slate-900 cursor-pointer block">
                      [{action.action_type}] {action.description}
                    </label>
                    <p className="text-xs text-slate-500 mt-1 font-mono">ID: {action.action_id}</p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        {isPendingReview && (
          <div className="space-y-3 pt-4 border-t">
            <label className="block font-semibold text-sm text-slate-700 uppercase tracking-wider">Ghi chú phê duyệt</label>
            <textarea
              className="w-full p-3 border rounded-md text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
              rows={3}
              placeholder="Nhập ghi chú hoặc lý do trả về..."
              value={reason}
              onChange={e => setReason(e.target.value)}
              disabled={isSubmitting}
            />
            
            <div className="flex gap-3 pt-2">
              <Button
                className="flex-1"
                variant="default"
                size="lg"
                disabled={isSubmitting}
                onClick={() => onSubmit(HumanReviewOutcome.ACCEPT_ACTIONS, Array.from(selectedActions), reason)}
              >
                {isSubmitting ? "Đang xử lý..." : "Phê duyệt & Thực thi"}
              </Button>
              <Button
                className="flex-1"
                variant="outline"
                size="lg"
                disabled={isSubmitting}
                onClick={() => onSubmit(HumanReviewOutcome.MANUAL_HANDLING, [], reason)}
              >
                Trả về Xử lý Thủ công
              </Button>
            </div>
          </div>
        )}

        {isCompleted && (
          <div className="p-4 bg-emerald-50 text-emerald-800 rounded-md border border-emerald-200 text-center font-medium">
            ✅ Hồ sơ đã hoàn tất phê duyệt.
          </div>
        )}
      </CardContent>
    </Card>
  );
}
