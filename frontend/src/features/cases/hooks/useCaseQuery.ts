"use client";

import { useCallback, useEffect, useState } from "react";

import { getCase } from "@/features/cases/api";
import type { CaseDetail, CaseStatus } from "@/shared/types/api";
import { ApiError } from "@/shared/utils/api-client";

const POLLING_STATUSES: ReadonlySet<CaseStatus> = new Set([
  "TIER1_PLANNING",
  "TIER2_DEBATING",
]);

interface CaseQueryState {
  caseData: CaseDetail | null;
  isLoading: boolean;
  isRefreshing: boolean;
  error: string | null;
}

export function useCaseQuery(caseId: string, pollingIntervalMs = 4_000) {
  const [refreshIndex, setRefreshIndex] = useState(0);
  const [state, setState] = useState<CaseQueryState>({
    caseData: null,
    isLoading: true,
    isRefreshing: false,
    error: null,
  });

  const refresh = useCallback(() => {
    setRefreshIndex((value) => value + 1);
  }, []);

  useEffect(() => {
    let disposed = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let controller = new AbortController();

    const load = async (initial: boolean) => {
      if (disposed) {
        return;
      }
      setState((current) => ({
        ...current,
        isLoading: initial && current.caseData === null,
        isRefreshing: !initial && current.caseData !== null,
        error: initial ? null : current.error,
      }));
      try {
        const caseData = await getCase(caseId, { signal: controller.signal });
        if (disposed) {
          return;
        }
        setState({
          caseData: { ...caseData, documents: caseData.documents ?? [] },
          isLoading: false,
          isRefreshing: false,
          error: null,
        });
        if (POLLING_STATUSES.has(caseData.status)) {
          timer = setTimeout(() => {
            controller = new AbortController();
            void load(false);
          }, pollingIntervalMs);
        }
      } catch (error: unknown) {
        if (disposed || controller.signal.aborted) {
          return;
        }
        const message =
          error instanceof ApiError ? error.message : "Không thể tải hồ sơ.";
        setState((current) => ({
          ...current,
          isLoading: false,
          isRefreshing: false,
          error: message,
        }));
      }
    };

    void load(true);
    return () => {
      disposed = true;
      controller.abort();
      if (timer !== undefined) {
        clearTimeout(timer);
      }
    };
  }, [caseId, pollingIntervalMs, refreshIndex]);

  return { ...state, refresh };
}
