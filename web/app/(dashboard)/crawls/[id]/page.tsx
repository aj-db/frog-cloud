"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { Alert } from "@/components/alert";
import { Button } from "@/components/button";
import { CrawlProgress } from "@/components/crawl-progress";
import type { CrawlTableQuerySnapshot } from "@/components/crawl-table";
import { CrawlTable } from "@/components/crawl-table";
import { CrawlStatusBadge } from "@/components/crawl-status-badge";
import { IssueSummary, type IssueFilter } from "@/components/issue-summary";
import { JobErrorState } from "@/components/job-error-state";
import { StatCard } from "@/components/stat-card";
import type { CrawlIssueRow, CrawlJob, CrawlLinkRow } from "@/lib/api-types";
import { jobIsActive } from "@/lib/job-status";
import { useCrawlApi } from "@/lib/use-crawl-api";

type Tab = "pages" | "issues" | "links";

const issueColumnHelper = createColumnHelper<CrawlIssueRow>();
const linkColumnHelper = createColumnHelper<CrawlLinkRow>();

export default function CrawlDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const api = useCrawlApi();
  const id = params.id;

  const tabParam = searchParams.get("tab") as Tab | null;
  const tab: Tab =
    tabParam === "issues" || tabParam === "links" || tabParam === "pages"
      ? tabParam
      : "pages";

  const setTab = useCallback(
    (next: Tab) => {
      const p = new URLSearchParams(searchParams.toString());
      p.set("tab", next);
      router.replace(`?${p.toString()}`, { scroll: false });
    },
    [router, searchParams],
  );

  const [job, setJob] = useState<CrawlJob | null>(null);
  const [issueFilter, setIssueFilter] = useState<IssueFilter | null>(null);
  const [exportSnapshot, setExportSnapshot] = useState<CrawlTableQuerySnapshot | null>(null);
  const [linksCursor, setLinksCursor] = useState<string | null>(null);
  const [linksStack, setLinksStack] = useState<(string | null)[]>([]);

  useEffect(() => {
    let cancelled = false;
    void api.getCrawl(id).then((j) => {
      if (!cancelled) setJob(j);
    });
    return () => {
      cancelled = true;
    };
  }, [api, id]);

  const issuesQuery = useQuery({
    queryKey: ["crawl-issues", id],
    queryFn: () => api.getCrawlIssues(id),
    enabled: Boolean(id) && Boolean(job && (job.status === "complete" || job.status === "loading")),
  });

  const linksQuery = useQuery({
    queryKey: ["crawl-links", id, linksCursor],
    queryFn: () => api.getCrawlLinks(id, { cursor: linksCursor ?? undefined, limit: 100 }),
    enabled: Boolean(id) && tab === "links" && Boolean(job && job.status === "complete"),
  });

  const retryMutation = useMutation({
    mutationFn: () => api.retryCrawl(id),
    onSuccess: (j) => {
      setJob(j);
      void queryClient.invalidateQueries({ queryKey: ["crawl-issues", id] });
      void queryClient.invalidateQueries({ queryKey: ["crawl-links", id] });
    },
  });

  const duplicateMutation = useMutation({
    mutationFn: () => api.duplicateCrawl(id),
    onSuccess: (j) => {
      router.push(`/crawls/${j.id}`);
    },
  });

  const exportMutation = useMutation({
    mutationFn: async () => {
      const snap = exportSnapshot ?? { cursor: null, limit: 100, sort: "address", dir: "asc" };
      const { cursor: _omitCursor, ...rest } = snap;
      void _omitCursor;
      return api.exportCrawlCSV(id, rest);
    },
    onSuccess: (blob) => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `crawl-${id}-pages.csv`;
      a.click();
      URL.revokeObjectURL(url);
    },
  });

  const issueStats = useMemo(() => {
    const list = issuesQuery.data ?? [];
    let err = 0;
    let warn = 0;
    let info = 0;
    for (const i of list) {
      if (i.severity === "error") err += 1;
      else if (i.severity === "warning") warn += 1;
      else info += 1;
    }
    return { err, warn, info, total: list.length };
  }, [issuesQuery.data]);

  const issueColumns = useMemo(
    () => [
      issueColumnHelper.accessor("issue_type", {
        header: "Type",
        cell: (c) => (
          <span className="text-[13px] text-[var(--charcoal)]">{c.getValue()}</span>
        ),
      }),
      issueColumnHelper.accessor("severity", {
        header: "Severity",
        cell: (c) => (
          <span className="text-[12px] font-semibold capitalize text-[var(--muted)]">
            {c.getValue()}
          </span>
        ),
      }),
      issueColumnHelper.accessor("details", {
        header: "Details",
        cell: (c) => (
          <span className="max-w-[320px] truncate text-[12px] text-[var(--muted)]">
            {c.getValue() ?? "—"}
          </span>
        ),
      }),
    ],
    [],
  );

  const issueTable = useReactTable({
    data: issuesQuery.data ?? [],
    columns: issueColumns,
    getCoreRowModel: getCoreRowModel(),
  });

  const linkRows = linksQuery.data?.items ?? [];
  const linkNext = linksQuery.data?.next_cursor ?? null;

  const linkColumns = useMemo(
    () => [
      linkColumnHelper.accessor("source_url", {
        header: "From",
        cell: (c) => (
          <span className="max-w-[200px] truncate text-[12px] text-[var(--charcoal)]">
            {c.getValue()}
          </span>
        ),
      }),
      linkColumnHelper.accessor("target_url", {
        header: "To",
        cell: (c) => (
          <span className="max-w-[200px] truncate text-[12px] text-[var(--charcoal)]">
            {c.getValue()}
          </span>
        ),
      }),
      linkColumnHelper.accessor("status_code", {
        header: "Code",
        cell: (c) => (
          <span className="font-mono text-[12px]">{c.getValue() ?? "—"}</span>
        ),
      }),
      linkColumnHelper.accessor("anchor_text", {
        header: "Anchor",
        cell: (c) => (
          <span className="max-w-[160px] truncate text-[12px] text-[var(--muted)]">
            {c.getValue() ?? "—"}
          </span>
        ),
      }),
    ],
    [],
  );

  const linkTable = useReactTable({
    data: linkRows,
    columns: linkColumns,
    getCoreRowModel: getCoreRowModel(),
  });

  if (!job) {
    return (
      <div className="ds-card flex items-center gap-3 py-12">
        <span className="ds-spinner ds-spinner--sm" />
        <span className="text-[13px] text-[var(--muted)]">Loading crawl…</span>
      </div>
    );
  }

  const partialData = job.status === "loading";
  const showResultTables = job.status === "complete" || partialData;
  const showStats =
    job.status !== "failed" && job.status !== "cancelled";
  const active = jobIsActive(job.status);

  return (
    <div className="space-y-8">
      <nav className="text-[12px] font-medium text-[var(--muted)]">
        <Link href="/crawls" className="hover:text-[var(--charcoal)]">
          Crawls
        </Link>
        <span className="mx-1.5">/</span>
        <span className="text-[var(--charcoal)]">{job.target_url}</span>
      </nav>

      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="ds-section-label mb-1">Job</p>
          <h1 className="ds-page-title max-w-[640px] break-words">{job.target_url}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <CrawlStatusBadge status={job.status} />
            <span className="font-mono text-[11px] text-[var(--muted)]">{job.id}</span>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {showResultTables ? (
            <Button
              type="button"
              variant="secondary"
              loading={exportMutation.isPending}
              onClick={() => exportMutation.mutate()}
            >
              Export CSV
            </Button>
          ) : null}
          <Link href="/crawls/new" className="ds-btn ds-btn--ghost no-underline">
            New crawl
          </Link>
        </div>
      </div>

      {active ? (
        <CrawlProgress jobId={id} onJobUpdate={setJob} />
      ) : null}

      {partialData ? (
        <Alert variant="warning" title="Partial data">
          Results are still loading into the database. Tables may be incomplete until the job
          finishes.
        </Alert>
      ) : null}

      {job.status === "failed" ? (
        <JobErrorState
          message={job.error ?? "Unknown error"}
          failedAt={job.completed_at}
          busy={retryMutation.isPending || duplicateMutation.isPending}
          onRetry={() => retryMutation.mutate()}
          onDuplicate={() => duplicateMutation.mutate()}
        />
      ) : null}

      {showStats ? (
        <div className="grid gap-3 sm:grid-cols-3">
          <StatCard
            label="Pages crawled"
            value={job.urls_crawled ?? 0}
            delta={
              issueStats.total
                ? { value: `${issueStats.total} open issues`, positive: false }
                : undefined
            }
          />
          <StatCard label="Issues found" value={issueStats.total} />
          <StatCard
            label="Avg response (ms)"
            value={
              job.avg_response_time_ms != null
                ? Math.round(job.avg_response_time_ms)
                : "—"
            }
          />
        </div>
      ) : null}

      {showResultTables ? (
        <>
          <IssueSummary
            issues={issuesQuery.data ?? []}
            activeFilter={issueFilter}
            onSelect={setIssueFilter}
          />

          <div>
            <div className="mb-3 flex flex-wrap gap-1 border-b" style={{ borderColor: "var(--border-faded)" }}>
              {(
                [
                  ["pages", "Pages"],
                  ["issues", "Issues"],
                  ["links", "Links"],
                ] as const
              ).map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setTab(key)}
                  className="px-3 py-2 text-[12px] font-semibold transition-colors"
                  style={{
                    color: tab === key ? "var(--charcoal)" : "var(--muted)",
                    borderBottom:
                      tab === key ? "2px solid var(--charcoal)" : "2px solid transparent",
                  }}
                >
                  {label}
                </button>
              ))}
            </div>

            {tab === "pages" ? (
              <CrawlTable
                jobId={id}
                issueFilter={issueFilter}
                onQuerySnapshot={setExportSnapshot}
              />
            ) : null}

            {tab === "issues" ? (
              <div className="ds-table-wrap">
                {issuesQuery.isLoading ? (
                  <div className="flex items-center gap-2 p-6 text-[var(--muted)]">
                    <span className="ds-spinner ds-spinner--sm" />
                    Loading issues…
                  </div>
                ) : (
                  <table className="ds-table">
                    <thead>
                      {issueTable.getHeaderGroups().map((hg) => (
                        <tr key={hg.id}>
                          {hg.headers.map((h) => (
                            <th key={h.id}>
                              {flexRender(h.column.columnDef.header, h.getContext())}
                            </th>
                          ))}
                        </tr>
                      ))}
                    </thead>
                    <tbody>
                      {(issuesQuery.data ?? []).length === 0 ? (
                        <tr>
                          <td colSpan={3} className="py-8 text-center text-[var(--muted)]">
                            No issues for this crawl.
                          </td>
                        </tr>
                      ) : (
                        issueTable.getRowModel().rows.map((row) => (
                          <tr key={row.id}>
                            {row.getVisibleCells().map((cell) => (
                              <td key={cell.id}>
                                {flexRender(cell.column.columnDef.cell, cell.getContext())}
                              </td>
                            ))}
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                )}
              </div>
            ) : null}

            {tab === "links" ? (
              <div className="space-y-3">
                <div className="ds-table-wrap">
                  {linksQuery.isLoading ? (
                    <div className="flex items-center gap-2 p-6 text-[var(--muted)]">
                      <span className="ds-spinner ds-spinner--sm" />
                      Loading links…
                    </div>
                  ) : (
                    <table className="ds-table">
                      <thead>
                        {linkTable.getHeaderGroups().map((hg) => (
                          <tr key={hg.id}>
                            {hg.headers.map((h) => (
                              <th key={h.id}>
                                {flexRender(h.column.columnDef.header, h.getContext())}
                              </th>
                            ))}
                          </tr>
                        ))}
                      </thead>
                      <tbody>
                        {linkRows.length === 0 ? (
                          <tr>
                            <td colSpan={4} className="py-8 text-center text-[var(--muted)]">
                              No links indexed yet.
                            </td>
                          </tr>
                        ) : (
                          linkTable.getRowModel().rows.map((row) => (
                            <tr key={row.id}>
                              {row.getVisibleCells().map((cell) => (
                                <td key={cell.id}>
                                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                                </td>
                              ))}
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  )}
                </div>
                <div className="flex justify-end gap-2">
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={linksStack.length === 0 || linksQuery.isLoading}
                    onClick={() => {
                      setLinksStack((s) => {
                        if (s.length === 0) return s;
                        const prev = s[s.length - 1];
                        setLinksCursor(prev);
                        return s.slice(0, -1);
                      });
                    }}
                  >
                    Previous
                  </Button>
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={!linkNext || linksQuery.isLoading}
                    onClick={() => {
                      setLinksStack((s) => [...s, linksCursor]);
                      setLinksCursor(linkNext);
                    }}
                  >
                    Next
                  </Button>
                </div>
              </div>
            ) : null}
          </div>
        </>
      ) : null}
    </div>
  );
}
