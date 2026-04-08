"use client";

import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo, useState } from "react";
import { Alert } from "@/components/alert";
import { Button } from "@/components/button";
import { CrawlStatusBadge } from "@/components/crawl-status-badge";
import type { CrawlJob } from "@/lib/api-types";
import { formatDuration } from "@/lib/duration";
import { jobIsActive } from "@/lib/job-status";
import { useCrawlApi } from "@/lib/use-crawl-api";

const columnHelper = createColumnHelper<CrawlJob>();

export default function CrawlsPage() {
  const api = useCrawlApi();
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["crawls"],
    queryFn: () => api.getCrawls(),
  });
  const [deleteTarget, setDeleteTarget] = useState<CrawlJob | null>(null);
  const deleteMutation = useMutation({
    mutationFn: (jobId: string) => api.deleteCrawl(jobId),
    onSuccess: () => {
      setDeleteTarget(null);
      void queryClient.invalidateQueries({ queryKey: ["crawls"] });
    },
  });

  const columns = useMemo(
    () => [
      columnHelper.accessor("target_url", {
        header: "Target URL",
        cell: (info) => (
          <Link
            href={`/crawls/${info.row.original.id}`}
            className="font-medium text-[var(--charcoal)] underline-offset-2 hover:underline"
          >
            <span className="max-w-[280px] truncate inline-block align-bottom">
              {info.getValue()}
            </span>
          </Link>
        ),
      }),
      columnHelper.accessor("status", {
        header: "Status",
        cell: (info) => <CrawlStatusBadge status={info.getValue()} />,
      }),
      columnHelper.display({
        id: "profile",
        header: "Profile",
        cell: (info) => (
          <span className="text-[13px] text-[var(--muted)]">
            {info.row.original.profile?.name ?? "—"}
          </span>
        ),
      }),
      columnHelper.accessor("started_at", {
        header: "Started",
        cell: (info) => (
          <span className="font-mono text-[12px] text-[var(--muted)]">
            {info.getValue()
              ? new Intl.DateTimeFormat(undefined, {
                  dateStyle: "medium",
                  timeStyle: "short",
                }).format(new Date(info.getValue() as string))
              : "—"}
          </span>
        ),
      }),
      columnHelper.display({
        id: "duration",
        header: "Duration",
        cell: (info) => (
          <span className="font-mono text-[12px] text-[var(--charcoal)]">
            {formatDuration(
              info.row.original.started_at,
              info.row.original.completed_at,
            )}
          </span>
        ),
      }),
      columnHelper.display({
        id: "actions",
        header: "",
        cell: (info) => {
          const job = info.row.original;
          if (jobIsActive(job.status)) return null;
          return (
            <button
              type="button"
              className="text-[12px] font-medium text-[var(--muted)] hover:text-[var(--red)] transition-colors"
              onClick={(e) => {
                e.stopPropagation();
                setDeleteTarget(job);
              }}
            >
              Delete
            </button>
          );
        },
      }),
    ],
    [],
  );

  const table = useReactTable({
    data: query.data ?? [],
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="ds-section-label mb-1">Workspace</p>
          <h1 className="ds-page-title">Crawls</h1>
          <p className="mt-1 max-w-xl text-[13px] text-[var(--muted)]">
            Start a crawl, monitor progress, and open reports without leaving the browser.
          </p>
        </div>
        <Link href="/crawls/new" className="ds-btn ds-btn--primary no-underline">
          New crawl
        </Link>
      </div>

      {query.isLoading ? (
        <div className="ds-card flex items-center gap-3 py-10">
          <span className="ds-spinner ds-spinner--sm" />
          <span className="text-[13px] text-[var(--muted)]">Loading crawls…</span>
        </div>
      ) : null}

      {query.isError ? (
        <Alert variant="error" title="Could not load crawls">
          <div className="flex flex-wrap items-center gap-2">
            <span>Check your API URL and organization access, then try again.</span>
            <Button type="button" variant="secondary" onClick={() => void query.refetch()}>
              Retry
            </Button>
          </div>
        </Alert>
      ) : null}

      {query.isSuccess && query.data.length === 0 ? (
        <div className="ds-card space-y-3 py-10 text-center">
          <p className="font-soehne text-[16px] font-semibold text-[var(--charcoal)]">
            No crawls yet
          </p>
          <p className="text-[13px] text-[var(--muted)]">
            Create your first crawl to see it listed here.
          </p>
          <Link href="/crawls/new" className="ds-btn ds-btn--primary inline-flex no-underline">
            Start a crawl
          </Link>
        </div>
      ) : null}

      {query.isSuccess && query.data.length > 0 ? (
        <div className="ds-table-wrap">
          <table className="ds-table">
            <thead>
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id}>
                  {hg.headers.map((header) => (
                    <th key={header.id}>
                      {flexRender(header.column.columnDef.header, header.getContext())}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.map((row) => (
                <tr key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {deleteTarget ? (
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
            <p className="break-all font-mono text-[12px] text-[var(--charcoal)]">
              {deleteTarget.target_url}
            </p>
            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="secondary"
                disabled={deleteMutation.isPending}
                onClick={() => setDeleteTarget(null)}
              >
                Cancel
              </Button>
              <Button
                type="button"
                variant="primary"
                loading={deleteMutation.isPending}
                onClick={() => deleteMutation.mutate(deleteTarget.id)}
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
