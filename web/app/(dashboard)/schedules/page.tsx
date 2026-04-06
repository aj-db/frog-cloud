"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Alert } from "@/components/alert";
import { Badge } from "@/components/badge";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { cronHint } from "@/lib/cron-hint";
import type { ScheduledCrawl } from "@/lib/api-types";
import { useCrawlApi } from "@/lib/use-crawl-api";

export default function SchedulesPage() {
  const api = useCrawlApi();
  const queryClient = useQueryClient();
  const schedulesQuery = useQuery({
    queryKey: ["schedules"],
    queryFn: () => api.getSchedules(),
  });
  const profilesQuery = useQuery({
    queryKey: ["profiles"],
    queryFn: () => api.getCrawlProfiles(),
  });

  const [editing, setEditing] = useState<ScheduledCrawl | null>(null);
  const [creating, setCreating] = useState(false);
  const [targetUrl, setTargetUrl] = useState("");
  const [profileId, setProfileId] = useState("");
  const [cronExpression, setCronExpression] = useState("0 0 * * *");
  const [timezone, setTimezone] = useState(
    Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
  );

  const profiles = useMemo(() => profilesQuery.data ?? [], [profilesQuery.data]);

  const resetForm = () => {
    setEditing(null);
    setCreating(false);
    setTargetUrl("");
    setProfileId("");
    setCronExpression("0 0 * * *");
    setTimezone(Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC");
  };

  const createMutation = useMutation({
    mutationFn: () =>
      api.createSchedule({
        target_url: targetUrl.trim(),
        profile_id: profileId,
        cron_expression: cronExpression.trim(),
        timezone: timezone.trim(),
        is_active: true,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["schedules"] });
      resetForm();
    },
  });

  const updateMutation = useMutation({
    mutationFn: (patch: Parameters<typeof api.updateSchedule>[1]) => {
      if (!editing) throw new Error("No schedule");
      return api.updateSchedule(editing.id, patch);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["schedules"] });
      resetForm();
    },
  });

  const patchMutation = useMutation({
    mutationFn: ({
      id,
      patch,
    }: {
      id: string;
      patch: Parameters<typeof api.updateSchedule>[1];
    }) => api.updateSchedule(id, patch),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["schedules"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteSchedule(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["schedules"] });
      resetForm();
    },
  });

  const startEdit = (s: ScheduledCrawl) => {
    setEditing(s);
    setCreating(false);
    setTargetUrl(s.target_url);
    setProfileId(s.profile_id);
    setCronExpression(s.cron_expression);
    setTimezone(s.timezone);
  };

  const busy =
    createMutation.isPending ||
    updateMutation.isPending ||
    deleteMutation.isPending ||
    patchMutation.isPending;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="ds-section-label mb-1">Automation</p>
          <h1 className="ds-page-title">Schedules</h1>
          <p className="mt-1 text-[13px] text-[var(--muted)]">
            Recurring crawls with timezone-aware cron expressions. Pausing stops the next run
            until re-enabled.
          </p>
        </div>
        <Button type="button" variant="primary" onClick={() => { resetForm(); setCreating(true); }} disabled={creating}>
          New schedule
        </Button>
      </div>

      {schedulesQuery.isError ? (
        <Alert variant="error" title="Could not load schedules">
          Confirm the schedules API is available for this tenant.
        </Alert>
      ) : null}

      {creating || editing ? (
        <form
          className="ds-card ds-card--lg space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            if (editing) {
              updateMutation.mutate({
                target_url: targetUrl.trim(),
                profile_id: profileId,
                cron_expression: cronExpression.trim(),
                timezone: timezone.trim(),
              });
            } else {
              createMutation.mutate();
            }
          }}
        >
          <p className="font-soehne text-[14px] font-semibold text-[var(--charcoal)]">
            {editing ? "Edit schedule" : "Create schedule"}
          </p>
          <Input
            label="Target URL"
            value={targetUrl}
            onChange={(e) => setTargetUrl(e.target.value)}
            required
            placeholder="https://example.com"
          />
          <div>
            <label className="ds-label" htmlFor="sched-profile">
              Profile
            </label>
            <select
              id="sched-profile"
              className="ds-select"
              value={profileId}
              onChange={(e) => setProfileId(e.target.value)}
              required
            >
              <option value="">Select profile</option>
              {profiles.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>
          <Input
            label="Cron expression"
            value={cronExpression}
            onChange={(e) => setCronExpression(e.target.value)}
            required
            placeholder="0 0 * * *"
          />
          <p className="text-[12px] text-[var(--muted)]">
            Human-readable: <span className="font-mono text-[var(--charcoal)]">{cronHint(cronExpression)}</span>
          </p>
          <Input
            label="Timezone"
            value={timezone}
            onChange={(e) => setTimezone(e.target.value)}
            required
            placeholder="America/New_York"
          />
          {(createMutation.isError || updateMutation.isError) && (
            <Alert variant="error" title="Save failed">
              Check cron syntax, timezone, and URL validation, then retry.
            </Alert>
          )}
          <div className="flex flex-wrap gap-2">
            <Button type="submit" variant="primary" loading={busy}>
              {editing ? "Save schedule" : "Create schedule"}
            </Button>
            <Button type="button" variant="ghost" disabled={busy} onClick={resetForm}>
              Cancel
            </Button>
          </div>
        </form>
      ) : null}

      {schedulesQuery.isLoading ? (
        <div className="ds-card flex items-center gap-2 py-10 text-[var(--muted)]">
          <span className="ds-spinner ds-spinner--sm" />
          Loading schedules…
        </div>
      ) : null}

      {schedulesQuery.isSuccess && schedulesQuery.data.length === 0 && !creating ? (
        <div className="ds-card py-10 text-center text-[13px] text-[var(--muted)]">
          No recurring crawls yet. Create a schedule to see it here.
        </div>
      ) : null}

      <div className="space-y-2">
        {schedulesQuery.data?.map((s) => (
          <div
            key={s.id}
            className="ds-card flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"
          >
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <p className="font-soehne truncate text-[14px] font-semibold text-[var(--charcoal)]">
                  {s.target_url}
                </p>
                <Badge variant={s.is_active ? "success" : "neutral"}>
                  {s.is_active ? "Active" : "Paused"}
                </Badge>
              </div>
              <p className="mt-1 text-[12px] text-[var(--muted)]">
                Profile: {s.profile?.name ?? s.profile_id}
              </p>
              <p className="mt-1 font-mono text-[11px] text-[var(--charcoal)]">
                {s.cron_expression}
                <span className="ml-2 text-[var(--muted)]">({cronHint(s.cron_expression)})</span>
              </p>
              <p className="mt-1 text-[12px] text-[var(--muted)]">
                Timezone: <span className="font-mono text-[var(--charcoal)]">{s.timezone}</span>
                {s.next_run_at ? (
                  <>
                    {" "}
                    · Next:{" "}
                    <span className="font-mono text-[var(--charcoal)]">
                      {new Intl.DateTimeFormat(undefined, {
                        dateStyle: "medium",
                        timeStyle: "short",
                        timeZone: s.timezone,
                      }).format(new Date(s.next_run_at))}
                    </span>
                  </>
                ) : null}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button type="button" variant="secondary" onClick={() => startEdit(s)}>
                Edit
              </Button>
              <Button
                type="button"
                variant="ghost"
                disabled={busy}
                onClick={() =>
                  patchMutation.mutate({
                    id: s.id,
                    patch: { is_active: !s.is_active },
                  })
                }
              >
                {s.is_active ? "Pause" : "Resume"}
              </Button>
              <Button
                type="button"
                variant="secondary"
                disabled={busy}
                onClick={() => {
                  if (window.confirm("Delete this schedule?")) {
                    deleteMutation.mutate(s.id);
                  }
                }}
              >
                Delete
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
