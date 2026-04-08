"use client";

import { useMemo } from "react";
import type { CrawlIssueRow, IssueSeverity } from "@/lib/api-types";
import { Badge } from "@/components/badge";

export interface IssueFilter {
  issue_type: string;
  severity?: IssueSeverity;
}

interface IssueSummaryProps {
  issues: CrawlIssueRow[];
  activeFilter: IssueFilter | null;
  onSelect: (filter: IssueFilter | null) => void;
}

export function IssueSummary({ issues, activeFilter, onSelect }: IssueSummaryProps) {
  const groups = useMemo(() => {
    const map = new Map<
      string,
      { errors: number; warnings: number; infos: number }
    >();
    for (const issue of issues) {
      const cur = map.get(issue.issue_type) ?? { errors: 0, warnings: 0, infos: 0 };
      if (issue.severity === "error") cur.errors += 1;
      else if (issue.severity === "warning") cur.warnings += 1;
      else cur.infos += 1;
      map.set(issue.issue_type, cur);
    }
    return Array.from(map.entries()).sort((a, b) => {
      const total = (x: [string, { errors: number; warnings: number; infos: number }]) =>
        x[1].errors + x[1].warnings + x[1].infos;
      return total(b) - total(a);
    });
  }, [issues]);

  if (groups.length === 0) {
    return (
      <div className="ds-card">
        <p className="ds-section-label mb-1">Issues</p>
        <p className="text-[13px] text-[var(--muted)]">No issues recorded for this crawl.</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <p className="ds-section-label">Issues by type</p>
      <div className="grid gap-2">
        {groups.map(([type, counts]) => {
          const selected = activeFilter?.issue_type === type;
          return (
            <button
              key={type}
              type="button"
              onClick={() =>
                selected ? onSelect(null) : onSelect({ issue_type: type })
              }
              className="ds-card text-left transition-colors"
              style={{
                outline: selected ? "2px solid var(--charcoal)" : undefined,
                outlineOffset: 2,
              }}
            >
              <p className="font-soehne text-[13px] font-semibold text-[var(--charcoal)]">
                {type.replace(/_/g, " ")}
              </p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {counts.errors > 0 ? (
                  <Badge variant="error">{counts.errors} errors</Badge>
                ) : null}
                {counts.warnings > 0 ? (
                  <Badge variant="warning">{counts.warnings} warnings</Badge>
                ) : null}
                {counts.infos > 0 ? (
                  <Badge variant="info">{counts.infos} info</Badge>
                ) : null}
              </div>
              <p className="mt-2 text-[11px] font-medium text-[var(--muted)]">
                {selected ? "Click to clear table filter" : "Click to filter pages table"}
              </p>
            </button>
          );
        })}
      </div>
    </div>
  );
}
