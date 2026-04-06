import type { JobStatus } from "@/lib/api-types";
import { jobStatusLabel, jobIsActive } from "@/lib/job-status";
import { Badge, type BadgeVariant } from "@/components/badge";

function variantForStatus(status: JobStatus | string): BadgeVariant {
  if (status === "complete") return "success";
  if (status === "failed") return "error";
  if (status === "loading") return "info";
  if (jobIsActive(status)) return "warning";
  return "neutral";
}

export function CrawlStatusBadge({ status }: { status: JobStatus | string }) {
  return <Badge variant={variantForStatus(status)}>{jobStatusLabel(status)}</Badge>;
}
