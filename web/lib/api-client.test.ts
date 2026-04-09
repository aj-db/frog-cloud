import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createCrawlApi } from "./api-client";
import type {
  CrawlComparisonSummary,
  CrawlJobAccepted,
  IssueTrendResponse,
} from "./api-types";
import { ApiRequestError } from "./api-types";

const originalFetch = global.fetch;
const originalApiUrl = process.env.NEXT_PUBLIC_API_URL;

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: init.status ?? 200,
    headers: {
      "content-type": "application/json",
      ...(init.headers ?? {}),
    },
  });
}

function csvResponse(body: string, init: ResponseInit = {}): Response {
  return new Response(body, {
    status: init.status ?? 200,
    headers: {
      "content-type": "text/csv",
      ...(init.headers ?? {}),
    },
  });
}

function requestAt(mock: ReturnType<typeof vi.fn>, index = 0): Request {
  return mock.mock.calls[index]?.[0] as Request;
}

describe("createCrawlApi", () => {
  const getToken = vi.fn(async () => "token-123");
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    global.fetch = fetchMock as typeof fetch;
    process.env.NEXT_PUBLIC_API_URL = "https://api.example.com";
    getToken.mockClear();
  });

  afterEach(() => {
    global.fetch = originalFetch;
    if (originalApiUrl === undefined) {
      delete process.env.NEXT_PUBLIC_API_URL;
    } else {
      process.env.NEXT_PUBLIC_API_URL = originalApiUrl;
    }
  });

  it("loads crawl summary with the previous crawl query param", async () => {
    const summary: CrawlComparisonSummary = {
      current: {
        job_id: "job-1",
        target_url: "https://example.com",
        completed_at: null,
        urls_crawled: 12,
        avg_response_time_ms: 123,
        issues_count: 4,
        issue_type_counts: [
          { issue_type: "missing_title", count: 3 },
          { issue_type: "status_404", count: 1 },
        ],
        status_codes: { status_2xx: 10, status_3xx: 1, status_4xx: 1, status_5xx: 0, other: 0 },
        status_code_counts: [
          { status_code: 200, count: 10 },
          { status_code: 301, count: 1 },
          { status_code: 404, count: 1 },
        ],
        indexability: { indexable: 8, non_indexable: 4 },
        sitemap_coverage: { in_sitemap: 7, not_in_sitemap: 5, unknown: 0 },
      },
      previous: null,
      new_issue_types: [],
      resolved_issue_types: [],
      issue_type_deltas: [],
    };
    fetchMock.mockResolvedValue(jsonResponse(summary));

    const api = createCrawlApi(getToken);
    await expect(api.getCrawlSummary("job-1", "prev-1")).resolves.toEqual(summary);

    const request = requestAt(fetchMock);
    const url = new URL(request.url);
    expect(request.method).toBe("GET");
    expect(url.pathname).toBe("/api/crawls/job-1/summary");
    expect(url.searchParams.get("previous_job_id")).toBe("prev-1");
    expect(request.headers.get("authorization")).toBe("Bearer token-123");
  });

  it("loads issues trend for completed crawls", async () => {
    const trend: IssueTrendResponse = {
      issue_types: ["missing_title"],
      points: [
        {
          job_id: "job-1",
          completed_at: "2026-04-08T00:00:00.000Z",
          target_url: "https://example.com",
          issue_type: "missing_title",
          url_count: 3,
        },
      ],
    };
    fetchMock.mockResolvedValue(jsonResponse(trend));

    const api = createCrawlApi(getToken);
    await expect(api.getIssuesTrend()).resolves.toEqual(trend);

    const request = requestAt(fetchMock);
    expect(request.method).toBe("GET");
    expect(new URL(request.url).pathname).toBe("/api/crawls/issues-trend");
    expect(request.headers.get("authorization")).toBe("Bearer token-123");
  });

  it("exports crawl CSV as a blob with serialized filters", async () => {
    fetchMock.mockResolvedValue(csvResponse("address,status_code\nhttps://example.com,200\n"));

    const api = createCrawlApi(getToken);
    const blob = await api.exportCrawlCSV("job-1", {
      filters: '[{"field":"status_code","operator":"neq","value":"200"}]',
      filter_logic: "or",
    });

    const request = requestAt(fetchMock);
    const url = new URL(request.url);
    expect(request.method).toBe("GET");
    expect(url.pathname).toBe("/api/crawls/job-1/pages/export");
    expect(url.searchParams.get("format")).toBe("csv");
    expect(url.searchParams.get("filters")).toBe(
      '[{"field":"status_code","operator":"neq","value":"200"}]',
    );
    expect(url.searchParams.get("filter_logic")).toBe("or");
    await expect(blob.text()).resolves.toContain("address,status_code");
  });

  it("surfaces export failures through ApiRequestError", async () => {
    fetchMock.mockResolvedValue(csvResponse("Only format=csv is supported", { status: 400 }));

    const api = createCrawlApi(getToken);
    await expect(api.exportCrawlCSV("job-1", { filters: "[]" })).rejects.toMatchObject({
      name: "ApiRequestError",
      status: 400,
      body: "Only format=csv is supported",
    });
  });

  it("retries a crawl with a typed POST request", async () => {
    const accepted: CrawlJobAccepted = { job_id: "job-2", status: "queued" };
    fetchMock.mockResolvedValue(jsonResponse(accepted, { status: 202 }));

    const api = createCrawlApi(getToken);
    await expect(api.retryCrawl("job-1")).resolves.toEqual(accepted);

    const request = requestAt(fetchMock);
    expect(request.method).toBe("POST");
    expect(new URL(request.url).pathname).toBe("/api/crawls/job-1/retry");
    expect(request.headers.get("authorization")).toBe("Bearer token-123");
    expect(request.headers.get("content-type")).toBeNull();
    await expect(request.text()).resolves.toBe("");
  });

  it("deletes a crawl with a typed DELETE request", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));

    const api = createCrawlApi(getToken);
    await expect(api.deleteCrawl("job-1")).resolves.toBeUndefined();

    const request = requestAt(fetchMock);
    expect(request.method).toBe("DELETE");
    expect(new URL(request.url).pathname).toBe("/api/crawls/job-1");
    expect(request.headers.get("authorization")).toBe("Bearer token-123");
  });

  it("surfaces duplicate failures through ApiRequestError", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ detail: "Job not found" }, { status: 404 }),
    );

    const api = createCrawlApi(getToken);
    await expect(api.duplicateCrawl("missing-job")).rejects.toMatchObject({
      name: "ApiRequestError",
      status: 404,
      body: { detail: "Job not found" },
    } satisfies Partial<ApiRequestError>);

    const request = requestAt(fetchMock);
    expect(request.method).toBe("POST");
    expect(new URL(request.url).pathname).toBe("/api/crawls/missing-job/duplicate");
    expect(request.headers.get("authorization")).toBe("Bearer token-123");
    expect(request.headers.get("content-type")).toBeNull();
    await expect(request.text()).resolves.toBe("");
  });
});
