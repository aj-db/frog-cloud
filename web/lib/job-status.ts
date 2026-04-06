import type { JobStatus } from "./api-types";

export function jobStatusLabel(status: JobStatus | string): string {
  switch (status) {
    case "queued":
    case "provisioning":
      return "Pending";
    case "running":
    case "extracting":
      return "Running";
    case "loading":
      return "Loading";
    case "complete":
      return "Completed";
    case "failed":
      return "Failed";
    case "cancelled":
      return "Cancelled";
    default:
      return status;
  }
}

export function jobIsActive(status: JobStatus | string): boolean {
  return (
    status === "queued" ||
    status === "provisioning" ||
    status === "running" ||
    status === "extracting" ||
    status === "loading"
  );
}
