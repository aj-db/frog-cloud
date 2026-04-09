import type { CrawlJob, IssueTrendResponse } from "./api-types";
import { parseStatusIssueCode } from "./issue-types";

export interface IssuesTrendChartRow {
  jobId: string;
  completedAt: string | null;
  targetUrl: string;
  label: string;
  [issueType: string]: string | number | null;
}

function buildChartLabel(completedAt: string | null, fallback: string): string {
  if (!completedAt) return fallback;

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
  }).format(new Date(completedAt));
}

export function buildIssuesTrendSeries(
  trend: IssueTrendResponse,
  completedCrawls: CrawlJob[] = [],
): IssuesTrendChartRow[] {
  const rows = new Map<string, IssuesTrendChartRow>();

  for (const crawl of completedCrawls) {
    rows.set(crawl.id, {
      jobId: crawl.id,
      completedAt: crawl.completed_at,
      targetUrl: crawl.target_url,
      label: buildChartLabel(crawl.completed_at, crawl.id.slice(0, 8)),
    });
  }

  for (const point of trend.points) {
    const existing = rows.get(point.job_id) ?? {
      jobId: point.job_id,
      completedAt: point.completed_at,
      targetUrl: point.target_url,
      label: buildChartLabel(point.completed_at, point.job_id.slice(0, 8)),
    };

    existing[point.issue_type] = point.url_count;
    rows.set(point.job_id, existing);
  }

  const issueTypes = trend.issue_types;
  const sortedRows = Array.from(rows.values()).sort((left, right) => {
    if (left.completedAt && right.completedAt) {
      return left.completedAt.localeCompare(right.completedAt);
    }
    if (left.completedAt) return -1;
    if (right.completedAt) return 1;
    return left.jobId.localeCompare(right.jobId);
  });

  return sortedRows.map((row) => {
    const nextRow: IssuesTrendChartRow = { ...row };
    for (const issueType of issueTypes) {
      if (typeof nextRow[issueType] !== "number") {
        nextRow[issueType] = 0;
      }
    }
    return nextRow;
  });
}

export function getDefaultIssueTypes(
  trend: IssueTrendResponse,
  limit = 6,
): string[] {
  const totals = new Map<string, number>();

  for (const issueType of trend.issue_types) {
    totals.set(issueType, 0);
  }

  for (const point of trend.points) {
    totals.set(point.issue_type, (totals.get(point.issue_type) ?? 0) + point.url_count);
  }

  return Array.from(totals.entries())
    .filter(([issueType]) => parseStatusIssueCode(issueType) !== 200)
    .sort((left, right) => {
      if (right[1] !== left[1]) {
        return right[1] - left[1];
      }
      return left[0].localeCompare(right[0]);
    })
    .slice(0, limit)
    .map(([issueType]) => issueType);
}
