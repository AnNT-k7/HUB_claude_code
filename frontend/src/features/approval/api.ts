import type {
  ApprovalRecord,
  DecisionRequest,
  OperationsExecutionResult,
} from "@/shared/types/api";
import { apiClient, type ApiRequestOptions } from "@/shared/utils/api-client";

export const DEFAULT_OFFICER_ID =
  process.env.NEXT_PUBLIC_OFFICER_ID?.trim() || "demo-officer";

function officerOptions(
  officerId: string,
  options: ApiRequestOptions = {},
): ApiRequestOptions {
  const headers = new Headers(options.headers);
  headers.set("X-Officer-ID", officerId);
  return { ...options, headers };
}

export function submitDecision(
  caseId: string,
  input: DecisionRequest,
  officerId = DEFAULT_OFFICER_ID,
  options: ApiRequestOptions = {},
): Promise<ApprovalRecord> {
  return apiClient.post<ApprovalRecord, DecisionRequest>(
    `/operations/cases/${encodeURIComponent(caseId)}/decision`,
    input,
    officerOptions(officerId, options),
  );
}

export function executeOperations(
  caseId: string,
  officerId = DEFAULT_OFFICER_ID,
  options: ApiRequestOptions = {},
): Promise<OperationsExecutionResult> {
  return apiClient.post<OperationsExecutionResult>(
    `/operations/cases/${encodeURIComponent(caseId)}/execute`,
    undefined,
    officerOptions(officerId, options),
  );
}
