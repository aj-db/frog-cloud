"use client";

import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import { useEffect, useMemo, useState } from "react";
import type { CrawlPageRow, PagesQueryParams } from "@/lib/api-types";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import type { IssueFilter } from "@/components/issue-summary";
import { useCrawlApi } from "@/lib/use-crawl-api";
import { useQuery } from "@tanstack/react-query";

const indexabilityOptions = [
  { value: "", label: "Any indexability" },
  { value: "Indexable", label: "Indexable" },
  { value: "Non-Indexable", label: "Non-Indexable" },
];

export interface CrawlTableQuerySnapshot extends PagesQueryParams {
  cursor: string | null;
}

export interface CrawlTableProps {
  jobId: string;
  issueFilter: IssueFilter | null;
  onQuerySnapshot?: (q: CrawlTableQuerySnapshot) => void;
}

function SortIndicator({ active, dir }: { active: boolean; dir: "asc" | "desc" }) {
  if (!active) return <span className="text-[var(--border-faded)]">↕</span>;
  return <span aria-hidden>{dir === "asc" ? "↑" : "↓"}</span>;
}

export function CrawlTable({ jobId, issueFilter, onQuerySnapshot }: CrawlTableProps) {
  const api = useCrawlApi();
  const [cursor, setCursor] = useState<string | null>(null);
  const [cursorStack, setCursorStack] = useState<(string | null)[]>([]);
  const [sorting, setSorting] = useState<SortingState>([{ id: "address", desc: false }]);
  const [statusFilter, setStatusFilter] = useState("");
  const [indexability, setIndexability] = useState("");
  const [search, setSearch] = useState("");
  const [hasIssues, setHasIssues] = useState(false);

  const sortKey = (sorting[0]?.id ?? "address") as PagesQueryParams["sort"];
  const sortDir = sorting[0]?.desc ? "desc" : "asc";

  const queryParams: PagesQueryParams = useMemo(
    () => ({
      cursor,
      limit: 100,
      sort: sortKey,
      dir: sortDir,
      status_code: statusFilter || undefined,
      indexability: indexability || undefined,
      search: search || undefined,
      has_issues: hasIssues || undefined,
      issue_type: issueFilter?.issue_type,
      severity: issueFilter?.severity,
    }),
    [
      cursor,
      sortKey,
      sortDir,
      statusFilter,
      indexability,
      search,
      hasIssues,
      issueFilter?.issue_type,
      issueFilter?.severity,
    ],
  );

  const snapshot: CrawlTableQuerySnapshot = useMemo(
    () => ({ ...queryParams, cursor }),
    [queryParams, cursor],
  );

  useEffect(() => {
    onQuerySnapshot?.(snapshot);
  }, [snapshot, onQuerySnapshot]);

  const pagesQuery = useQuery({
    queryKey: ["crawl-pages", jobId, queryParams],
    queryFn: () => api.getCrawlPages(jobId, queryParams),
    enabled: Boolean(jobId),
  });

  const rows = pagesQuery.data?.items ?? [];
  const nextCursor = pagesQuery.data?.next_cursor ?? null;

  const [selected, setSelected] = useState<CrawlPageRow | null>(null);

  const columns = useMemo<ColumnDef<CrawlPageRow>[]>(
    () => [
      {
        accessorKey: "address",
        header: "Address",
        cell: (info) => (
          <span className="max-w-[240px] truncate text-[13px] text-[var(--charcoal)]">
            {info.getValue<string>()}
          </span>
        ),
      },
      {
        accessorKey: "status_code",
        header: "Status",
        cell: (info) => (
          <span className="font-mono text-[12px] font-medium text-[var(--charcoal)]">
            {info.getValue<number | null>() ?? "—"}
          </span>
        ),
      },
      {
        accessorKey: "title",
        header: "Title",
        cell: (info) => (
          <span className="max-w-[180px] truncate text-[13px] text-[var(--muted)]">
            {info.getValue<string | null>() ?? "—"}
          </span>
        ),
      },
      {
        accessorKey: "word_count",
        header: "Words",
        cell: (info) => (
          <span className="font-mono text-[12px]">{info.getValue<number | null>() ?? "—"}</span>
        ),
      },
      {
        accessorKey: "response_time",
        header: "RT (ms)",
        cell: (info) => (
          <span className="font-mono text-[12px]">{info.getValue<number | null>() ?? "—"}</span>
        ),
      },
      {
        accessorKey: "indexability",
        header: "Indexability",
        cell: (info) => (
          <span className="text-[12px] text-[var(--muted)]">
            {info.getValue<string | null>() ?? "—"}
          </span>
        ),
      },
      {
        accessorKey: "crawl_depth",
        header: "Depth",
        cell: (info) => (
          <span className="font-mono text-[12px]">{info.getValue<number | null>() ?? "—"}</span>
        ),
      },
    ],
    [],
  );

  const table = useReactTable({
    data: rows,
    columns,
    state: { sorting },
    manualSorting: true,
    getCoreRowModel: getCoreRowModel(),
  });

  const toggleSort = (columnId: string) => {
    setSorting((prev) => {
      const cur = prev[0];
      if (cur?.id === columnId) {
        return [{ id: columnId, desc: !cur.desc }];
      }
      return [{ id: columnId, desc: false }];
    });
    setCursor(null);
    setCursorStack([]);
  };

  const goNext = () => {
    if (!nextCursor) return;
    setCursorStack((s) => [...s, cursor]);
    setCursor(nextCursor);
  };

  const goPrev = () => {
    setCursorStack((s) => {
      if (s.length === 0) return s;
      const prev = s[s.length - 1];
      setCursor(prev);
      return s.slice(0, -1);
    });
  };

  return (
    <div className="space-y-3">
      <div className="ds-card grid gap-3 sm:grid-cols-2">
        <Input
          label="Search URL or title"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setCursor(null);
            setCursorStack([]);
          }}
          placeholder="https://example.com"
        />
        <div>
          <label className="ds-label" htmlFor="status-code-filter">
            Status code
          </label>
          <input
            id="status-code-filter"
            className="ds-input"
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setCursor(null);
              setCursorStack([]);
            }}
            placeholder="e.g. 404 or 4xx"
          />
        </div>
        <div>
          <label className="ds-label" htmlFor="index-filter">
            Indexability
          </label>
          <select
            id="index-filter"
            className="ds-select"
            value={indexability}
            onChange={(e) => {
              setIndexability(e.target.value);
              setCursor(null);
              setCursorStack([]);
            }}
          >
            {indexabilityOptions.map((o) => (
              <option key={o.value || "any"} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
        <label className="flex items-end gap-2 pb-2 text-[12px] font-medium text-[var(--charcoal)]">
          <input
            type="checkbox"
            checked={hasIssues}
            onChange={(e) => {
              setHasIssues(e.target.checked);
              setCursor(null);
              setCursorStack([]);
            }}
            className="h-4 w-4 rounded border border-[var(--border)]"
          />
          Only URLs with issues
        </label>
      </div>

      <div className="ds-table-wrap">
        <table className="ds-table">
          <thead>
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((header) => {
                  const colId = header.column.id;
                  const sortable = [
                    "address",
                    "status_code",
                    "word_count",
                    "response_time",
                    "crawl_depth",
                  ].includes(colId);
                  const sorted = sorting[0]?.id === colId;
                  const dir = sorting[0]?.desc ? "desc" : "asc";
                  return (
                    <th
                      key={header.id}
                      className={sortable ? "ds-th-sortable" : undefined}
                      onClick={
                        sortable
                          ? () => {
                              toggleSort(colId);
                            }
                          : undefined
                      }
                    >
                      <span className="inline-flex items-center gap-1">
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        {sortable ? (
                          <SortIndicator active={sorted} dir={dir as "asc" | "desc"} />
                        ) : null}
                      </span>
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>
          <tbody>
            {pagesQuery.isLoading ? (
              <tr>
                <td colSpan={columns.length} className="py-10 text-center text-[var(--muted)]">
                  <span className="ds-spinner ds-spinner--sm mr-2 align-middle" />
                  Loading pages…
                </td>
              </tr>
            ) : pagesQuery.isError ? (
              <tr>
                <td colSpan={columns.length} className="py-8 text-center text-[var(--red)]">
                  Could not load pages.
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="py-8 text-center text-[var(--muted)]">
                  No rows match the current filters.
                </td>
              </tr>
            ) : (
              table.getRowModel().rows.map((row) => (
                <tr
                  key={row.id}
                  className="cursor-pointer"
                  onClick={() => setSelected(row.original)}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-mono text-[11px] text-[var(--muted)]">
          Total (reported): {pagesQuery.data?.total_count ?? "—"}
        </p>
        <div className="flex gap-2">
          <Button
            type="button"
            variant="secondary"
            disabled={cursorStack.length === 0 || pagesQuery.isLoading}
            onClick={goPrev}
          >
            Previous
          </Button>
          <Button
            type="button"
            variant="secondary"
            disabled={!nextCursor || pagesQuery.isLoading}
            onClick={goNext}
          >
            Next
          </Button>
        </div>
      </div>

      {selected ? (
        <PageDrawer row={selected} onClose={() => setSelected(null)} />
      ) : null}
    </div>
  );
}

function PageDrawer({ row, onClose }: { row: CrawlPageRow; onClose: () => void }) {
  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/20 p-3"
      role="dialog"
      aria-modal="true"
      aria-label="Page details"
    >
      <button
        type="button"
        className="absolute inset-0 cursor-default"
        aria-label="Close drawer"
        onClick={onClose}
      />
      <div
        className="relative z-10 flex h-full w-full max-w-md flex-col overflow-y-auto border bg-[var(--card)] shadow-lg"
        style={{ borderColor: "var(--border)", borderRadius: "var(--radius)" }}
      >
        <div
          className="flex items-center justify-between border-b px-4 py-3"
          style={{ borderColor: "var(--border-faded)" }}
        >
          <p className="font-soehne text-[14px] font-semibold text-[var(--charcoal)]">
            Page details
          </p>
          <button
            type="button"
            className="ds-btn ds-btn--ghost"
            onClick={onClose}
          >
            Close
          </button>
        </div>
        <div className="space-y-3 p-4 text-[13px]">
          <div>
            <p className="ds-label">URL</p>
            <p className="break-all text-[var(--charcoal)]">{row.address}</p>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <p className="ds-label">Status</p>
              <p className="font-mono font-medium text-[var(--charcoal)]">
                {row.status_code ?? "—"}
              </p>
            </div>
            <div>
              <p className="ds-label">Depth</p>
              <p className="font-mono font-medium text-[var(--charcoal)]">
                {row.crawl_depth ?? "—"}
              </p>
            </div>
            <div>
              <p className="ds-label">Words</p>
              <p className="font-mono font-medium text-[var(--charcoal)]">
                {row.word_count ?? "—"}
              </p>
            </div>
            <div>
              <p className="ds-label">Response (ms)</p>
              <p className="font-mono font-medium text-[var(--charcoal)]">
                {row.response_time ?? "—"}
              </p>
            </div>
          </div>
          <div>
            <p className="ds-label">Title</p>
            <p className="text-[var(--charcoal)]">{row.title ?? "—"}</p>
          </div>
          <div>
            <p className="ds-label">Indexability</p>
            <p className="text-[var(--charcoal)]">{row.indexability ?? "—"}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
