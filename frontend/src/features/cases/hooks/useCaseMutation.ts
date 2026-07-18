"use client";

import { useCallback, useState } from "react";

import { createCase, uploadCaseDocument } from "@/features/cases/api";
import type {
  CaseCreateRequest,
  CaseDetail,
  DocumentMetadata,
} from "@/shared/types/api";
import { ApiError } from "@/shared/utils/api-client";

type MutationPhase = "idle" | "creating" | "uploading";

export function useCaseMutation() {
  const [phase, setPhase] = useState<MutationPhase>("idle");
  const [error, setError] = useState<string | null>(null);

  const reset = useCallback(() => {
    setPhase("idle");
    setError(null);
  }, []);

  const createCaseWithDocuments = useCallback(
    async (input: CaseCreateRequest, files: readonly File[]): Promise<CaseDetail> => {
      setError(null);
      setPhase("creating");
      try {
        const createdCase = await createCase(input);
        if (files.length > 0) {
          setPhase("uploading");
          await Promise.all(
            files.map((file) => uploadCaseDocument(createdCase.id, file)),
          );
        }
        setPhase("idle");
        return createdCase;
      } catch (caught: unknown) {
        const message =
          caught instanceof ApiError
            ? caught.message
            : "Không thể tạo hồ sơ. Vui lòng thử lại.";
        setError(message);
        setPhase("idle");
        throw caught;
      }
    },
    [],
  );

  const uploadDocuments = useCallback(
    async (caseId: string, files: readonly File[]): Promise<DocumentMetadata[]> => {
      setError(null);
      setPhase("uploading");
      try {
        const documents = await Promise.all(
          files.map((file) => uploadCaseDocument(caseId, file)),
        );
        setPhase("idle");
        return documents;
      } catch (caught: unknown) {
        const message =
          caught instanceof ApiError
            ? caught.message
            : "Không thể tải tài liệu lên.";
        setError(message);
        setPhase("idle");
        throw caught;
      }
    },
    [],
  );

  return {
    phase,
    error,
    isPending: phase !== "idle",
    createCaseWithDocuments,
    uploadDocuments,
    reset,
  };
}
