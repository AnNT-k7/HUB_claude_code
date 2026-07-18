import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/shared/utils/api-client";

describe("apiClient", () => {
  const fetchMock = vi.fn(
    async (_input: RequestInfo | URL, _init?: RequestInit): Promise<Response> =>
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
  );

  beforeEach(() => {
    fetchMock.mockClear();
    vi.stubGlobal("fetch", fetchMock);
  });

  it("serializes snake_case JSON payloads", async () => {
    await apiClient.post<{ ok: boolean }, { company_name: string }>("/cases", {
      company_name: "Minh An",
    });

    const options = fetchMock.mock.calls[0]?.[1];
    const headers = new Headers(options?.headers);
    expect(options?.body).toBe(JSON.stringify({ company_name: "Minh An" }));
    expect(headers.get("content-type")).toBe("application/json");
  });

  it("keeps multipart boundaries under browser control", async () => {
    const formData = new FormData();
    formData.append("file", new File(["policy"], "policy.pdf"));

    await apiClient.upload<{ ok: boolean }>("/cases/case-1/documents", formData);

    const options = fetchMock.mock.calls[0]?.[1];
    const headers = new Headers(options?.headers);
    expect(options?.body).toBe(formData);
    expect(headers.has("content-type")).toBe(false);
  });
});
