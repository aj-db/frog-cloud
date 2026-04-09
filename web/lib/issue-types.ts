const STATUS_ISSUE_RE = /^status_(\d+)$/;

export function parseStatusIssueCode(issueType: string): number | null {
  const match = issueType.match(STATUS_ISSUE_RE);
  if (!match) {
    return null;
  }
  const parsed = Number(match[1]);
  return Number.isFinite(parsed) ? parsed : null;
}

export function formatIssueTypeLabel(issueType: string): string {
  const statusCode = parseStatusIssueCode(issueType);
  if (statusCode != null) {
    return `HTTP ${statusCode}`;
  }
  return issueType.replace(/_/g, " ");
}

export function formatStatusCodeLabel(statusCode: number | null): string {
  return statusCode == null ? "No status" : `HTTP ${statusCode}`;
}

export function statusCodeFilterKey(statusCode: number | null): string {
  return statusCode == null ? "__empty__" : String(statusCode);
}
