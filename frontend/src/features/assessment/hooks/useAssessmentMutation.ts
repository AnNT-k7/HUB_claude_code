"use client";

import { useCallback, useState } from "react";

import { startAssessment } from "@/features/assessment/api";
import type { AssessmentStartResponse } from "@/shared/types/api";
import { ApiError } from "@/shared/utils/api-client";

export function useAssessmentMutation() {
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const start = useCallback(async (caseId: string): Promise<AssessmentStartResponse> => {
    setIsStarting(true);
    setError(null);
    try {
      const response = await startAssessment(caseId);
      setIsStarting(false);
      return response;
    } catch (caught: unknown) {
      const message =
        caught instanceof ApiError
          ? caught.message
          : "Không thể khởi động quá trình thẩm định.";
      setError(message);
      setIsStarting(false);
      throw caught;
    }
  }, []);

  return { start, isStarting, error, clearError: () => setError(null) };
}
