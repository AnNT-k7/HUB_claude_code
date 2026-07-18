"use client";

import { useRef, useState, type ChangeEvent, type DragEvent } from "react";

import { Button } from "@/shared/components/ui/button";
import { cn } from "@/shared/utils/classnames";
import { formatFileSize } from "@/shared/utils/formatters";

const MAX_FILE_SIZE = 25 * 1024 * 1024;
const ACCEPTED_EXTENSIONS = [
  ".pdf",
  ".doc",
  ".docx",
  ".xls",
  ".xlsx",
  ".csv",
  ".png",
  ".jpg",
  ".jpeg",
];

interface DocumentUploadZoneProps {
  files: readonly File[];
  onChange: (files: File[]) => void;
  disabled?: boolean;
  compact?: boolean;
}

function fileKey(file: File): string {
  return `${file.name}:${file.size}:${file.lastModified}`;
}

export function DocumentUploadZone({
  files,
  onChange,
  disabled = false,
  compact = false,
}: DocumentUploadZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  const addFiles = (incoming: FileList | readonly File[]) => {
    const selected = Array.from(incoming);
    const invalidFile = selected.find((file) => file.size > MAX_FILE_SIZE);
    if (invalidFile) {
      setValidationError(`${invalidFile.name} vượt quá giới hạn 25 MB.`);
      return;
    }
    const existingKeys = new Set(files.map(fileKey));
    const uniqueFiles = selected.filter((file) => !existingKeys.has(fileKey(file)));
    setValidationError(null);
    onChange([...files, ...uniqueFiles]);
  };

  const handleInput = (event: ChangeEvent<HTMLInputElement>) => {
    if (event.target.files) {
      addFiles(event.target.files);
    }
    event.target.value = "";
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(false);
    if (!disabled) {
      addFiles(event.dataTransfer.files);
    }
  };

  return (
    <div className="space-y-3">
      <div
        onDragEnter={(event) => {
          event.preventDefault();
          if (!disabled) setIsDragging(true);
        }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={(event) => {
          if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
            setIsDragging(false);
          }
        }}
        onDrop={handleDrop}
        className={cn(
          "rounded-2xl border-2 border-dashed text-center transition-colors",
          compact ? "p-5" : "p-7",
          isDragging
            ? "border-primary bg-primary/5"
            : "border-slate-300 bg-slate-50/70 hover:border-primary/40",
          disabled && "cursor-not-allowed opacity-60",
        )}
      >
        <input
          ref={inputRef}
          className="sr-only"
          type="file"
          multiple
          disabled={disabled}
          accept={ACCEPTED_EXTENSIONS.join(",")}
          onChange={handleInput}
          aria-label="Chọn tài liệu hồ sơ"
        />
        <div className="mx-auto grid h-11 w-11 place-items-center rounded-xl bg-white text-xl shadow-sm ring-1 ring-border">
          ↑
        </div>
        <p className="mt-3 text-sm font-bold text-foreground">
          Kéo thả tài liệu vào đây
        </p>
        <p className="mt-1 text-xs leading-5 text-muted-foreground">
          PDF, Office, CSV hoặc ảnh · tối đa 25 MB mỗi tệp
        </p>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="mt-4"
          disabled={disabled}
          onClick={() => inputRef.current?.click()}
        >
          Chọn tệp
        </Button>
      </div>

      {validationError ? (
        <p role="alert" className="text-sm font-medium text-danger">
          {validationError}
        </p>
      ) : null}

      {files.length > 0 ? (
        <ul className="space-y-2" aria-label="Tài liệu đã chọn">
          {files.map((file) => (
            <li
              key={fileKey(file)}
              className="flex items-center justify-between gap-3 rounded-xl border border-border bg-white px-3 py-2.5"
            >
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold">{file.name}</p>
                <p className="text-xs text-muted-foreground">
                  {formatFileSize(file.size)}
                </p>
              </div>
              <button
                type="button"
                disabled={disabled}
                className="shrink-0 rounded-lg px-2 py-1 text-xs font-semibold text-muted-foreground hover:bg-red-50 hover:text-danger disabled:opacity-50"
                onClick={() =>
                  onChange(files.filter((candidate) => fileKey(candidate) !== fileKey(file)))
                }
                aria-label={`Xóa ${file.name}`}
              >
                Xóa
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
