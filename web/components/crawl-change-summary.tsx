"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Badge } from "@/components/badge";
import { StatCard } from "@/components/stat-card";
import type { CrawlComparisonSummary, CrawlJob } from "@/lib/api-types";
import { useCrawlApi } from "@/lib/use-crawl-api";

function formatDelta(current: number, previous: number): { value: string; positive: boolean } {
  const diff = current - previous;
  const sign = diff > 0 ? "+" : "";
  return { value: `${sign}${diff} vs previous`, positive: diff <= 0 };
}

const STATUS_COLORS: Record<string, string> = {
  "2xx": "var(--green)",
  "3xx": "var(--blue)",
  "4xx": "var(--yellow)",
  "5xx": "var(--red)",
};

interface DonutSlice {
  label: string;
  value: number;
  prev: number | null;
  color: string;
}

function StatusDonut({ slices, size = 120, stroke = 18 }: { slices: DonutSlice[]; size?: number; stroke?: number }) {
  const [hovered, setHovered] = useState<string | null>(null);
  const total = slices.reduce((s, d) => s + d.value, 0);
  if (total === 0) return null;

  const r = (size - stroke) / 2;
  const c = Math.PI * 2 * r;

  const arcs = slices.reduce<{ label: string; color: string; value: number; dashLen: number; gap: number; offset: number }[]>(
    (acc, s) => {
      if (s.value === 0) return acc;
      const dashLen = (s.value / total) * c;
      const prevOffset = acc.length > 0 ? acc[acc.length - 1].offset + acc[acc.length - 1].dashLen : 0;
      acc.push({ ...s, dashLen, gap: c - dashLen, offset: prevOffset });
      return acc;
    },
    [],
  );

  return (
    <div className="flex items-center gap-6">
      <div className="relative shrink-0" style={{ width: size, height: size }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90">
          {arcs.map((s) => {
            const isHovered = hovered === s.label;
            return (
              <circle
                key={s.label}
                cx={size / 2}
                cy={size / 2}
                r={r}
                fill="none"
                stroke={s.color}
                strokeWidth={isHovered ? stroke + 4 : stroke}
                strokeDasharray={`${s.dashLen} ${s.gap}`}
                strokeDashoffset={-s.offset}
                className="transition-all duration-150"
                style={{ opacity: hovered && !isHovered ? 0.35 : 1 }}
                onMouseEnter={() => setHovered(s.label)}
                onMouseLeave={() => setHovered(null)}
              />
            );
          })}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          {hovered ? (
            <>
              <span className="font-soehne text-[18px] font-semibold leading-tight text-[var(--charcoal)]">
                {slices.find((s) => s.label === hovered)?.value}
              </span>
              <span className="text-[10px] font-medium text-[var(--muted)]">{hovered}</span>
            </>
          ) : (
            <>
              <span className="font-soehne text-[18px] font-semibold leading-tight text-[var(--charcoal)]">{total}</span>
              <span className="text-[10px] font-medium text-[var(--muted)]">total</span>
            </>
          )}
        </div>
      </div>

      <div className="grid gap-1.5">
        {slices.map((s) => {
          const diff = s.prev != null ? s.value - s.prev : null;
          return (
            <div
              key={s.label}
              className="flex items-center gap-2 rounded px-1.5 py-0.5 transition-colors"
              style={{ background: hovered === s.label ? "var(--light-grey)" : undefined }}
              onMouseEnter={() => setHovered(s.label)}
              onMouseLeave={() => setHovered(null)}
            >
              <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: s.color }} />
              <span className="text-[12px] font-medium text-[var(--charcoal)]">{s.label}</span>
              <span className="font-mono text-[12px] text-[var(--charcoal)]">{s.value}</span>
              {diff != null && diff !== 0 ? (
                <span
                  className="font-mono text-[11px] font-semibold"
                  style={{ color: diff > 0 ? "var(--red)" : "var(--green)" }}
                >
                  {diff > 0 ? `+${diff}` : diff}
                </span>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function SummaryContent({
  summary,
  baselines,
  compareJobId,
  onCompareChange,
  activeIssueType,
  onIssueSelect,
}: {
  summary: CrawlComparisonSummary;
  baselines: CrawlJob[];
  compareJobId: string | undefined;
  onCompareChange: (id: string | undefined) => void;
  activeIssueType: string | null;
  onIssueSelect?: (issueType: string | null) => void;
}) {
  const { current, previous } = summary;
  const hasPrevious = previous != null;

  const avgRtCurrent = current.avg_response_time_ms != null ? Math.round(current.avg_response_time_ms) : null;
  const avgRtPrevious = previous?.avg_response_time_ms != null ? Math.round(previous.avg_response_time_ms) : null;
  const hasSitemapData = current.sitemap_coverage.in_sitemap > 0 || current.sitemap_coverage.not_in_sitemap > 0;
  const previousHasSitemapData = previous != null && (previous.sitemap_coverage.in_sitemap > 0 || previous.sitemap_coverage.not_in_sitemap > 0);

  const cov = current.sitemap_coverage;
  const sitemapTotal = cov.in_sitemap + cov.not_in_sitemap;
  const sitemapPct = sitemapTotal > 0 ? Math.round((cov.in_sitemap / sitemapTotal) * 100) : 0;

  const issueRows: { type: string; prev: number | null; curr: number | null; delta: number; status: "new" | "resolved" | "changed" }[] = [];
  const seen = new Set<string>();
  for (const t of summary.new_issue_types) {
    const d = summary.issue_type_deltas.find((x) => x.issue_type === t);
    issueRows.push({ type: t, prev: null, curr: d?.current_count ?? null, delta: d?.delta ?? 0, status: "new" });
    seen.add(t);
  }
  for (const t of summary.resolved_issue_types) {
    const d = summary.issue_type_deltas.find((x) => x.issue_type === t);
    issueRows.push({ type: t, prev: d?.previous_count ?? null, curr: 0, delta: d?.delta ?? 0, status: "resolved" });
    seen.add(t);
  }
  for (const d of summary.issue_type_deltas) {
    if (seen.has(d.issue_type)) continue;
    issueRows.push({ type: d.issue_type, prev: d.previous_count, curr: d.current_count, delta: d.delta, status: "changed" });
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-2 text-[12px] text-[var(--charcoal)]">
        <span className="shrink-0 font-medium text-[var(--muted)]">Compared to</span>
        <select
          value={compareJobId ?? ""}
          onChange={(e) => onCompareChange(e.target.value ? e.target.value : undefined)}
          className="ds-select py-1.5 pl-2 pr-7 text-[12px] max-w-[260px]"
        >
          <option value="">previous crawl (auto)</option>
          {baselines.map((b) => (
            <option key={b.id} value={b.id}>
              {new Date(b.completed_at || b.started_at || "").toLocaleDateString()} — {b.id.slice(0, 8)}
            </option>
          ))}
        </select>
        {hasPrevious ? (
          <Link
            href={`/crawls/${previous.job_id}`}
            className="shrink-0 text-[12px] font-medium text-[var(--muted)] hover:underline"
          >
            View crawl
          </Link>
        ) : null}
      </div>

      {!hasPrevious ? (
        <p className="text-[12px] text-[var(--muted)]">
          First crawl in this series — no previous data to compare.
        </p>
      ) : null}

      <div className="grid gap-3 grid-cols-2">
        <StatCard
          label="Pages crawled"
          value={current.urls_crawled}
          delta={
            hasPrevious
              ? formatDelta(current.urls_crawled, previous.urls_crawled)
              : undefined
          }
        />
        <StatCard
          label="Issues"
          value={current.issues_count}
          delta={
            hasPrevious
              ? {
                  ...formatDelta(current.issues_count, previous.issues_count),
                  positive: current.issues_count <= previous.issues_count,
                }
              : undefined
          }
        />
        <StatCard
          label="Avg response (ms)"
          value={avgRtCurrent ?? "—"}
          delta={
            hasPrevious && avgRtCurrent != null && avgRtPrevious != null
              ? {
                  ...formatDelta(avgRtCurrent, avgRtPrevious),
                  positive: avgRtCurrent <= avgRtPrevious,
                }
              : undefined
          }
        />
        {hasSitemapData ? (
          <div className="ds-card flex flex-col justify-between">
            <div>
              <p
                className="mb-2 text-[10.5px] font-semibold uppercase tracking-[0.07em]"
                style={{ color: "var(--muted)" }}
              >
                Missing from sitemap
              </p>
              <div className="flex items-baseline gap-2">
                <p
                  className="font-soehne text-2xl font-semibold tracking-[-0.03em] sm:text-[28px]"
                  style={{ color: cov.not_in_sitemap > 0 ? "var(--red)" : "var(--charcoal)", lineHeight: "1" }}
                >
                  {cov.not_in_sitemap}
                </p>
                {hasPrevious && previousHasSitemapData ? (
                  <p
                    className="text-[11px] font-semibold"
                    style={{
                      color: cov.not_in_sitemap <= previous.sitemap_coverage.not_in_sitemap ? "var(--green)" : "var(--red)",
                    }}
                  >
                    {formatDelta(cov.not_in_sitemap, previous.sitemap_coverage.not_in_sitemap).value}
                  </p>
                ) : null}
              </div>
            </div>
            <div className="mt-3 space-y-1.5">
              <div className="flex items-center justify-between text-[11px] font-medium text-[var(--muted)]">
                <span>{sitemapPct}% coverage</span>
              </div>
              <div
                className="h-1.5 w-full overflow-hidden rounded-full"
                style={{ background: "var(--light-grey)" }}
              >
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${sitemapPct}%`,
                    background: sitemapPct === 100 ? "var(--green)" : "var(--yellow)",
                  }}
                />
              </div>
            </div>
          </div>
        ) : (
          <StatCard
            label="Indexable"
            value={current.indexability.indexable}
            delta={
              hasPrevious
                ? formatDelta(current.indexability.indexable, previous.indexability.indexable)
                : undefined
            }
          />
        )}
      </div>

      <div className="ds-card space-y-3">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-[var(--muted)]">
          Status code distribution
        </p>
        <StatusDonut
          slices={[
            { label: "2xx", value: current.status_codes.status_2xx, prev: previous?.status_codes.status_2xx ?? null, color: STATUS_COLORS["2xx"] },
            { label: "3xx", value: current.status_codes.status_3xx, prev: previous?.status_codes.status_3xx ?? null, color: STATUS_COLORS["3xx"] },
            { label: "4xx", value: current.status_codes.status_4xx, prev: previous?.status_codes.status_4xx ?? null, color: STATUS_COLORS["4xx"] },
            { label: "5xx", value: current.status_codes.status_5xx, prev: previous?.status_codes.status_5xx ?? null, color: STATUS_COLORS["5xx"] },
          ]}
        />
      </div>

      {issueRows.length > 0 ? (
        <div className="ds-table-wrap">
          <table className="ds-table text-[12px]">
            <thead>
              <tr>
                <th className="text-left">Issue type</th>
                <th className="text-right w-[72px]">Previous</th>
                <th className="text-right w-[72px]">Current</th>
                <th className="text-right w-[72px]">Change</th>
                <th className="text-center w-[72px]">Status</th>
              </tr>
            </thead>
            <tbody>
              {issueRows.map((r) => (
                <tr
                  key={r.type}
                  className="cursor-pointer transition-colors hover:bg-[var(--light-grey)]"
                  style={{ background: activeIssueType === r.type ? "var(--light-grey)" : undefined }}
                  onClick={() => onIssueSelect?.(activeIssueType === r.type ? null : r.type)}
                  title={`Filter pages by "${r.type.replace(/_/g, " ")}"`}
                >
                  <td className="text-[var(--charcoal)]">{r.type.replace(/_/g, " ")}</td>
                  <td className="text-right font-mono text-[var(--muted)]">{r.prev ?? "—"}</td>
                  <td className="text-right font-mono">{r.curr ?? "—"}</td>
                  <td className="text-right font-mono font-semibold" style={{ color: r.delta > 0 ? "var(--red)" : r.delta < 0 ? "var(--green)" : "var(--muted)" }}>
                    {r.delta > 0 ? `+${r.delta}` : r.delta === 0 ? "—" : r.delta}
                  </td>
                  <td className="text-center">
                    <Badge variant={r.status === "new" ? "error" : r.status === "resolved" ? "success" : "info"}>
                      {r.status}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}

export interface CrawlChangeSummaryProps {
  jobId: string;
  targetUrl: string;
  enabled: boolean;
  activeIssueType?: string | null;
  onIssueSelect?: (issueType: string | null) => void;
}

export function CrawlChangeSummary({ jobId, targetUrl, enabled, activeIssueType = null, onIssueSelect }: CrawlChangeSummaryProps) {
  const api = useCrawlApi();
  const [compareJobId, setCompareJobId] = useState<string | undefined>();

  const baselinesQuery = useQuery({
    queryKey: ["crawls", { target_url: targetUrl, status: "complete" }],
    queryFn: () => api.getCrawls({ target_url: targetUrl, status: "complete" }),
    enabled: enabled && !!targetUrl,
  });

  const query = useQuery({
    queryKey: ["crawl-summary", jobId, compareJobId],
    queryFn: () => api.getCrawlSummary(jobId, compareJobId),
    enabled,
    retry: false,
  });

  if (query.isLoading) {
    return (
      <div className="ds-card flex items-center gap-2 py-6 text-[var(--muted)]">
        <span className="ds-spinner ds-spinner--sm" />
        <span className="text-[12px]">Loading comparison…</span>
      </div>
    );
  }

  if (query.isError) {
    return null;
  }

  if (!query.data) return null;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b pb-3" style={{ borderColor: "var(--border-faded)" }}>
        <p className="ds-section-label !mb-0">Crawl-to-crawl comparison</p>
      </div>
      <SummaryContent
        summary={query.data}
        baselines={baselinesQuery.data?.filter(b => b.id !== jobId) ?? []}
        compareJobId={compareJobId}
        onCompareChange={setCompareJobId}
        activeIssueType={activeIssueType}
        onIssueSelect={onIssueSelect}
      />
    </div>
  );
}
