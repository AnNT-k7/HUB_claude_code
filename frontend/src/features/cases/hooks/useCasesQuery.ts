"use client";

import { useCallback, useEffect, useState } from "react";

import { listCases } from "@/features/cases/api";
import type { CaseSummary } from "@/shared/types/api";
import { ApiError } from "@/shared/utils/api-client";

interface CasesQueryState {
  cases: CaseSummary[];
  isLoading: boolean;
  error: string | null;
}

export function useCasesQuery() {
  const [refreshIndex, setRefreshIndex] = useState(0);
  const [state, setState] = useState<CasesQueryState>({
    cases: [],
    isLoading: true,
    error: null,
  });

  const refresh = useCallback(() => {
    setState((current) => ({ ...current, isLoading: true, error: null }));
    setRefreshIndex((value) => value + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    void listCases({ signal: controller.signal })
      .then((cases) => {
        setState({ cases, isLoading: false, error: null });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        const message =
          error instanceof ApiError ? error.message : "Không thể tải danh sách hồ sơ.";
        setState((current) => ({ ...current, isLoading: false, error: message }));
      });

    return () => controller.abort();
  }, [refreshIndex]);

  return { ...state, refresh };
}
