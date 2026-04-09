"use client";

import { useMemo, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Alert } from "@/components/alert";
import type { CrawlJob } from "@/lib/api-types";
import { formatIssueTypeLabel } from "@/lib/issue-types";
import {
  buildIssuesTrendSeries,
  getDefaultIssueTypes,
  type IssuesTrendChartRow,
} from "@/lib/issues-trend";
import { useCrawlApi } from "@/lib/use-crawl-api";
import { useQuery } from "@tanstack/react-query";

const LINE_COLORS = [
  "var(--charcoal)",
  "var(--blue)",
  "var(--green)",
  "var(--purple)",
  "var(--pink)",
  "var(--yellow)",
  "var(--red)",
  "var(--gray-600)",
];

interface TrendTooltipProps {
  active?: boolean;
  label?: string;
  payload?: ReadonlyArray<{
    color?: string;
    dataKey?: string | number;
    value?: string | number;
    payload?: IssuesTrendChartRow;
  }>;
}

function TrendTooltip({ active, label, payload }: TrendTooltipProps) {
  if (!active || !payload || payload.length === 0) {
    return null;
  }

  const row = payload[0]?.payload;
  return (
    <div
      className="min-w-[220px] space-y-2 border bg-[var(--card)] p-3 shadow-lg"
      style={{ borderColor: "var(--border)", borderRadius: "var(--radius-sm)" }}
    >
      <div className="space-y-1">
        <p className="font-soehne text-[13px] font-semibold text-[var(--charcoal)]">
          {label}
        </p>
        {row?.targetUrl ? (
          <p className="break-all text-[11px] text-[var(--muted)]">{row.targetUrl}</p>
        ) : null}
      </div>
      <div className="space-y-1.5">
        {payload.map((item) => (
          <div
            key={String(item.dataKey)}
            className="flex items-center justify-between gap-4 text-[12px]"
          >
            <div className="flex items-center gap-2 text-[var(--charcoal)]">
              <span
                className="h-2.5 w-2.5 rounded-full"
                style={{ background: item.color ?? "var(--charcoal)" }}
              />
              <span>{formatIssueTypeLabel(String(item.dataKey ?? ""))}</span>
            </div>
            <span className="font-mono font-semibold text-[var(--charcoal)]">
              {item.value ?? 0}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

interface TrendLegendProps {
  hiddenIssueTypes: Set<string>;
  onToggle: (issueType: string) => void;
  payload?: ReadonlyArray<{
    color?: string;
    dataKey?: string | number;
    value?: string;
  }>;
}

function TrendLegend({ hiddenIssueTypes, onToggle, payload }: TrendLegendProps) {
  if (!payload || payload.length === 0) {
    return null;
  }

  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {payload.map((item) => {
        const issueType = String(item.dataKey ?? item.value ?? "");
        const hidden = hiddenIssueTypes.has(issueType);

        return (
          <button
            key={issueType}
            type="button"
            onClick={() => onToggle(issueType)}
            className="inline-flex items-center gap-2 rounded-full border px-3 py-1 text-[11px] font-medium transition-opacity"
            style={{
              borderColor: hidden ? "var(--border)" : item.color ?? "var(--border)",
              color: "var(--charcoal)",
              opacity: hidden ? 0.55 : 1,
            }}
            aria-pressed={!hidden}
            aria-label={`${hidden ? "Show" : "Hide"} ${formatIssueTypeLabel(issueType)} line`}
          >
            <span
              className="h-2.5 w-2.5 rounded-full"
              style={{ background: item.color ?? "var(--charcoal)" }}
            />
            <span>{formatIssueTypeLabel(issueType)}</span>
          </button>
        );
      })}
    </div>
  );
}

export interface IssuesTrendChartProps {
  completedCrawls: CrawlJob[];
}

export function IssuesTrendChart({ completedCrawls }: IssuesTrendChartProps) {
  const api = useCrawlApi();
  const [userSelectedIssueTypes, setUserSelectedIssueTypes] = useState<string[] | null>(null);
  const [hiddenIssueTypes, setHiddenIssueTypes] = useState<Set<string>>(new Set());

  const query = useQuery({
    queryKey: ["issues-trend"],
    queryFn: () => api.getIssuesTrend(),
  });

  const selectedIssueTypes = useMemo(() => {
    if (!query.data) {
      return [];
    }

    const selected =
      userSelectedIssueTypes ??
      getDefaultIssueTypes(query.data, Math.min(query.data.issue_types.length, 6));

    return selected.filter((issueType) => query.data.issue_types.includes(issueType));
  }, [query.data, userSelectedIssueTypes]);

  const visibleHiddenIssueTypes = useMemo(() => {
    const next = new Set<string>();
    for (const issueType of hiddenIssueTypes) {
      if (selectedIssueTypes.includes(issueType)) {
        next.add(issueType);
      }
    }
    return next;
  }, [hiddenIssueTypes, selectedIssueTypes]);

  const chartRows = useMemo(() => {
    if (!query.data) {
      return [];
    }

    return buildIssuesTrendSeries(query.data, completedCrawls);
  }, [completedCrawls, query.data]);

  const remainingIssueTypes = useMemo(() => {
    if (!query.data) {
      return [];
    }

    return query.data.issue_types.filter(
      (issueType) => !selectedIssueTypes.includes(issueType),
    );
  }, [query.data, selectedIssueTypes]);

  const selectedCount = selectedIssueTypes.length;

  if (query.isLoading) {
    return (
      <div className="ds-card flex items-center gap-3 py-10">
        <span className="ds-spinner ds-spinner--sm" />
        <span className="text-[13px] text-[var(--muted)]">Loading issue trend…</span>
      </div>
    );
  }

  if (query.isError) {
    return (
      <Alert variant="error" title="Could not load issue trend">
        Historical issue counts are unavailable right now. Try refreshing the page.
      </Alert>
    );
  }

  if (!query.data || query.data.issue_types.length === 0 || chartRows.length === 0) {
    return (
      <div className="ds-card space-y-2">
        <p className="ds-section-label !mb-0">Issues trend</p>
        <p className="text-[13px] text-[var(--muted)]">
          Completed crawls are available, but there are no recorded issue types to chart yet.
        </p>
      </div>
    );
  }

  return (
    <section className="ds-card space-y-5" aria-labelledby="issues-trend-title">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <p className="ds-section-label !mb-0">Issues trend</p>
          <h2
            id="issues-trend-title"
            className="font-soehne text-[18px] font-semibold tracking-[-0.02em] text-[var(--charcoal)]"
          >
            URL count by issue type across completed crawls
          </h2>
          <p className="max-w-3xl text-[13px] text-[var(--muted)]">
            Add issue types to compare how many URLs were affected in each crawl, then
            toggle lines from the legend to simplify the view.
          </p>
        </div>

        <div className="w-full max-w-[260px]">
          <label htmlFor="issues-trend-field" className="ds-label">
            Add issue type
          </label>
          <select
            id="issues-trend-field"
            defaultValue=""
            className="ds-select py-1.5 pl-2 pr-7 text-[12px]"
            disabled={remainingIssueTypes.length === 0}
            onChange={(event) => {
              const issueType = event.target.value;
              if (!issueType) {
                return;
              }

              setUserSelectedIssueTypes((current) => {
                const next = current ?? selectedIssueTypes;
                return next.includes(issueType) ? next : [...next, issueType];
              });
              event.target.value = "";
            }}
          >
            <option value="">Select an issue type…</option>
            {remainingIssueTypes.map((issueType) => (
              <option key={issueType} value={issueType}>
                {formatIssueTypeLabel(issueType)}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {selectedIssueTypes.map((issueType, index) => {
          const hidden = visibleHiddenIssueTypes.has(issueType);

          return (
            <button
              key={issueType}
              type="button"
              onClick={() => {
                setUserSelectedIssueTypes((current) =>
                  (current ?? selectedIssueTypes).filter((value) => value !== issueType),
                );
              }}
              className="inline-flex items-center gap-2 rounded-full border px-3 py-1 text-[11px] font-medium"
              style={{
                borderColor: LINE_COLORS[index % LINE_COLORS.length],
                color: hidden ? "var(--muted)" : "var(--charcoal)",
                background: hidden ? "var(--light-grey)" : "transparent",
              }}
              aria-label={`Remove ${formatIssueTypeLabel(issueType)} from the chart`}
              title={hidden ? "Currently hidden in the legend" : "Remove from the chart"}
            >
              <span
                className="h-2.5 w-2.5 rounded-full"
                style={{ background: LINE_COLORS[index % LINE_COLORS.length] }}
              />
              <span>{formatIssueTypeLabel(issueType)}</span>
              <span aria-hidden>×</span>
            </button>
          );
        })}
        {selectedCount === 0 ? (
          <p className="text-[12px] text-[var(--muted)]">
            Choose at least one issue type to draw the trend line.
          </p>
        ) : null}
      </div>

      {selectedCount > 0 ? (
        <div className="space-y-2">
          <div className="h-[360px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={chartRows}
                margin={{ top: 8, right: 16, left: 8, bottom: 0 }}
              >
                <CartesianGrid
                  stroke="var(--border-faded)"
                  strokeDasharray="3 3"
                  vertical={false}
                />
                <XAxis
                  dataKey="label"
                  minTickGap={24}
                  tickLine={false}
                  axisLine={{ stroke: "var(--border)" }}
                  tick={{ fill: "var(--muted)", fontSize: 11 }}
                />
                <YAxis
                  allowDecimals={false}
                  tickLine={false}
                  axisLine={false}
                  tick={{ fill: "var(--muted)", fontSize: 11 }}
                />
                <Tooltip content={<TrendTooltip />} />
                <Legend
                  verticalAlign="bottom"
                  content={
                    <TrendLegend
                      hiddenIssueTypes={visibleHiddenIssueTypes}
                      onToggle={(issueType) => {
                        setHiddenIssueTypes((current) => {
                          const next = new Set(current);
                          if (next.has(issueType)) {
                            next.delete(issueType);
                          } else {
                            next.add(issueType);
                          }
                          return next;
                        });
                      }}
                    />
                  }
                />
                {selectedIssueTypes.map((issueType, index) => (
                  <Line
                    key={issueType}
                    type="monotone"
                    dataKey={issueType}
                    name={formatIssueTypeLabel(issueType)}
                    stroke={LINE_COLORS[index % LINE_COLORS.length]}
                    strokeWidth={2}
                    dot={{ r: 2 }}
                    activeDot={{ r: 4 }}
                    hide={visibleHiddenIssueTypes.has(issueType)}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>

          <p className="text-[12px] text-[var(--muted)]">
            Each point shows the number of URLs with that issue in the crawl.
          </p>
        </div>
      ) : null}
    </section>
  );
}
