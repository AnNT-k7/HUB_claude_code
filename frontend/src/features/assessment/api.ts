import type {
  AssessmentStartResponse,
  AssessmentRun,
  AssessmentRuntime,
  DebateLog,
  PaginatedResponse,
  SharedBoard,
} from "@/shared/types/api";
import { apiClient, type ApiRequestOptions } from "@/shared/utils/api-client";

type DebateListResponse = DebateLog[] | PaginatedResponse<DebateLog>;

export function startAssessment(
  caseId: string,
  options: ApiRequestOptions = {},
): Promise<AssessmentStartResponse> {
  return apiClient.post<AssessmentStartResponse>(
    `/orchestrator/cases/${encodeURIComponent(caseId)}/assessment`,
    undefined,
    options,
  );
}

export function stopAssessment(
  caseId: string,
  options: ApiRequestOptions = {},
): Promise<AssessmentRun> {
  return apiClient.post<AssessmentRun>(
    `/orchestrator/cases/${encodeURIComponent(caseId)}/assessment/stop`,
    undefined,
    options,
  );
}

export function resumeAssessment(
  caseId: string,
  options: ApiRequestOptions = {},
): Promise<AssessmentStartResponse> {
  return apiClient.post<AssessmentStartResponse>(
    `/orchestrator/cases/${encodeURIComponent(caseId)}/assessment/resume`,
    undefined,
    options,
  );
}

export function getAssessmentRuntime(
  caseId: string,
  options: ApiRequestOptions = {},
): Promise<AssessmentRuntime> {
  return apiClient.get<AssessmentRuntime>(
    `/orchestrator/cases/${encodeURIComponent(caseId)}/assessment/runtime`,
    options,
  );
}

export function getSharedBoard(
  caseId: string,
  options: ApiRequestOptions = {},
): Promise<SharedBoard> {
  return apiClient.get<SharedBoard>(
    `/orchestrator/cases/${encodeURIComponent(caseId)}/shared-board`,
    options,
  );
}

export async function getDebates(
  caseId: string,
  options: ApiRequestOptions = {},
): Promise<DebateLog[]> {
  const response = await apiClient.get<DebateListResponse>(
    `/orchestrator/cases/${encodeURIComponent(caseId)}/debates`,
    options,
  );
  return Array.isArray(response) ? response : response.items;
}
