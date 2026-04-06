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
  urls_crawled: number | null;
  error: string | null;
  profile?: CrawlProfile | null;
  /** Aggregates — optional until backend sends them */
  issues_count?: number | null;
  avg_response_time_ms?: number | null;
}

export interface CrawlPageRow {
  id: string;
  job_id: string;
  address: string;
  status_code: number | null;
  title: string | null;
  word_count: number | null;
  indexability: string | null;
  crawl_depth: number | null;
  response_time: number | null;
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
  search?: string;
  has_issues?: boolean;
  issue_type?: string;
  severity?: IssueSeverity;
}

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
