"use client";

import { useCallback, useEffect, useState } from "react";

import { getDebates, getSharedBoard } from "@/features/assessment/api";
import type { DebateLog, SharedBoard } from "@/shared/types/api";
import { ApiError } from "@/shared/utils/api-client";

interface SharedBoardQueryState {
  board: SharedBoard | null;
  debates: DebateLog[];
  isLoading: boolean;
  isRefreshing: boolean;
  error: string | null;
  lastUpdatedAt: string | null;
}

export function useSharedBoardQuery(
  caseId: string,
  enabled: boolean,
  pollingIntervalMs = 3_000,
) {
  const [refreshIndex, setRefreshIndex] = useState(0);
  const [state, setState] = useState<SharedBoardQueryState>({
    board: null,
    debates: [],
    isLoading: enabled,
    isRefreshing: false,
    error: null,
    lastUpdatedAt: null,
  });

  const refresh = useCallback(() => {
    setRefreshIndex((value) => value + 1);
  }, []);

  useEffect(() => {
    if (!enabled) {
      setState((current) => ({ ...current, isLoading: false, isRefreshing: false }));
      return undefined;
    }

    let disposed = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let controller = new AbortController();

    const load = async (initial: boolean) => {
      setState((current) => ({
        ...current,
        isLoading: initial && current.board === null,
        isRefreshing: !initial && current.board !== null,
        error: initial ? null : current.error,
      }));
      try {
        const [board, debates] = await Promise.all([
          getSharedBoard(caseId, { signal: controller.signal }),
          getDebates(caseId, { signal: controller.signal }),
        ]);
        if (disposed) return;
        const normalizedBoard: SharedBoard = {
          ...board,
          task_breakdown: board.task_breakdown ?? {},
          specialist_outputs: board.specialist_outputs ?? {},
        };
        setState({
          board: normalizedBoard,
          debates,
          isLoading: false,
          isRefreshing: false,
          error: null,
          lastUpdatedAt: normalizedBoard.updated_at ?? new Date().toISOString(),
        });

        const shouldContinue =
          !normalizedBoard.consensus_reached &&
          normalizedBoard.status !== "MAX_ROUNDS_REACHED" &&
          normalizedBoard.status !== "REQUIRES_MORE_DATA";
        if (shouldContinue) {
          timer = setTimeout(() => {
            controller = new AbortController();
            void load(false);
          }, pollingIntervalMs);
        }
      } catch (error: unknown) {
        if (disposed || controller.signal.aborted) return;
        if (error instanceof ApiError && error.status === 404) {
          setState({
            board: null,
            debates: [],
            isLoading: false,
            isRefreshing: false,
            error: null,
            lastUpdatedAt: null,
          });
          return;
        }
        const message =
          error instanceof ApiError
            ? error.message
            : "Không thể tải trạng thái Shared Board.";
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
      if (timer !== undefined) clearTimeout(timer);
    };
  }, [caseId, enabled, pollingIntervalMs, refreshIndex]);

  return { ...state, refresh };
}
