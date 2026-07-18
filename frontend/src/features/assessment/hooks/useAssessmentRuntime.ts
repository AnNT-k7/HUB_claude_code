"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { getAssessmentRuntime } from "@/features/assessment/api";
import type { AssessmentEvent, AssessmentRuntime } from "@/shared/types/api";
import { API_BASE_URL, ApiError } from "@/shared/utils/api-client";

const TERMINAL = new Set(["PAUSED", "COMPLETED", "FAILED"]);

function runStatusFromEvent(event: AssessmentEvent) {
  if (event.event_type === "RUN_STARTED") return "RUNNING" as const;
  if (event.event_type === "STOP_REQUESTED") return "STOP_REQUESTED" as const;
  if (event.event_type === "RUN_PAUSED") return "PAUSED" as const;
  if (event.event_type === "RUN_COMPLETED") return "COMPLETED" as const;
  if (event.event_type === "RUN_FAILED") return "FAILED" as const;
  return null;
}

export function useAssessmentRuntime(
  caseId: string,
  enabled: boolean,
  onActivity?: () => void,
) {
  const [runtime, setRuntime] = useState<AssessmentRuntime>({ events: [] });
  const [isLoading, setIsLoading] = useState(enabled);
  const [isLive, setIsLive] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshIndex, setRefreshIndex] = useState(0);
  const lastEventIdRef = useRef(0);

  const refresh = useCallback(() => setRefreshIndex((value) => value + 1), []);

  useEffect(() => {
    lastEventIdRef.current = runtime.events.at(-1)?.id ?? 0;
  }, [runtime.events]);

  useEffect(() => {
    if (!enabled) return undefined;
    let disposed = false;
    let pollTimer: ReturnType<typeof setTimeout> | undefined;
    const controller = new AbortController();

    const load = async () => {
      try {
        const result = await getAssessmentRuntime(caseId, { signal: controller.signal });
        if (disposed) return;
        setRuntime(result);
        setError(null);
      } catch (caught: unknown) {
        if (disposed || controller.signal.aborted) return;
        setError(caught instanceof ApiError ? caught.message : "Không thể tải tiến trình agent.");
      } finally {
        if (!disposed) {
          setIsLoading(false);
          pollTimer = setTimeout(() => void load(), 2_500);
        }
      }
    };
    void load();
    return () => {
      disposed = true;
      controller.abort();
      if (pollTimer) clearTimeout(pollTimer);
    };
  }, [caseId, enabled, refreshIndex]);

  useEffect(() => {
    const runId = runtime.run?.id;
    const runStatus = runtime.run?.status;
    if (!enabled || !runId || !runStatus || TERMINAL.has(runStatus)) return undefined;
    const controller = new AbortController();
    const lastId = lastEventIdRef.current;

    const connect = async () => {
      try {
        const headers = new Headers({ Accept: "text/event-stream" });
        const officerId = process.env.NEXT_PUBLIC_OFFICER_ID?.trim();
        if (officerId) headers.set("X-Officer-ID", officerId);
        const response = await fetch(
          `${API_BASE_URL}/orchestrator/cases/${encodeURIComponent(caseId)}/events/stream?after=${lastId}`,
          { headers, credentials: "include", signal: controller.signal },
        );
        if (!response.ok || !response.body) throw new Error("SSE unavailable");
        setIsLive(true);
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        while (!controller.signal.aborted) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const packets = buffer.split("\n\n");
          buffer = packets.pop() ?? "";
          for (const packet of packets) {
            const data = packet
              .split("\n")
              .find((line) => line.startsWith("data: "))
              ?.slice(6);
            if (!data) continue;
            const event = JSON.parse(data) as AssessmentEvent;
            setRuntime((current) => ({
              ...current,
              run: current.run
                ? {
                    ...current.run,
                    current_stage: event.stage,
                    status: runStatusFromEvent(event) ?? current.run.status,
                  }
                : current.run,
              events: current.events.some((item) => item.id === event.id)
                ? current.events
                : [...current.events, event].slice(-200),
            }));
            onActivity?.();
          }
        }
      } catch {
        if (!controller.signal.aborted) setIsLive(false);
      } finally {
        if (!controller.signal.aborted) refresh();
      }
    };
    void connect();
    return () => {
      controller.abort();
      setIsLive(false);
    };
  }, [caseId, enabled, onActivity, refresh, runtime.run?.id, runtime.run?.status]);

  return { runtime, isLoading, isLive, error, refresh };
}
