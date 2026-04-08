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

const sitemapOptions = [
  { value: "", label: "Any sitemap status" },
  { value: "true", label: "In sitemap" },
  { value: "false", label: "Not in sitemap" },
];

const DEPTH_SENTINEL = 2_147_483_647;
function formatDepth(v: number | null | undefined): string {
  if (v == null || v >= DEPTH_SENTINEL) return "—";
  return String(v);
}

export interface CrawlTableQuerySnapshot extends PagesQueryParams {
  cursor: string | null;
}

export interface CrawlTableProps {
  jobId: string;
  issueFilter: IssueFilter | null;
  onIssueFilterChange?: (filter: IssueFilter | null) => void;
  issueTypes?: string[];
  onQuerySnapshot?: (q: CrawlTableQuerySnapshot) => void;
}

function SortIndicator({ active, dir }: { active: boolean; dir: "asc" | "desc" }) {
  if (!active) return <span className="text-[var(--border-faded)]">↕</span>;
  return <span aria-hidden>{dir === "asc" ? "↑" : "↓"}</span>;
}

export function CrawlTable({ jobId, issueFilter, onIssueFilterChange, issueTypes = [], onQuerySnapshot }: CrawlTableProps) {
  const api = useCrawlApi();
  const [cursor, setCursor] = useState<string | null>(null);
  const [cursorStack, setCursorStack] = useState<(string | null)[]>([]);
  const [sorting, setSorting] = useState<SortingState>([{ id: "address", desc: false }]);
  const [statusFilter, setStatusFilter] = useState("");
  const [indexability, setIndexability] = useState("");
  const [contentType, setContentType] = useState("");
  const [sitemapFilter, setSitemapFilter] = useState("");
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
      content_type: contentType || undefined,
      in_sitemap: sitemapFilter === "true" ? true : sitemapFilter === "false" ? false : undefined,
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
      contentType,
      sitemapFilter,
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
        accessorKey: "indexability",
        header: "Indexability",
        cell: (info) => (
          <span className="text-[12px] text-[var(--muted)]">
            {info.getValue<string | null>() ?? "—"}
          </span>
        ),
      },
      {
        accessorKey: "meta_description",
        header: "Meta Description",
        cell: (info) => (
          <span className="max-w-[180px] truncate text-[12px] text-[var(--muted)]">
            {info.getValue<string | null>() ?? "—"}
          </span>
        ),
      },
      {
        accessorKey: "h1",
        header: "H1",
        cell: (info) => (
          <span className="max-w-[160px] truncate text-[12px] text-[var(--muted)]">
            {info.getValue<string | null>() ?? "—"}
          </span>
        ),
      },
      {
        accessorKey: "canonical",
        header: "Canonical",
        cell: (info) => (
          <span className="max-w-[160px] truncate text-[12px] text-[var(--muted)]">
            {info.getValue<string | null>() ?? "—"}
          </span>
        ),
      },
      {
        accessorKey: "canonical_link_element",
        header: "Canonical Link",
        cell: (info) => (
          <span className="max-w-[160px] truncate text-[12px] text-[var(--muted)]">
            {info.getValue<string | null>() ?? "—"}
          </span>
        ),
      },
      {
        accessorKey: "meta_robots",
        header: "Meta Robots",
        cell: (info) => (
          <span className="max-w-[120px] truncate text-[12px] text-[var(--muted)]">
            {info.getValue<string | null>() ?? "—"}
          </span>
        ),
      },
      {
        accessorKey: "x_robots_tag",
        header: "X-Robots-Tag",
        cell: (info) => (
          <span className="max-w-[120px] truncate text-[12px] text-[var(--muted)]">
            {info.getValue<string | null>() ?? "—"}
          </span>
        ),
      },
      {
        accessorKey: "pagination_status",
        header: "Pagination",
        cell: (info) => (
          <span className="text-[12px] text-[var(--muted)]">
            {info.getValue<string | null>() ?? "—"}
          </span>
        ),
      },
      {
        accessorKey: "content_type",
        header: "Content Type",
        cell: (info) => (
          <span className="max-w-[120px] truncate text-[12px] text-[var(--muted)]">
            {info.getValue<string | null>() ?? "—"}
          </span>
        ),
      },
      {
        accessorKey: "http_version",
        header: "HTTP",
        cell: (info) => (
          <span className="font-mono text-[12px]">
            {info.getValue<string | null>() ?? "—"}
          </span>
        ),
      },
      {
        accessorKey: "redirect_url",
        header: "Redirect URL",
        cell: (info) => (
          <span className="max-w-[160px] truncate text-[12px] text-[var(--muted)]">
            {info.getValue<string | null>() ?? "—"}
          </span>
        ),
      },
      {
        accessorKey: "in_sitemap",
        header: "Sitemap",
        cell: (info) => {
          const v = info.getValue<boolean | null>();
          return (
            <span className="text-[12px] text-[var(--muted)]">
              {v === true ? "Yes" : v === false ? "No" : "—"}
            </span>
          );
        },
      },
      {
        accessorKey: "word_count",
        header: "Words",
        cell: (info) => (
          <span className="font-mono text-[12px]">{info.getValue<number | null>() ?? "—"}</span>
        ),
      },
      {
        accessorKey: "crawl_depth",
        header: "Depth",
        cell: (info) => (
          <span className="font-mono text-[12px]">{formatDepth(info.getValue<number | null>())}</span>
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
        accessorKey: "size_bytes",
        header: "Size (B)",
        cell: (info) => (
          <span className="font-mono text-[12px]">{info.getValue<number | null>() ?? "—"}</span>
        ),
      },
      {
        accessorKey: "inlinks",
        header: "Inlinks",
        cell: (info) => (
          <span className="font-mono text-[12px]">{info.getValue<number | null>() ?? "—"}</span>
        ),
      },
      {
        accessorKey: "outlinks",
        header: "Outlinks",
        cell: (info) => (
          <span className="font-mono text-[12px]">{info.getValue<number | null>() ?? "—"}</span>
        ),
      },
      {
        accessorKey: "link_score",
        header: "Link Score",
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
      <div className="ds-card grid items-end gap-3 grid-cols-2 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-6">
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
        <div>
          <label className="ds-label" htmlFor="content-type-filter">
            Content type
          </label>
          <input
            id="content-type-filter"
            className="ds-input"
            value={contentType}
            onChange={(e) => {
              setContentType(e.target.value);
              setCursor(null);
              setCursorStack([]);
            }}
            placeholder="e.g. text/html"
          />
        </div>
        <div>
          <label className="ds-label" htmlFor="sitemap-filter">
            Sitemap
          </label>
          <select
            id="sitemap-filter"
            className="ds-select"
            value={sitemapFilter}
            onChange={(e) => {
              setSitemapFilter(e.target.value);
              setCursor(null);
              setCursorStack([]);
            }}
          >
            {sitemapOptions.map((o) => (
              <option key={o.value || "any"} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
        {issueTypes.length > 0 ? (
          <div>
            <label className="ds-label" htmlFor="issue-type-filter">
              Issue type
            </label>
            <select
              id="issue-type-filter"
              className="ds-select"
              value={issueFilter?.issue_type ?? ""}
              onChange={(e) => {
                const val = e.target.value;
                onIssueFilterChange?.(val ? { issue_type: val } : null);
                setCursor(null);
                setCursorStack([]);
              }}
            >
              <option value="">Any issue type</option>
              {issueTypes.map((t) => (
                <option key={t} value={t}>
                  {t.replace(/_/g, " ")}
                </option>
              ))}
            </select>
          </div>
        ) : null}
        <label className="flex h-9 items-center gap-2 text-[12px] font-medium text-[var(--charcoal)]">
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

function DrawerField({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div>
      <p className="ds-label">{label}</p>
      <p className="break-all text-[var(--charcoal)]">{value ?? "—"}</p>
    </div>
  );
}

function DrawerMonoField({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div>
      <p className="ds-label">{label}</p>
      <p className="font-mono font-medium text-[var(--charcoal)]">{value ?? "—"}</p>
    </div>
  );
}

function DrawerSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-[var(--muted)]">{title}</p>
      {children}
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
        <div className="space-y-5 p-4 text-[13px]">
          <div>
            <p className="ds-label">URL</p>
            <p className="break-all text-[var(--charcoal)]">{row.address}</p>
          </div>

          <DrawerSection title="Crawl metrics">
            <div className="grid grid-cols-2 gap-3">
              <DrawerMonoField label="Status" value={row.status_code} />
              <DrawerMonoField label="Depth" value={formatDepth(row.crawl_depth)} />
              <DrawerMonoField label="Words" value={row.word_count} />
              <DrawerMonoField label="Response (ms)" value={row.response_time} />
              <DrawerMonoField label="Size (bytes)" value={row.size_bytes} />
              <DrawerMonoField label="Link score" value={row.link_score} />
            </div>
          </DrawerSection>

          <DrawerSection title="SEO on-page">
            <DrawerField label="Title" value={row.title} />
            <DrawerField label="Meta description" value={row.meta_description} />
            <DrawerField label="H1" value={row.h1} />
            <DrawerField label="Indexability" value={row.indexability} />
            <DrawerField label="Canonical" value={row.canonical} />
            <DrawerField label="Canonical link element" value={row.canonical_link_element} />
          </DrawerSection>

          <DrawerSection title="Technical">
            <div className="grid grid-cols-2 gap-3">
              <DrawerField label="Content type" value={row.content_type} />
              <DrawerField label="HTTP version" value={row.http_version} />
              <DrawerField
                label="In sitemap"
                value={row.in_sitemap === true ? "Yes" : row.in_sitemap === false ? "No" : null}
              />
            </div>
            <DrawerField label="Redirect URL" value={row.redirect_url} />
            <DrawerField label="Meta robots" value={row.meta_robots} />
            <DrawerField label="X-Robots-Tag" value={row.x_robots_tag} />
            <DrawerField label="Pagination" value={row.pagination_status} />
          </DrawerSection>

          <DrawerSection title="Link graph">
            <div className="grid grid-cols-2 gap-3">
              <DrawerMonoField label="Inlinks" value={row.inlinks} />
              <DrawerMonoField label="Outlinks" value={row.outlinks} />
            </div>
          </DrawerSection>
        </div>
      </div>
    </div>
  );
}
