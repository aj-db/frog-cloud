export interface PollSnapshot {
  status: string;
  progress_pct: number | null;
  error: string | null;
  last_heartbeat_at?: string | null;
  urls_crawled?: number | null;
  status_message?: string | null;
  extraction_partial?: boolean;
}

export interface PollControllerOptions {
  /** Polling interval when job is not terminal */
  intervalMs?: number;
  /** Time without a successful fetch before marking stale */
  staleAfterMs?: number;
  /** Called on every successful poll */
  onUpdate?: (snapshot: PollSnapshot & { stale: boolean }) => void;
  /** Called when a poll request throws */
  onPollError?: (err: unknown) => void;
  /** Status values that stop polling */
  isTerminal?: (status: string) => boolean;
}

const defaultTerminal = (status: string) =>
  status === "complete" || status === "failed" || status === "cancelled";

/**
 * Polls job status on an interval. Tracks last successful response time for stale detection.
 * Returns `stop()` to clear timers.
 */
export function startJobPoll(
  fetchSnapshot: () => Promise<PollSnapshot>,
  options: PollControllerOptions = {},
): { stop: () => void } {
  const intervalMs = options.intervalMs ?? 3500;
  const staleAfterMs = options.staleAfterMs ?? 45_000;
  const isTerminal = options.isTerminal ?? defaultTerminal;

  let pollTimer: ReturnType<typeof setInterval> | null = null;
  let staleTimer: ReturnType<typeof setInterval> | null = null;
  let stopped = false;
  let lastSuccessAt = Date.now();

  const emitStaleCheck = () => {
    if (stopped) return;
    const stale = Date.now() - lastSuccessAt > staleAfterMs;
    if (stale) {
      options.onUpdate?.({
        status: "unknown",
        progress_pct: null,
        error: null,
        stale: true,
      });
    }
  };

  const run = async () => {
    if (stopped) return;
    try {
      const snapshot = await fetchSnapshot();
      lastSuccessAt = Date.now();
      options.onUpdate?.({ ...snapshot, stale: false });
      if (isTerminal(snapshot.status)) {
        stop();
      }
    } catch (err) {
      options.onPollError?.(err);
      emitStaleCheck();
    }
  };

  const stop = () => {
    stopped = true;
    if (pollTimer) clearInterval(pollTimer);
    if (staleTimer) clearInterval(staleTimer);
    pollTimer = null;
    staleTimer = null;
  };

  void run();
  pollTimer = setInterval(run, intervalMs);
  staleTimer = setInterval(emitStaleCheck, 2000);

  return { stop };
}
