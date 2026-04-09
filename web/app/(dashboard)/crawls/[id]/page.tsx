"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Alert } from "@/components/alert";
import { Button } from "@/components/button";
import { CrawlProgress } from "@/components/crawl-progress";
import type { CrawlTableQuerySnapshot } from "@/components/crawl-table";
import { CrawlTable } from "@/components/crawl-table";
import { CrawlChangeSummary } from "@/components/crawl-change-summary";
import { CrawlStatusBadge } from "@/components/crawl-status-badge";
import { JobErrorState } from "@/components/job-error-state";
import type { CrawlJob } from "@/lib/api-types";
import { type FilterLogic, type FilterRule, createFilterRule } from "@/lib/filter-fields";
import { jobIsActive } from "@/lib/job-status";
import { useCrawlApi } from "@/lib/use-crawl-api";

export default function CrawlDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const api = useCrawlApi();
  const id = params.id;

  const [job, setJob] = useState<CrawlJob | null>(null);
  const [filterRules, setFilterRules] = useState<FilterRule[]>([]);
  const [filterLogic, setFilterLogic] = useState<FilterLogic>("and");
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const deleteMutation = useMutation({
    mutationFn: () => api.deleteCrawl(id),
    onSuccess: () => router.push("/crawls"),
  });
  const [exportSnapshot, setExportSnapshot] = useState<CrawlTableQuerySnapshot | null>(null);

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

  const retryMutation = useMutation({
    mutationFn: () => api.retryCrawl(id),
    onSuccess: (j) => {
      router.push(`/crawls/${j.job_id}`);
    },
  });

  const duplicateMutation = useMutation({
    mutationFn: () => api.duplicateCrawl(id),
    onSuccess: (j) => {
      router.push(`/crawls/${j.job_id}`);
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

  const issueTypeList = useMemo(() => {
    const counts = new Map<string, number>();
    for (const i of issuesQuery.data ?? []) {
      counts.set(i.issue_type, (counts.get(i.issue_type) ?? 0) + 1);
    }
    return Array.from(counts.entries())
      .sort((a, b) => b[1] - a[1])
      .map(([t]) => t);
  }, [issuesQuery.data]);

  const activeIssueType = useMemo(() => {
    const rule = filterRules.find(
      (r) => r.field === "issue_type" && r.op === "equals" && r.value,
    );
    return rule?.value ?? null;
  }, [filterRules]);

  const handleIssueSelect = useCallback(
    (issueType: string | null) => {
      if (!issueType) {
        setFilterRules((prev) =>
          prev.filter((r) => !(r.field === "issue_type" && r.op === "equals")),
        );
        return;
      }
      setFilterRules((prev) => {
        const existing = prev.find(
          (r) => r.field === "issue_type" && r.op === "equals",
        );
        if (existing) {
          if (existing.value === issueType) {
            return prev.filter((r) => r.id !== existing.id);
          }
          return prev.map((r) =>
            r.id === existing.id ? { ...r, value: issueType } : r,
          );
        }
        const rule = createFilterRule("issue_type");
        rule.op = "equals";
        rule.value = issueType;
        return [...prev, rule];
      });
    },
    [],
  );

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
          {!active ? (
            <button
              type="button"
              className="ds-btn ds-btn--ghost text-[var(--muted)] hover:text-[var(--red)]"
              onClick={() => setShowDeleteConfirm(true)}
            >
              Delete
            </button>
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

      {showResultTables ? (
        <div className="grid items-start gap-6 lg:grid-cols-[360px_1fr]">
          <div className="space-y-6 lg:sticky lg:top-20 lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto">
            <CrawlChangeSummary
              jobId={id}
              targetUrl={job.target_url}
              enabled={job.status === "complete"}
              activeIssueType={activeIssueType}
              onIssueSelect={handleIssueSelect}
            />
          </div>

          <div className="min-w-0">
            <CrawlTable
              jobId={id}
              filterRules={filterRules}
              filterLogic={filterLogic}
              onFilterRulesChange={setFilterRules}
              onFilterLogicChange={setFilterLogic}
              issueTypes={issueTypeList}
              onQuerySnapshot={setExportSnapshot}
            />
          </div>
        </div>
      ) : null}

      {showDeleteConfirm ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/20 p-4"
          role="dialog"
          aria-modal="true"
          aria-label="Confirm delete"
        >
          <div
            className="w-full max-w-sm space-y-4 border bg-[var(--card)] p-6 shadow-lg"
            style={{ borderColor: "var(--border)", borderRadius: "var(--radius)" }}
          >
            <p className="font-soehne text-[14px] font-semibold text-[var(--charcoal)]">
              Delete this crawl?
            </p>
            <p className="text-[13px] text-[var(--muted)]">
              This will permanently remove the crawl and all its pages, issues, and links.
              This action cannot be undone.
            </p>
            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="secondary"
                disabled={deleteMutation.isPending}
                onClick={() => setShowDeleteConfirm(false)}
              >
                Cancel
              </Button>
              <Button
                type="button"
                variant="primary"
                loading={deleteMutation.isPending}
                onClick={() => deleteMutation.mutate()}
                className="!bg-[var(--red)] !text-white"
              >
                Delete
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
