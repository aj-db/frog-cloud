import createClient from "openapi-fetch";
import type {
  CrawlComparisonSummary,
  CrawlIssueRow,
  CrawlJobAccepted,
  CrawlJob,
  CrawlProfile,
  CreateCrawlInput,
  CreateProfileInput,
  CreateScheduleInput,
  IssueTrendResponse,
  PaginatedPages,
  PagesQueryParams,
  ScheduledCrawl,
  UpdateProfileInput,
  UpdateScheduleInput,
} from "./api-types";
import { ApiRequestError } from "./api-types";

/** Minimal OpenAPI-style map for openapi-fetch */
export interface paths {
  "/api/crawls": {
    get: {
      responses: {
        200: { content: { "application/json": CrawlJob[] | { crawls: CrawlJob[] } } };
      };
    };
    post: {
      requestBody: { content: { "application/json": CreateCrawlInput } };
      responses: {
        202: { content: { "application/json": CrawlJobAccepted } };
        400: { content: { "application/json": unknown } };
      };
    };
  };
  "/api/crawls/{job_id}": {
    get: {
      parameters: { path: { job_id: string } };
      responses: {
        200: { content: { "application/json": CrawlJob } };
      };
    };
    delete: {
      parameters: { path: { job_id: string } };
      responses: {
        204: { content: never };
      };
    };
  };
  "/api/crawls/{job_id}/pages": {
    get: {
      parameters: {
        path: { job_id: string };
        query: Record<string, string | number | boolean | undefined>;
      };
      responses: {
        200: { content: { "application/json": PaginatedPages } };
      };
    };
  };
  "/api/crawls/{job_id}/pages/export": {
    get: {
      parameters: {
        path: { job_id: string };
        query: Record<string, string | number | boolean | undefined>;
      };
      responses: {
        200: { content: { "text/csv": string } };
      };
    };
  };
  "/api/crawls/{job_id}/issues": {
    get: {
      parameters: {
        path: { job_id: string };
        query?: Record<string, string | undefined>;
      };
      responses: {
        200: { content: { "application/json": CrawlIssueRow[] | { items: CrawlIssueRow[] } } };
      };
    };
  };
  "/api/crawls/{job_id}/summary": {
    get: {
      parameters: {
        path: { job_id: string };
        query?: { previous_job_id?: string };
      };
      responses: {
        200: { content: { "application/json": CrawlComparisonSummary } };
      };
    };
  };
  "/api/crawls/issues-trend": {
    get: {
      responses: {
        200: { content: { "application/json": IssueTrendResponse } };
      };
    };
  };
  "/api/crawls/{job_id}/retry": {
    post: {
      parameters: { path: { job_id: string } };
      responses: {
        202: { content: { "application/json": CrawlJobAccepted } };
      };
    };
  };
  "/api/crawls/{job_id}/duplicate": {
    post: {
      parameters: { path: { job_id: string } };
      responses: {
        202: { content: { "application/json": CrawlJobAccepted } };
      };
    };
  };
  "/api/profiles": {
    get: {
      responses: {
        200: { content: { "application/json": CrawlProfile[] | { items: CrawlProfile[] } } };
      };
    };
    post: {
      requestBody: { content: { "application/json": CreateProfileInput } };
      responses: {
        201: { content: { "application/json": CrawlProfile } };
      };
    };
  };
  "/api/profiles/{profile_id}": {
    patch: {
      parameters: { path: { profile_id: string } };
      requestBody: { content: { "application/json": UpdateProfileInput } };
      responses: {
        200: { content: { "application/json": CrawlProfile } };
      };
    };
    delete: {
      parameters: { path: { profile_id: string } };
      responses: {
        204: { content: never };
      };
    };
  };
  "/api/schedules": {
    get: {
      responses: {
        200: { content: { "application/json": ScheduledCrawl[] | { items: ScheduledCrawl[] } } };
      };
    };
    post: {
      requestBody: { content: { "application/json": CreateScheduleInput } };
      responses: {
        201: { content: { "application/json": ScheduledCrawl } };
      };
    };
  };
  "/api/schedules/{schedule_id}": {
    patch: {
      parameters: { path: { schedule_id: string } };
      requestBody: { content: { "application/json": UpdateScheduleInput } };
      responses: {
        200: { content: { "application/json": ScheduledCrawl } };
      };
    };
    delete: {
      parameters: { path: { schedule_id: string } };
      responses: {
        204: { content: never };
      };
    };
  };
}

export type GetToken = () => Promise<string | null>;

function getBaseUrl(): string {
  const url = process.env.NEXT_PUBLIC_API_URL;
  if (!url) return "http://localhost:8000";
  return url.replace(/\/$/, "");
}

function normalizeCrawlList(
  payload: CrawlJob[] | { crawls?: CrawlJob[]; items?: CrawlJob[] },
): CrawlJob[] {
  if (Array.isArray(payload)) return payload;
  return payload.items ?? payload.crawls ?? [];
}

