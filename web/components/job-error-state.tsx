"use client";

import { Alert } from "@/components/alert";
import { Button } from "@/components/button";

export interface JobErrorStateProps {
  message: string;
  failedAt: string | null;
  onRetry: () => void;
  onDuplicate: () => void;
  busy?: boolean;
}

export function JobErrorState({
  message,
  failedAt,
  onRetry,
  onDuplicate,
  busy = false,
}: JobErrorStateProps) {
  const when = failedAt
    ? new Intl.DateTimeFormat(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(new Date(failedAt))
    : null;

  return (
    <div className="space-y-4">
      <Alert variant="error" title="This crawl failed">
        <p className="whitespace-pre-wrap">{message}</p>
        {when ? (
          <p className="mt-2 font-mono text-[12px] text-[var(--muted)]">Failed at {when}</p>
        ) : null}
      </Alert>
      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="primary" loading={busy} onClick={onRetry}>
          Re-run crawl
        </Button>
        <Button type="button" variant="secondary" disabled={busy} onClick={onDuplicate}>
          Duplicate job
        </Button>
      </div>
    </div>
  );
}
