import type {
  CaseCreateRequest,
  CaseDetail,
  CaseListResponse,
  CaseSummary,
  DocumentMetadata,
} from "@/shared/types/api";
import { apiClient, type ApiRequestOptions } from "@/shared/utils/api-client";

export async function listCases(
  options: ApiRequestOptions = {},
): Promise<CaseSummary[]> {
  const response = await apiClient.get<CaseListResponse>("/cases", options);
  return Array.isArray(response) ? response : response.items;
}

export function getCase(
  caseId: string,
  options: ApiRequestOptions = {},
): Promise<CaseDetail> {
  return apiClient.get<CaseDetail>(`/cases/${encodeURIComponent(caseId)}`, options);
}

export function createCase(
  input: CaseCreateRequest,
  options: ApiRequestOptions = {},
): Promise<CaseDetail> {
  return apiClient.post<CaseDetail, CaseCreateRequest>("/cases", input, options);
}

export function uploadCaseDocument(
  caseId: string,
  file: File,
  options: ApiRequestOptions = {},
): Promise<DocumentMetadata> {
  const formData = new FormData();
  formData.append("file", file, file.name);
  return apiClient.upload<DocumentMetadata>(
    `/cases/${encodeURIComponent(caseId)}/documents`,
    formData,
    options,
  );
}
