"use client";

import Link from "next/link";
import { useState } from "react";

import { DebateLogViewer } from "@/features/assessment/components/DebateLogViewer";
import { RatioTable } from "@/features/assessment/components/RatioTable";
import { SharedBoardGrid } from "@/features/assessment/components/SharedBoardGrid";
import { SynthesisPanel } from "@/features/assessment/components/SynthesisPanel";
import { useAssessmentMutation } from "@/features/assessment/hooks/useAssessmentMutation";
import { useSharedBoardQuery } from "@/features/assessment/hooks/useSharedBoardQuery";
import { RagCitationModal } from "@/features/approval/components/RagCitationModal";
import { VerificationPanel } from "@/features/approval/components/VerificationPanel";
import { DocumentUploadZone } from "@/features/cases/components/DocumentUploadZone";
import { useCaseMutation } from "@/features/cases/hooks/useCaseMutation";
import { useCaseQuery } from "@/features/cases/hooks/useCaseQuery";
import { Alert } from "@/shared/components/ui/alert";
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";
import { EmptyState } from "@/shared/components/ui/empty-state";
import { PageSkeleton, Skeleton } from "@/shared/components/ui/skeleton";
import type { AgentCitation, CaseStatus } from "@/shared/types/api";
import {
  caseStatusLabel,
  formatDateTime,
  formatFileSize,
  formatMoney,
} from "@/shared/utils/formatters";
import { caseStatusTone } from "@/shared/utils/status";

const RESTARTABLE_STATUSES: ReadonlySet<CaseStatus> = new Set([
  "INGESTED",
  "AWAITING_DOCS",
  "REVISION_REQUESTED",
  "FAILED",
]);

interface CaseWorkspaceProps {
  caseId: string;
}

