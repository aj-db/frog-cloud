"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Alert } from "@/components/alert";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import type { CrawlProfile } from "@/lib/api-types";
import { useCrawlApi } from "@/lib/use-crawl-api";

export function SettingsClient() {
  const api = useCrawlApi();
  const queryClient = useQueryClient();
  const profilesQuery = useQuery({
    queryKey: ["profiles"],
    queryFn: () => api.getCrawlProfiles(),
  });

  const [editing, setEditing] = useState<CrawlProfile | null>(null);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [configPath, setConfigPath] = useState("");

  const resetForm = () => {
    setName("");
    setDescription("");
    setConfigPath("");
    setEditing(null);
    setCreating(false);
  };

  const createMutation = useMutation({
    mutationFn: () =>
      api.createProfile({
        name: name.trim(),
        description: description.trim() || null,
        config_path: configPath.trim() || null,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["profiles"] });
      resetForm();
    },
  });

  const updateMutation = useMutation({
    mutationFn: () => {
      if (!editing) throw new Error("No profile");
      return api.updateProfile(editing.id, {
        name: name.trim(),
        description: description.trim() || null,
        config_path: configPath.trim() || null,
      });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["profiles"] });
      resetForm();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteProfile(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["profiles"] });
      resetForm();
    },
  });

  const startEdit = (p: CrawlProfile) => {
    setEditing(p);
    setCreating(false);
    setName(p.name);
    setDescription(p.description ?? "");
    setConfigPath(p.config_path ?? "");
  };

  const startCreate = () => {
    setCreating(true);
    setEditing(null);
    setName("");
    setDescription("");
    setConfigPath("");
  };

  const busy =
    createMutation.isPending || updateMutation.isPending || deleteMutation.isPending;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="ds-section-label mb-1">Admin</p>
          <h1 className="ds-page-title">Crawl profiles</h1>
          <p className="mt-1 text-[13px] text-[var(--muted)]">
            Manage stored Screaming Frog configuration profiles for your organization.
          </p>
        </div>
        <Button type="button" variant="primary" onClick={startCreate} disabled={creating}>
          New profile
        </Button>
      </div>

      {profilesQuery.isError ? (
        <Alert variant="error" title="Could not load profiles">
          Verify API connectivity and try again.
        </Alert>
      ) : null}

      {creating || editing ? (
        <form
          className="ds-card ds-card--lg space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            if (editing) updateMutation.mutate();
            else createMutation.mutate();
          }}
        >
          <p className="font-soehne text-[14px] font-semibold text-[var(--charcoal)]">
            {editing ? "Edit profile" : "Create profile"}
          </p>
          <Input label="Name" value={name} onChange={(e) => setName(e.target.value)} required />
          <div>
            <label className="ds-label" htmlFor="desc">
              Description
            </label>
            <textarea
              id="desc"
              className="ds-input min-h-[88px] resize-y"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <Input
            label="Config path / URI"
            value={configPath}
            onChange={(e) => setConfigPath(e.target.value)}
            placeholder="configs/standard-audit.seospiderconfig"
          />
          {(createMutation.isError || updateMutation.isError) && (
            <Alert variant="error" title="Save failed">
              The API could not save this profile.
            </Alert>
          )}
          <div className="flex flex-wrap gap-2">
            <Button type="submit" variant="primary" loading={busy}>
              {editing ? "Save changes" : "Create"}
            </Button>
            <Button type="button" variant="ghost" disabled={busy} onClick={resetForm}>
              Cancel
            </Button>
            {editing ? (
              <Button
                type="button"
                variant="secondary"
                disabled={busy}
                onClick={() => {
                  if (
                    window.confirm(
                      `Delete profile “${editing.name}”? This cannot be undone.`,
                    )
                  ) {
                    deleteMutation.mutate(editing.id);
                  }
                }}
              >
                Delete
              </Button>
            ) : null}
          </div>
        </form>
      ) : null}

      {profilesQuery.isLoading ? (
        <div className="ds-card flex items-center gap-2 py-10 text-[var(--muted)]">
          <span className="ds-spinner ds-spinner--sm" />
          Loading profiles…
        </div>
      ) : null}

      {profilesQuery.isSuccess && profilesQuery.data.length === 0 && !creating ? (
        <div className="ds-card py-10 text-center text-[13px] text-[var(--muted)]">
          No profiles yet. Seed the API or create one above.
        </div>
      ) : null}

      <div className="space-y-2">
        {profilesQuery.data?.map((p) => (
          <div key={p.id} className="ds-card flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="font-soehne text-[14px] font-semibold text-[var(--charcoal)]">
                {p.name}
              </p>
              {p.description ? (
                <p className="mt-1 text-[13px] text-[var(--muted)]">{p.description}</p>
              ) : null}
              {p.config_path ? (
                <p className="mt-2 font-mono text-[11px] text-[var(--muted)]">
                  {p.config_path}
                </p>
              ) : null}
            </div>
            <Button type="button" variant="secondary" onClick={() => startEdit(p)}>
              Edit
            </Button>
          </div>
        ))}
      </div>
    </div>
  );
}
