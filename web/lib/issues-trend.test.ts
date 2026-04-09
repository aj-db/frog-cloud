import { describe, expect, it } from "vitest";

import {
  buildIssuesTrendSeries,
  getDefaultIssueTypes,
} from "./issues-trend";
import type { IssueTrendResponse } from "./api-types";

describe("issues trend helpers", () => {
  it("builds zero-filled chart rows sorted by crawl completion time", () => {
    const trend: IssueTrendResponse = {
      issue_types: ["duplicate_h1", "missing_title"],
      points: [
        {
          job_id: "job-2",
          completed_at: "2026-04-09T00:00:00.000Z",
          target_url: "https://example.com",
          issue_type: "missing_title",
          url_count: 2,
        },
        {
          job_id: "job-1",
          completed_at: "2026-04-08T00:00:00.000Z",
          target_url: "https://example.com",
          issue_type: "duplicate_h1",
          url_count: 1,
        },
        {
          job_id: "job-1",
          completed_at: "2026-04-08T00:00:00.000Z",
          target_url: "https://example.com",
          issue_type: "missing_title",
          url_count: 4,
        },
      ],
    };

    const rows = buildIssuesTrendSeries(trend);

    expect(rows).toHaveLength(2);
    expect(rows[0]).toMatchObject({
      jobId: "job-1",
      duplicate_h1: 1,
      missing_title: 4,
    });
    expect(rows[1]).toMatchObject({
      jobId: "job-2",
      duplicate_h1: 0,
      missing_title: 2,
    });
  });

  it("prefers the highest-volume issue types for the default selection", () => {
    const trend: IssueTrendResponse = {
      issue_types: ["duplicate_h1", "missing_title", "missing_meta_description"],
      points: [
        {
          job_id: "job-1",
          completed_at: "2026-04-08T00:00:00.000Z",
          target_url: "https://example.com",
          issue_type: "missing_title",
          url_count: 8,
        },
        {
          job_id: "job-1",
          completed_at: "2026-04-08T00:00:00.000Z",
          target_url: "https://example.com",
          issue_type: "duplicate_h1",
          url_count: 2,
        },
        {
          job_id: "job-2",
          completed_at: "2026-04-09T00:00:00.000Z",
          target_url: "https://example.com",
          issue_type: "missing_meta_description",
          url_count: 5,
        },
      ],
    };

    expect(getDefaultIssueTypes(trend, 2)).toEqual([
      "missing_title",
      "missing_meta_description",
    ]);
  });
});
