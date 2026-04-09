import { describe, expect, it } from "vitest";

import {
  formatIssueTypeLabel,
  formatStatusCodeLabel,
  parseStatusIssueCode,
  statusCodeFilterKey,
} from "./issue-types";

describe("issue type helpers", () => {
  it("formats derived status issue types as HTTP labels", () => {
    expect(parseStatusIssueCode("status_404")).toBe(404);
    expect(formatIssueTypeLabel("status_404")).toBe("HTTP 404");
  });

  it("keeps non-status issue labels human readable", () => {
    expect(parseStatusIssueCode("missing_title")).toBeNull();
    expect(formatIssueTypeLabel("missing_title")).toBe("missing title");
  });

  it("formats exact status-code buckets for the detail summary", () => {
    expect(formatStatusCodeLabel(500)).toBe("HTTP 500");
    expect(formatStatusCodeLabel(null)).toBe("No status");
    expect(statusCodeFilterKey(null)).toBe("__empty__");
  });
});