export function CaseWorkspace({ caseId }: CaseWorkspaceProps) {
  const caseQuery = useCaseQuery(caseId);
  const assessmentMutation = useAssessmentMutation();
  const documentMutation = useCaseMutation();
  const [files, setFiles] = useState<File[]>([]);
  const [citation, setCitation] = useState<AgentCitation | null>(null);
  const caseData = caseQuery.caseData;
  const boardEnabled = caseData !== null && caseData.status !== "INGESTED";
  const boardQuery = useSharedBoardQuery(caseId, boardEnabled);

  const refreshAll = () => {
    caseQuery.refresh();
    boardQuery.refresh();
  };

  const startAssessment = async () => {
    try {
      await assessmentMutation.start(caseId);
      refreshAll();
    } catch {
      // The mutation renders a user-safe error.
    }
  };

  const uploadSelected = async () => {
    if (files.length === 0) return;
    try {
      await documentMutation.uploadDocuments(caseId, files);
      setFiles([]);
      refreshAll();
    } catch {
      // The mutation renders a user-safe error.
    }
  };

  if (caseQuery.isLoading) {
    return <PageSkeleton />;
  }

  if (caseQuery.error || !caseData) {
    return (
      <main className="page-container py-10">
        <Alert tone="danger" title="Không thể mở hồ sơ">
          <p>{caseQuery.error ?? "Hồ sơ không tồn tại hoặc bạn không có quyền truy cập."}</p>
          <div className="mt-4 flex gap-3">
            <Button size="sm" variant="outline" onClick={caseQuery.refresh}>
              Thử lại
            </Button>
            <Link className="text-sm font-bold text-primary hover:underline" href="/cases">
              Quay lại danh sách
            </Link>
          </div>
        </Alert>
      </main>
    );
  }

  const canStart = RESTARTABLE_STATUSES.has(caseData.status);

  return (
    <main className="page-container py-7 sm:py-9">
      <Link
        href="/cases"
        className="inline-flex items-center gap-1 rounded-lg text-sm font-semibold text-muted-foreground hover:text-primary focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/20"
      >
        ← Hồ sơ tín dụng
      </Link>

      <div className="mt-5 flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <Badge tone={caseStatusTone(caseData.status)} showDot>
              {caseStatusLabel(caseData.status)}
            </Badge>
            <span className="truncate font-mono text-xs text-muted-foreground">
              {caseData.id}
            </span>
            {caseQuery.isRefreshing ? (
              <span className="text-xs font-semibold text-primary">Đang đồng bộ…</span>
            ) : null}
          </div>
          <h1 className="mt-3 text-3xl font-black tracking-tight sm:text-4xl">
            {caseData.company_name}
          </h1>
          <div className="mt-3 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-muted-foreground">
            <span className="text-xl font-black text-foreground">
              {formatMoney(caseData.requested_amount, caseData.currency)}
            </span>
            <span>Khởi tạo {formatDateTime(caseData.created_at)}</span>
            <span>{caseData.documents.length} tài liệu</span>
          </div>
        </div>
        {canStart ? (
          <Button
            size="lg"
            isLoading={assessmentMutation.isStarting}
            disabled={caseData.documents.length === 0}
            onClick={startAssessment}
          >
            {caseData.status === "INGESTED" ? "Bắt đầu thẩm định" : "Chạy lại thẩm định"}
          </Button>
        ) : null}
      </div>

      {assessmentMutation.error ? (
        <Alert tone="danger" className="mt-5">
          {assessmentMutation.error}
        </Alert>
      ) : null}

      {canStart && caseData.documents.length === 0 ? (
        <Alert tone="warning" className="mt-5">
          Cần tải lên ít nhất một tài liệu trước khi bắt đầu thẩm định.
        </Alert>
      ) : null}

      <div className="mt-7 grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0 space-y-6">
          {!boardEnabled ? (
            <Card>
              <CardContent className="pt-6">
                <EmptyState
                  title="Sẵn sàng khởi động Orchestrator"
                  description="Sau khi có tài liệu, Orchestrator sẽ lập kế hoạch, phân công các specialist agent và ghi mọi kết quả lên Shared Board."
                  action={
                    <Button
                      disabled={caseData.documents.length === 0}
                      isLoading={assessmentMutation.isStarting}
                      onClick={startAssessment}
                    >
                      Bắt đầu thẩm định
                    </Button>
                  }
                />
              </CardContent>
            </Card>
          ) : null}

          {boardEnabled && boardQuery.isLoading ? (
            <Card className="p-6">
              <Skeleton className="h-6 w-40" />
              <div className="mt-6 grid gap-4 lg:grid-cols-2">
                {[0, 1, 2, 3].map((item) => (
                  <Skeleton key={item} className="h-56" />
                ))}
              </div>
            </Card>
          ) : null}

          {boardQuery.error ? (
            <Alert tone="danger" title="Không thể đồng bộ Shared Board">
              <p>{boardQuery.error}</p>
              <Button className="mt-3" size="sm" variant="outline" onClick={boardQuery.refresh}>
                Thử lại
              </Button>
            </Alert>
          ) : null}

          {boardEnabled && !boardQuery.isLoading && !boardQuery.error && !boardQuery.board ? (
            <Alert tone="info">
              Orchestrator đang khởi tạo Shared Board. Trang sẽ cập nhật khi trạng thái sẵn sàng.
            </Alert>
          ) : null}

          {boardQuery.board ? (
            <>
              <SharedBoardGrid board={boardQuery.board} onCitationClick={setCitation} />
              <SynthesisPanel board={boardQuery.board} />
              <div className="grid gap-6 lg:grid-cols-2">
                <RatioTable board={boardQuery.board} currency={caseData.currency} />
                <DebateLogViewer
                  debates={boardQuery.debates}
                  currentRound={boardQuery.board.current_debate_round}
                  maxRounds={boardQuery.board.max_debate_rounds}
                />
              </div>
              <VerificationPanel
                caseId={caseId}
                caseStatus={caseData.status}
                existingApproval={caseData.approval}
                consensusReached={boardQuery.board.consensus_reached}
                onStateChanged={refreshAll}
              />
            </>
          ) : null}
        </div>

        <aside className="space-y-6 xl:sticky xl:top-24">
          <Card>
            <CardHeader>
              <p className="eyebrow">Case evidence</p>
              <CardTitle>Tài liệu hồ sơ</CardTitle>
            </CardHeader>
            <CardContent>
              {caseData.documents.length > 0 ? (
                <ul className="mb-5 divide-y divide-border rounded-xl border border-border">
                  {caseData.documents.map((document) => (
                    <li key={document.id} className="flex items-center gap-3 px-3 py-3">
                      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-red-50 text-xs font-black text-red-700">
                        DOC
                      </span>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-bold">
                          {document.filename || `Tài liệu ${document.id.slice(0, 8)}`}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {formatFileSize(document.size_bytes)}
                          {document.uploaded_at || document.created_at
                            ? ` · ${formatDateTime(document.uploaded_at ?? document.created_at ?? "")}`
                            : ""}
                        </p>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mb-4 text-sm text-muted-foreground">Chưa có tài liệu.</p>
              )}

              <DocumentUploadZone
                files={files}
                onChange={setFiles}
                disabled={documentMutation.isPending}
                compact
              />
              {documentMutation.error ? (
                <p role="alert" className="mt-3 text-sm font-semibold text-danger">
                  {documentMutation.error}
                </p>
              ) : null}
              {files.length > 0 ? (
                <Button
                  className="mt-4 w-full"
                  variant="outline"
                  isLoading={documentMutation.isPending}
                  onClick={uploadSelected}
                >
                  Tải lên {files.length} tài liệu
                </Button>
              ) : null}
            </CardContent>
          </Card>

          <Alert tone="info" title="Nguyên tắc an toàn">
            Tài liệu khách hàng được cô lập theo mã hồ sơ và không được đưa vào bộ nhớ vector dài hạn.
          </Alert>
        </aside>
      </div>

      <RagCitationModal citation={citation} onClose={() => setCitation(null)} />
    </main>
  );
}
