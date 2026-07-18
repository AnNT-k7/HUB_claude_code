"use client";

import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { Dialog } from "@/shared/components/ui/dialog";
import type { AgentCitation } from "@/shared/types/api";

interface RagCitationModalProps {
  citation: AgentCitation | null;
  onClose: () => void;
}

export function RagCitationModal({ citation, onClose }: RagCitationModalProps) {
  return (
    <Dialog
      open={citation !== null}
      onClose={onClose}
      title="Căn cứ chính sách RAG"
      description="Nguồn nội bộ đã được agent sử dụng để hỗ trợ kết luận."
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Đóng
          </Button>
          {citation?.source_url ? (
            <a
              href={citation.source_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex h-11 items-center justify-center rounded-xl bg-primary px-4 text-sm font-semibold text-white hover:bg-primary/90"
            >
              Mở tài liệu nguồn ↗
            </a>
          ) : null}
        </>
      }
    >
      {citation ? (
        <div className="space-y-5">
          <div className="rounded-2xl border border-border bg-slate-50 p-4">
            <div className="flex flex-wrap gap-2">
              <Badge tone="info">Trang {citation.page_number}</Badge>
              <Badge tone="neutral">Mục {citation.section_id}</Badge>
              {citation.document_version ? (
                <Badge tone="purple">Phiên bản {citation.document_version}</Badge>
              ) : null}
            </div>
            <h3 className="mt-3 font-bold">{citation.document_name}</h3>
          </div>
          <blockquote className="rounded-r-xl border-l-4 border-primary bg-primary/5 px-5 py-4 text-sm italic leading-7 text-foreground">
            “{citation.quote}”
          </blockquote>
          <p className="text-xs leading-5 text-muted-foreground">
            Trích dẫn này là căn cứ hỗ trợ đánh giá, không thay thế quyết định của chuyên viên ngân hàng.
          </p>
        </div>
      ) : null}
    </Dialog>
  );
}
