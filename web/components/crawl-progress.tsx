"use client";

import { useEffect, useState } from "react";
import { Alert } from "@/components/alert";
import { Button } from "@/components/button";
import type { PollSnapshot } from "@/lib/progress";
import { startJobPoll } from "@/lib/progress";
import type { CrawlJob } from "@/lib/api-types";
import { jobIsActive, jobStatusLabel } from "@/lib/job-status";
import { useCrawlApi } from "@/lib/use-crawl-api";

type Snapshot = PollSnapshot & {
  stale: boolean;
  worker_stale: boolean;
  heartbeat_label: string | null;
  extraction_partial: boolean;
};

const HEARTBEAT_STALE_MS = 45_000;
const HEARTBEAT_STALE_EXTRACTION_MS = 360_000;

function formatHeartbeatAge(
  iso: string | null | undefined,
  nowMs: number,
): string | null {
  if (!iso) return null;
  const deltaMs = nowMs - new Date(iso).getTime();
  if (!Number.isFinite(deltaMs) || deltaMs < 0) return null;

  const seconds = Math.round(deltaMs / 1000);
  if (seconds < 5) return "just now";
  if (seconds < 60) return `${seconds}s ago`;

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.floor(minutes / 60);
  return `${hours}h ago`;
}

export function CrawlProgress({
  jobId,
  onJobUpdate,
}: {
  jobId: string;
  onJobUpdate?: (job: CrawlJob) => void;
}) {
  const api = useCrawlApi();
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [pollError, setPollError] = useState(false);

  useEffect(() => {
    const { stop } = startJobPoll(
      async () => {
        const job = await api.getCrawl(jobId);
        onJobUpdate?.(job);
        return {
          status: job.status,
          progress_pct: job.progress_pct,
          error: job.error,
          last_heartbeat_at: job.last_heartbeat_at,
          urls_crawled: job.urls_crawled,
          status_message: job.status_message,
          extraction_partial: job.extraction_partial ?? false,
        };
      },
      {
        intervalMs: 3500,
        staleAfterMs: 45_000,
        onUpdate: (s) => {
          const nowMs = Date.now();
          const heartbeatLabel = formatHeartbeatAge(s.last_heartbeat_at, nowMs);
          const isExtracting = s.status === "extracting" || s.status === "loading";
          const staleThreshold = isExtracting ? HEARTBEAT_STALE_EXTRACTION_MS : HEARTBEAT_STALE_MS;
          const workerStale =
            jobIsActive(s.status) &&
            Boolean(s.last_heartbeat_at) &&
            nowMs - new Date(s.last_heartbeat_at ?? 0).getTime() > staleThreshold;
          setSnapshot({
            ...s,
            worker_stale: workerStale,
            heartbeat_label: heartbeatLabel,
            extraction_partial: s.extraction_partial ?? false,
          });
          if (!s.stale) setPollError(false);
        },
        onPollError: () => setPollError(true),
      },
    );
    return stop;
  }, [api, jobId, onJobUpdate]);

  if (!snapshot && !pollError) {
    return (
      <div className="ds-card flex items-center gap-3">
        <span className="ds-spinner ds-spinner--sm" aria-hidden />
        <span className="text-[13px] font-medium text-[var(--muted)]">
          Checking job status…
        </span>
      </div>
    );
  }

  const active = snapshot ? jobIsActive(snapshot.status) : false;
  const showSpinner =
    active &&
    (snapshot?.status === "running" ||
      snapshot?.status === "queued" ||
      snapshot?.status === "provisioning" ||
      snapshot?.status === "extracting");

  const pct =
    snapshot?.progress_pct != null && !Number.isNaN(snapshot.progress_pct)
      ? Math.min(100, Math.max(0, snapshot.progress_pct))
      : null;

  return (
    <div className="space-y-3">
      {(snapshot?.stale || pollError) && (
        <Alert variant="warning" title="Data may be stale">
          <div className="flex flex-wrap items-center gap-2">
            <span>
              We could not refresh this job recently. You can retry manually.
            </span>
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                setPollError(false);
                void api.getCrawl(jobId).then((job) => {
                  const nowMs = Date.now();
                  const heartbeatLabel = formatHeartbeatAge(job.last_heartbeat_at, nowMs);
                  const isExtracting = job.status === "extracting" || job.status === "loading";
                  const staleThreshold = isExtracting ? HEARTBEAT_STALE_EXTRACTION_MS : HEARTBEAT_STALE_MS;
                  setSnapshot({
                    status: job.status,
                    progress_pct: job.progress_pct,
                    error: job.error,
                    last_heartbeat_at: job.last_heartbeat_at,
                    stale: false,
                    worker_stale:
                      jobIsActive(job.status) &&
                      Boolean(job.last_heartbeat_at) &&
                      nowMs - new Date(job.last_heartbeat_at ?? 0).getTime() > staleThreshold,
                    heartbeat_label: heartbeatLabel,
                    extraction_partial: job.extraction_partial ?? false,
                  });
                  onJobUpdate?.(job);
                });
              }}
            >
              Refresh now
            </Button>
          </div>
        </Alert>
      )}

      {snapshot?.worker_stale && !pollError && (
        <Alert variant="warning" title="Worker heartbeat is stale">
          {snapshot.status === "extracting" || snapshot.status === "loading"
            ? "The extraction process has not reported a heartbeat for several minutes. A watchdog will automatically recover if it remains unresponsive."
            : "The API is still reachable, but this crawl has not reported a worker heartbeat recently. It may be stalled."}
        </Alert>
      )}

      {snapshot?.status === "complete" && snapshot.extraction_partial && (
        <Alert variant="warning" title="Partial results">
          This crawl completed with partial data. Some issue tabs may have been capped or
          skipped due to volume limits or timeouts. Review the extraction details for specifics.
        </Alert>
      )}

      <div className="ds-card">
        <div className="flex flex-wrap items-center gap-3">
          {snapshot?.status === "complete" ? (
            <span
              className="inline-flex h-8 w-8 items-center justify-center rounded-full text-[var(--green)]"
              style={{ background: "var(--green-bg)" }}
              aria-label="Completed"
            >
              ✓
            </span>
          ) : showSpinner ? (
            <span className="ds-spinner" aria-hidden />
          ) : null}

          <div>
            <p className="font-soehne text-[14px] font-semibold text-[var(--charcoal)]">
              {snapshot ? jobStatusLabel(snapshot.status) : "Unknown"}
            </p>
            <p className="text-[12px] text-[var(--muted)]">
              {snapshot?.status_message
                ? snapshot.status_message
                : snapshot?.status === "extracting"
                  ? "Reading crawl results from engine…"
                  : snapshot?.status === "loading"
                    ? "Loading rows into the database…"
                    : snapshot?.status === "running"
                      ? snapshot.urls_crawled
                        ? `Crawling — ${snapshot.urls_crawled.toLocaleString()} URLs processed`
                        : "Crawl is running…"
                      : snapshot?.status === "queued"
                        ? "Job is queued and will start shortly."
                        : snapshot?.status === "provisioning"
                          ? "Provisioning worker resources…"
                          : null}
            </p>
            {active && snapshot?.heartbeat_label ? (
              <p className="mt-1 font-mono text-[11px] text-[var(--muted)]">
                Last worker heartbeat: {snapshot.heartbeat_label}
              </p>
            ) : null}
          </div>
        </div>

        {pct != null && active ? (
          <div className="mt-4">
            <div
              className="h-2 w-full overflow-hidden rounded-[var(--radius-pill)]"
              style={{ background: "var(--light-grey)", border: "1px solid var(--border-faded)" }}
            >
              <div
                className="h-full rounded-[var(--radius-pill)] transition-all"
                style={{
                  width: `${pct}%`,
                  background: "var(--charcoal)",
                }}
              />
            </div>
            <p className="mt-1 font-mono text-[11px] font-medium text-[var(--muted)]">
              {pct}%{snapshot?.urls_crawled ? ` · ${snapshot.urls_crawled.toLocaleString()} URLs` : ""}
            </p>
          </div>
        ) : null}
      </div>
    </div>
  );
}
