import type {
  AssessmentStartResponse,
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
