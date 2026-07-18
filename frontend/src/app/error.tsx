"use client";

import { useEffect } from "react";

import { Alert } from "@/shared/components/ui/alert";
import { Button } from "@/shared/components/ui/button";

interface ErrorPageProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function ErrorPage({ error, reset }: ErrorPageProps) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main className="page-container py-12">
      <Alert tone="danger" title="Đã xảy ra lỗi ngoài dự kiến">
        <p>Giao diện không thể hoàn tất thao tác này. Dữ liệu hồ sơ không bị thay đổi.</p>
        <Button className="mt-4" size="sm" variant="outline" onClick={reset}>
          Thử tải lại
        </Button>
      </Alert>
    </main>
  );
}
