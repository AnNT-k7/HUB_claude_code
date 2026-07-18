"use client";

import { useState, type FormEvent } from "react";

import { DocumentUploadZone } from "@/features/cases/components/DocumentUploadZone";
import { useCaseMutation } from "@/features/cases/hooks/useCaseMutation";
import { Alert } from "@/shared/components/ui/alert";
import { Button } from "@/shared/components/ui/button";
import { Dialog } from "@/shared/components/ui/dialog";
import type { CaseCreateRequest, CaseDetail } from "@/shared/types/api";

interface CaseCreationModalProps {
  open: boolean;
  onClose: () => void;
  onCreated: (createdCase: CaseDetail) => void;
}

interface FormState {
  companyName: string;
  requestedAmount: string;
  currency: string;
}

const INITIAL_FORM: FormState = {
  companyName: "",
  requestedAmount: "",
  currency: "VND",
};

export function CaseCreationModal({
  open,
  onClose,
  onCreated,
}: CaseCreationModalProps) {
  const [form, setForm] = useState<FormState>(INITIAL_FORM);
  const [files, setFiles] = useState<File[]>([]);
  const [validationError, setValidationError] = useState<string | null>(null);
  const mutation = useCaseMutation();

  const resetForm = () => {
    setForm(INITIAL_FORM);
    setFiles([]);
    setValidationError(null);
    mutation.reset();
  };

  const close = () => {
    resetForm();
    onClose();
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const companyName = form.companyName.trim();
    const requestedAmount = form.requestedAmount.trim().replaceAll(",", "");
    if (companyName.length < 2) {
      setValidationError("Vui lòng nhập tên doanh nghiệp hợp lệ.");
      return;
    }
    if (!/^\d+(\.\d+)?$/.test(requestedAmount) || Number(requestedAmount) <= 0) {
      setValidationError("Số tiền đề nghị phải lớn hơn 0.");
      return;
    }

    setValidationError(null);
    const payload: CaseCreateRequest = {
      company_name: companyName,
      requested_amount: requestedAmount,
      currency: form.currency,
    };
    try {
      const createdCase = await mutation.createCaseWithDocuments(payload, files);
      resetForm();
      onCreated(createdCase);
    } catch {
      // The mutation exposes its user-safe error below.
    }
  };

  const pendingLabel =
    mutation.phase === "creating"
      ? "Đang tạo hồ sơ…"
      : mutation.phase === "uploading"
        ? "Đang tải tài liệu…"
        : "Tạo hồ sơ";

  return (
    <Dialog
      open={open}
      onClose={mutation.isPending ? () => undefined : close}
      title="Khởi tạo hồ sơ tín dụng"
      description="Nhập thông tin đề nghị và đính kèm hồ sơ doanh nghiệp. Bạn có thể bổ sung tài liệu sau."
      className="sm:max-w-2xl"
    >
      <form onSubmit={handleSubmit} className="space-y-5">
        {(validationError ?? mutation.error) ? (
          <Alert tone="danger">{validationError ?? mutation.error}</Alert>
        ) : null}

        <div>
          <label htmlFor="company-name" className="form-label">
            Tên doanh nghiệp
          </label>
          <input
            id="company-name"
            className="form-input"
            value={form.companyName}
            disabled={mutation.isPending}
            autoComplete="organization"
            placeholder="Ví dụ: Công ty Cổ phần Minh An"
            onChange={(event) =>
              setForm((current) => ({
                ...current,
                companyName: event.target.value,
              }))
            }
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-[1fr_140px]">
          <div>
            <label htmlFor="requested-amount" className="form-label">
              Số tiền đề nghị
            </label>
            <input
              id="requested-amount"
              className="form-input"
              value={form.requestedAmount}
              disabled={mutation.isPending}
              inputMode="decimal"
              placeholder="50000000000"
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  requestedAmount: event.target.value,
                }))
              }
            />
          </div>
          <div>
            <label htmlFor="currency" className="form-label">
              Loại tiền
            </label>
            <select
              id="currency"
              className="form-input"
              value={form.currency}
              disabled={mutation.isPending}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  currency: event.target.value,
                }))
              }
            >
              <option value="VND">VND</option>
              <option value="USD">USD</option>
            </select>
          </div>
        </div>

        <div>
          <p className="form-label">Tài liệu ban đầu</p>
          <DocumentUploadZone
            files={files}
            onChange={setFiles}
            disabled={mutation.isPending}
            compact
          />
        </div>

        <div className="flex flex-col-reverse gap-3 border-t border-border pt-5 sm:flex-row sm:justify-end">
          <Button
            type="button"
            variant="ghost"
            disabled={mutation.isPending}
            onClick={onClose}
          >
            Hủy
          </Button>
          <Button type="submit" isLoading={mutation.isPending}>
            {pendingLabel}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
