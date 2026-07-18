import { describe, expect, it } from "vitest";

import {
  caseStatusLabel,
  formatFileSize,
  formatPercentage,
  formatRatio,
} from "@/shared/utils/formatters";

describe("formatters", () => {
  it("formats ratios without losing their meaning", () => {
    expect(formatRatio(1.284)).toBe("1.28x");
    expect(formatPercentage(0.625)).toBe("62.5%");
    expect(formatPercentage(62.5)).toBe("62.5%");
  });

  it("formats file sizes and case statuses", () => {
    expect(formatFileSize(1_048_576)).toBe("1.00 MB");
    expect(caseStatusLabel("TIER3_PENDING_REVIEW")).toBe("Chờ phê duyệt");
  });
});
