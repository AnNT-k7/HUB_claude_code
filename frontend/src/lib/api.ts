import { CaseContext, ReviewRequest } from '../types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
const REVIEWER_ID = 'LT-01'; // Fake reviewer ID

/**
 * Custom fetch wrapper to handle errors and standard headers
 */
async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${path}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'X-Role': 'UNDERWRITER',
      'X-Reviewer-Id': REVIEWER_ID,
      ...(options.headers || {}),
    },
  });

  if (!response.ok) {
    let errorMessage = response.statusText;
    try {
      const errorBody = await response.json();
      errorMessage = errorBody.detail || errorMessage;
    } catch {
      // Ignore JSON parse errors for non-JSON responses
    }
    throw new Error(`API Error ${response.status}: ${errorMessage}`);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}

/**
 * Khởi tạo một phiên thẩm định thu nhập mới cho Application ID
 */
export async function startIncomeVerification(applicationId: string): Promise<{ case_id: string; workflow_state: string }> {
  return apiFetch<{ case_id: string; workflow_state: string }>(
    `/applications/${applicationId}/income-verification`,
    {
      method: 'POST',
    }
  );
}

/**
 * Lấy chi tiết hồ sơ thẩm định bằng Case ID
 */
export async function getCaseDetails(caseId: string): Promise<CaseContext> {
  return apiFetch<CaseContext>(`/income-verifications/${caseId}`);
}

/**
 * Gửi quyết định phê duyệt cuối cùng
 */
export async function submitHumanReview(caseId: string, payload: ReviewRequest): Promise<{ message: string; next_state: string }> {
  return apiFetch<{ message: string; next_state: string }>(
    `/income-verifications/${caseId}/review`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    }
  );
}
