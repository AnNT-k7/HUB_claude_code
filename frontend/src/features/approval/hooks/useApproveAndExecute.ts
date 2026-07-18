"use client";

import { useCallback, useState } from "react";

import {
  DEFAULT_OFFICER_ID,
  executeOperations,
  submitDecision,
} from "@/features/approval/api";
import type {
  ApprovalRecord,
  DecisionRequest,
  OperationsExecutionResult,
} from "@/shared/types/api";
import { ApiError } from "@/shared/utils/api-client";

export function useApproveAndExecute(caseId: string) {
  const [isSubmittingDecision, setIsSubmittingDecision] = useState(false);
  const [isExecuting, setIsExecuting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [approval, setApproval] = useState<ApprovalRecord | null>(null);
  const [execution, setExecution] = useState<OperationsExecutionResult | null>(null);

  const decide = useCallback(
    async (input: DecisionRequest): Promise<ApprovalRecord> => {
      setIsSubmittingDecision(true);
      setError(null);
      try {
        const response = await submitDecision(caseId, input, DEFAULT_OFFICER_ID);
        setApproval(response);
        setIsSubmittingDecision(false);
        return response;
      } catch (caught: unknown) {
        const message =
          caught instanceof ApiError
            ? caught.message
            : "Không thể ghi nhận quyết định.";
        setError(message);
        setIsSubmittingDecision(false);
        throw caught;
      }
    },
    [caseId],
  );

  const execute = useCallback(async (): Promise<OperationsExecutionResult> => {
    setIsExecuting(true);
    setError(null);
    try {
      const response = await executeOperations(caseId, DEFAULT_OFFICER_ID);
      setExecution(response);
      setIsExecuting(false);
      return response;
    } catch (caught: unknown) {
      const message =
        caught instanceof ApiError
          ? caught.message
          : "Không thể thực thi tác vụ vận hành.";
      setError(message);
      setIsExecuting(false);
      throw caught;
    }
  }, [caseId]);

  return {
    officerId: DEFAULT_OFFICER_ID,
    approval,
    execution,
    isSubmittingDecision,
    isExecuting,
    error,
    decide,
    execute,
    clearError: () => setError(null),
  };
}
