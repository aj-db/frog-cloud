export type JobStatus =
  | "queued"
  | "provisioning"
  | "running"
  | "extracting"
  | "loading"
  | "complete"
  | "failed"
  | "cancelled";

export interface CrawlProfile {
  id: string;
  tenant_id?: string;
  name: string;
  description: string | null;
  config_path?: string | null;
}

export interface CrawlJob {
  id: string;
  tenant_id?: string;
  profile_id: string;
  target_url: string;
  status: JobStatus;
  progress_pct: number | null;
  started_at: string | null;
  completed_at: string | null;
  last_heartbeat_at: string | null;
  max_urls: number | null;
  urls_crawled: number | null;
  status_message: string | null;
  error: string | null;
  profile?: CrawlProfile | null;
  /** Aggregates — optional until backend sends them */
  issues_count?: number | null;
  avg_response_time_ms?: number | null;
}

export interface CrawlJobAccepted {
  job_id: string;
  status: JobStatus;
}

export interface CrawlPageRow {
  id: string;
  job_id: string;
  address: string;
  status_code: number | null;
  title: string | null;
  meta_description: string | null;
  h1: string | null;
  word_count: number | null;
  indexability: string | null;
  crawl_depth: number | null;
  response_time: number | null;
  canonical: string | null;
  content_type: string | null;
  redirect_url: string | null;
  size_bytes: number | null;
  inlinks: number | null;
  outlinks: number | null;
  meta_robots: string | null;
  canonical_link_element: string | null;
  pagination_status: string | null;
  http_version: string | null;
  x_robots_tag: string | null;
  link_score: number | null;
  in_sitemap: boolean | null;
}

export interface PaginatedPages {
  items: CrawlPageRow[];
  next_cursor: string | null;
  total_count: number;
}

export type IssueSeverity = "error" | "warning" | "info";

export interface CrawlIssueRow {
  id: string;
  job_id: string;
  page_id: string | null;
  issue_type: string;
  severity: IssueSeverity;
  details: string | null;
}

export interface CrawlLinkRow {
  id: string;
  job_id: string;
  source_url: string;
  target_url: string;
  link_type: string | null;
  anchor_text: string | null;
  status_code: number | null;
}

export interface PaginatedLinks {
  items: CrawlLinkRow[];
  next_cursor: string | null;
  total_count: number;
}

export interface ScheduledCrawl {
  id: string;
  tenant_id?: string;
  profile_id: string;
  target_url: string;
  cron_expression: string;
  timezone: string;
  is_active: boolean;
  next_run_at: string | null;
  profile?: CrawlProfile | null;
}

export interface CreateCrawlInput {
  target_url: string;
  profile_id: string;
  max_urls?: number | null;
}

export interface CreateProfileInput {
  name: string;
  description?: string | null;
  config_path?: string | null;
}

export interface UpdateProfileInput {
  name?: string;
  description?: string | null;
  config_path?: string | null;
}

export interface CreateScheduleInput {
  target_url: string;
  profile_id: string;
  cron_expression: string;
  timezone: string;
  is_active?: boolean;
}

export interface UpdateScheduleInput {
  target_url?: string;
  profile_id?: string;
  cron_expression?: string;
  timezone?: string;
  is_active?: boolean;
}

export interface PagesQueryParams {
  cursor?: string | null;
  limit?: number;
  sort?: "address" | "status_code" | "word_count" | "response_time" | "crawl_depth";
  dir?: "asc" | "desc";
  status_code?: string;
  indexability?: string;
  content_type?: string;
  in_sitemap?: boolean;
  search?: string;
  has_issues?: boolean;
  issue_type?: string;
  severity?: IssueSeverity;
}

// --- Cross-crawl comparison summary ------------------------------------------

export interface StatusCodeDistribution {
  status_2xx: number;
  status_3xx: number;
  status_4xx: number;
  status_5xx: number;
  other: number;
}

export interface IndexabilityDistribution {
  indexable: number;
  non_indexable: number;
}

export interface SitemapCoverage {
  in_sitemap: number;
  not_in_sitemap: number;
  unknown: number;
}

export interface IssueTypeDelta {
  issue_type: string;
  previous_count: number;
  current_count: number;
  delta: number;
}

export interface CrawlSnapshotAggregates {
  job_id: string;
  target_url: string;
  completed_at: string | null;
  urls_crawled: number;
  avg_response_time_ms: number | null;
  issues_count: number;
  status_codes: StatusCodeDistribution;
  indexability: IndexabilityDistribution;
  sitemap_coverage: SitemapCoverage;
}

export interface CrawlComparisonSummary {
  current: CrawlSnapshotAggregates;
  previous: CrawlSnapshotAggregates | null;
  new_issue_types: string[];
  resolved_issue_types: string[];
  issue_type_deltas: IssueTypeDelta[];
}

// --- Errors ------------------------------------------------------------------

export class ApiRequestError extends Error {
  status: number;
  body: unknown;

  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.body = body;
  }
}