function normalizeProfiles(
  payload: CrawlProfile[] | { items: CrawlProfile[] },
): CrawlProfile[] {
  if (Array.isArray(payload)) return payload;
  return payload.items ?? [];
}

function normalizeIssues(
  payload: CrawlIssueRow[] | { items: CrawlIssueRow[] },
): CrawlIssueRow[] {
  if (Array.isArray(payload)) return payload;
  return payload.items ?? [];
}

function normalizeSchedules(
  payload: ScheduledCrawl[] | { items: ScheduledCrawl[] },
): ScheduledCrawl[] {
  if (Array.isArray(payload)) return payload;
  return payload.items ?? [];
}

function buildPagesQuery(params: PagesQueryParams): Record<string, string | number | boolean> {
  const q: Record<string, string | number | boolean> = {};
  if (params.cursor) q.cursor = params.cursor;
  if (params.limit != null) q.limit = params.limit;
  if (params.sort) q.sort = params.sort;
  if (params.dir) q.dir = params.dir;
  if (params.filters) q.filters = params.filters;
  if (params.filter_logic && params.filter_logic !== "and") q.filter_logic = params.filter_logic;
  return q;
}

export function createCrawlApi(getToken: GetToken) {
  const client = createClient<paths>({ baseUrl: getBaseUrl() });

  async function headers(): Promise<HeadersInit> {
    const token = await getToken();
    const h: Record<string, string> = {};
    if (token) h.Authorization = `Bearer ${token}`;
    return h;
  }

  return {
    getCrawls: async (query?: { target_url?: string; status?: string }): Promise<CrawlJob[]> => {
      const q: Record<string, string> = {};
      if (query?.target_url) q.target_url = query.target_url;
      if (query?.status) q.status = query.status;

      const { data, error, response } = await client.GET("/api/crawls", {
        params: { query: q },
        headers: await headers(),
      });
      if (error || !response.ok) {
        throw new ApiRequestError("Failed to load crawls", response.status, error);
      }
      return normalizeCrawlList(data as CrawlJob[] | { crawls?: CrawlJob[]; items?: CrawlJob[] });
    },

    getCrawl: async (jobId: string): Promise<CrawlJob> => {
      const { data, error, response } = await client.GET("/api/crawls/{job_id}", {
        params: { path: { job_id: jobId } },
        headers: await headers(),
      });
      if (error || !response.ok || !data) {
        throw new ApiRequestError("Failed to load crawl", response.status, error);
      }
      return data as CrawlJob;
    },

    createCrawl: async (body: CreateCrawlInput): Promise<CrawlJobAccepted> => {
      const { data, error, response } = await client.POST("/api/crawls", {
        body,
        headers: await headers(),
      });
      if (error || !response.ok || !data) {
        throw new ApiRequestError("Failed to create crawl", response.status, error ?? data);
      }
      return data as CrawlJobAccepted;
    },

    getCrawlPages: async (
      jobId: string,
      params: PagesQueryParams = {},
    ): Promise<PaginatedPages> => {
      const { data, error, response } = await client.GET("/api/crawls/{job_id}/pages", {
        params: {
          path: { job_id: jobId },
          query: buildPagesQuery(params) as Record<string, string | number | boolean | undefined>,
        },
        headers: await headers(),
      });
      if (error || !response.ok || !data) {
        throw new ApiRequestError("Failed to load pages", response.status, error);
      }
      const d = data as PaginatedPages;
      return {
        items: d.items ?? [],
        next_cursor: d.next_cursor ?? null,
        total_count: d.total_count ?? d.items?.length ?? 0,
      };
    },

    getCrawlIssues: async (jobId: string): Promise<CrawlIssueRow[]> => {
      const { data, error, response } = await client.GET("/api/crawls/{job_id}/issues", {
        params: { path: { job_id: jobId } },
        headers: await headers(),
      });
      if (error || !response.ok) {
        throw new ApiRequestError("Failed to load issues", response.status, error);
      }
      return normalizeIssues(data as CrawlIssueRow[] | { items: CrawlIssueRow[] });
    },

    getCrawlSummary: async (jobId: string, previousJobId?: string): Promise<CrawlComparisonSummary> => {
      const { data, error, response } = await client.GET("/api/crawls/{job_id}/summary", {
        params: {
          path: { job_id: jobId },
          query: previousJobId ? { previous_job_id: previousJobId } : undefined,
        },
        headers: await headers(),
      });
      if (error || !response.ok || !data) {
        throw new ApiRequestError("Failed to load summary", response.status, error);
      }
      return data;
    },

    getIssuesTrend: async (): Promise<IssueTrendResponse> => {
      const { data, error, response } = await client.GET("/api/crawls/issues-trend", {
        headers: await headers(),
      });
      if (error || !response.ok || !data) {
        throw new ApiRequestError("Failed to load issues trend", response.status, error);
      }
      return data;
    },

    getCrawlProfiles: async (): Promise<CrawlProfile[]> => {
      const { data, error, response } = await client.GET("/api/profiles", {
        headers: await headers(),
      });
      if (error || !response.ok) {
        throw new ApiRequestError("Failed to load profiles", response.status, error);
      }
      return normalizeProfiles(data as CrawlProfile[] | { items: CrawlProfile[] });
    },

    createProfile: async (body: CreateProfileInput): Promise<CrawlProfile> => {
      const { data, error, response } = await client.POST("/api/profiles", {
        body,
        headers: await headers(),
      });
      if (error || !response.ok || !data) {
        throw new ApiRequestError("Failed to create profile", response.status, error);
      }
      return data as CrawlProfile;
    },

    updateProfile: async (
      profileId: string,
      body: UpdateProfileInput,
    ): Promise<CrawlProfile> => {
      const { data, error, response } = await client.PATCH("/api/profiles/{profile_id}", {
        params: { path: { profile_id: profileId } },
        body,
        headers: await headers(),
      });
      if (error || !response.ok || !data) {
        throw new ApiRequestError("Failed to update profile", response.status, error);
      }
      return data as CrawlProfile;
    },

    deleteProfile: async (profileId: string): Promise<void> => {
      const { error, response } = await client.DELETE("/api/profiles/{profile_id}", {
        params: { path: { profile_id: profileId } },
        headers: await headers(),
      });
      if (!response.ok) {
        throw new ApiRequestError("Failed to delete profile", response.status, error);
      }
    },

    getSchedules: async (): Promise<ScheduledCrawl[]> => {
      const { data, error, response } = await client.GET("/api/schedules", {
        headers: await headers(),
      });
      if (error || !response.ok) {
        throw new ApiRequestError("Failed to load schedules", response.status, error);
      }
      return normalizeSchedules(data as ScheduledCrawl[] | { items: ScheduledCrawl[] });
    },

    createSchedule: async (body: CreateScheduleInput): Promise<ScheduledCrawl> => {
      const { data, error, response } = await client.POST("/api/schedules", {
        body,
        headers: await headers(),
      });
      if (error || !response.ok || !data) {
        throw new ApiRequestError("Failed to create schedule", response.status, error);
      }
      return data as ScheduledCrawl;
    },

    updateSchedule: async (
      scheduleId: string,
      body: UpdateScheduleInput,
    ): Promise<ScheduledCrawl> => {
      const { data, error, response } = await client.PATCH("/api/schedules/{schedule_id}", {
        params: { path: { schedule_id: scheduleId } },
        body,
        headers: await headers(),
      });
      if (error || !response.ok || !data) {
        throw new ApiRequestError("Failed to update schedule", response.status, error);
      }
      return data as ScheduledCrawl;
    },

    deleteSchedule: async (scheduleId: string): Promise<void> => {
      const { error, response } = await client.DELETE("/api/schedules/{schedule_id}", {
        params: { path: { schedule_id: scheduleId } },
        headers: await headers(),
      });
      if (!response.ok) {
        throw new ApiRequestError("Failed to delete schedule", response.status, error);
      }
    },

    exportCrawlCSV: async (
      jobId: string,
      params: PagesQueryParams = {},
    ): Promise<Blob> => {
      const { data, error, response } = await client.GET("/api/crawls/{job_id}/pages/export", {
        params: {
          path: { job_id: jobId },
          query: {
            format: "csv",
            ...buildPagesQuery(params),
          },
        },
        parseAs: "blob",
        headers: await headers(),
      });
      if (error || !response.ok || !data) {
        throw new ApiRequestError("Export failed", response.status, error);
      }
      return data;
    },

    retryCrawl: async (jobId: string): Promise<CrawlJobAccepted> => {
      const { data, error, response } = await client.POST("/api/crawls/{job_id}/retry", {
        params: { path: { job_id: jobId } },
        headers: await headers(),
      });
      if (error || !response.ok || !data) {
        throw new ApiRequestError("Retry failed", response.status, error);
      }
      return data;
    },

    deleteCrawl: async (jobId: string): Promise<void> => {
      const { error, response } = await client.DELETE("/api/crawls/{job_id}", {
        params: { path: { job_id: jobId } },
        headers: await headers(),
      });
      if (!response.ok) {
        throw new ApiRequestError("Delete failed", response.status, error);
      }
    },

    duplicateCrawl: async (jobId: string): Promise<CrawlJobAccepted> => {
      const { data, error, response } = await client.POST("/api/crawls/{job_id}/duplicate", {
        params: { path: { job_id: jobId } },
        headers: await headers(),
      });
      if (error || !response.ok || !data) {
        throw new ApiRequestError("Duplicate failed", response.status, error);
      }
      return data;
    },
  };
}

export type CrawlApi = ReturnType<typeof createCrawlApi>;
