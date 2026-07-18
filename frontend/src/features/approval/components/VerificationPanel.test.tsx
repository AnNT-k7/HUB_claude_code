import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { VerificationPanel } from "@/features/approval/components/VerificationPanel";

describe("VerificationPanel", () => {
  it("requires explicit revision feedback before confirmation", () => {
    render(
      <VerificationPanel
        caseId="case-1"
        caseStatus="TIER3_PENDING_REVIEW"
        consensusReached
        onStateChanged={() => undefined}
      />,
    );

    fireEvent.click(screen.getByLabelText(/Yêu cầu chỉnh sửa/i));
    fireEvent.click(screen.getByRole("button", { name: /Xem lại & xác nhận/i }));

    expect(screen.getByRole("alert").textContent).toContain(
      "Vui lòng nhập phản hồi chỉnh sửa cụ thể",
    );
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("does not expose operations before approval", () => {
    render(
      <VerificationPanel
        caseId="case-1"
        caseStatus="TIER3_PENDING_REVIEW"
        consensusReached
        onStateChanged={() => undefined}
      />,
    );

    expect(screen.queryByRole("button", { name: /Thực thi vận hành/i })).toBeNull();
  });
});
