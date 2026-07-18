"use client";

import { useCallback, useState } from "react";

import { resumeAssessment, startAssessment, stopAssessment } from "@/features/assessment/api";
import type { AssessmentStartResponse } from "@/shared/types/api";
import { ApiError } from "@/shared/utils/api-client";

export function useAssessmentMutation() {
  const [isStarting, setIsStarting] = useState(false);
  const [isStopping, setIsStopping] = useState(false);
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

  const stop = useCallback(async (caseId: string) => {
    setIsStopping(true);
    setError(null);
    try {
      return await stopAssessment(caseId);
    } catch (caught: unknown) {
      setError(caught instanceof ApiError ? caught.message : "Không thể dừng thẩm định.");
      throw caught;
    } finally {
      setIsStopping(false);
    }
  }, []);

  const resume = useCallback(async (caseId: string) => {
    setIsStarting(true);
    setError(null);
    try {
      return await resumeAssessment(caseId);
    } catch (caught: unknown) {
      setError(caught instanceof ApiError ? caught.message : "Không thể tiếp tục thẩm định.");
      throw caught;
    } finally {
      setIsStarting(false);
    }
  }, []);

  return { start, stop, resume, isStarting, isStopping, error, clearError: () => setError(null) };
}
