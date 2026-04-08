"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { Alert } from "@/components/alert";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { useCrawlApi } from "@/lib/use-crawl-api";

const URL_PATTERN = /^https?:\/\/[^\s$.?#].[^\s]*$/i;

export default function NewCrawlPage() {
  const router = useRouter();
  const api = useCrawlApi();
  const [url, setUrl] = useState("");
  const [profileId, setProfileId] = useState("");
  const [maxUrls, setMaxUrls] = useState("");
  const [urlError, setUrlError] = useState<string | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [maxUrlsError, setMaxUrlsError] = useState<string | null>(null);

  const profilesQuery = useQuery({
    queryKey: ["profiles"],
    queryFn: () => api.getCrawlProfiles(),
  });

  const profileOptions = useMemo(() => profilesQuery.data ?? [], [profilesQuery.data]);

  const createMutation = useMutation({
    mutationFn: () =>
      api.createCrawl({
        target_url: url.trim(),
        profile_id: profileId,
        max_urls: maxUrls ? parseInt(maxUrls, 10) : null,
      }),
    onSuccess: (job) => {
      router.push(`/crawls/${job.job_id}`);
    },
  });

  const validate = (): boolean => {
    let ok = true;
    if (!url.trim()) {
      setUrlError("Enter a URL to crawl.");
      ok = false;
    } else if (!URL_PATTERN.test(url.trim())) {
      setUrlError("Use a valid http(s) URL.");
      ok = false;
    } else {
      setUrlError(null);
    }
    if (!profileId) {
      setProfileError("Choose a crawl profile.");
      ok = false;
    } else {
      setProfileError(null);
    }
    if (maxUrls) {
      const n = parseInt(maxUrls, 10);
      if (isNaN(n) || n < 1) {
        setMaxUrlsError("Must be a positive number.");
        ok = false;
      } else if (n > 1_000_000) {
        setMaxUrlsError("Maximum is 1,000,000.");
        ok = false;
      } else {
        setMaxUrlsError(null);
      }
    } else {
      setMaxUrlsError(null);
    }
    return ok;
  };

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    createMutation.mutate();
  };

  return (
    <div className="space-y-6">
      <div>
        <p className="ds-section-label mb-1">Crawls</p>
        <h1 className="ds-page-title">New crawl</h1>
        <p className="mt-1 text-[13px] text-[var(--muted)]">
          Submit a URL and profile. You will be redirected to the job as soon as it is accepted.
        </p>
      </div>

      <form onSubmit={onSubmit} className="ds-card ds-card--lg space-y-4">
        <Input
          label="Target URL"
          name="target_url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://example.com"
          error={urlError ?? undefined}
          autoComplete="url"
        />

        <div>
          <label className="ds-label" htmlFor="profile">
            Crawl profile
          </label>
          <select
            id="profile"
            className="ds-select"
            value={profileId}
            onChange={(e) => setProfileId(e.target.value)}
            disabled={profilesQuery.isLoading}
          >
            <option value="">Select a profile</option>
            {profileOptions.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
          {profileError ? (
            <p className="mt-1 text-[12px] font-medium text-[var(--red)]">{profileError}</p>
          ) : null}
          {profilesQuery.isError ? (
            <p className="mt-1 text-[12px] text-[var(--red)]">
              Profiles could not be loaded. Check the API and try again.
            </p>
          ) : null}
        </div>

        <Input
          label="URL limit"
          name="max_urls"
          type="number"
          min={1}
          max={1_000_000}
          value={maxUrls}
          onChange={(e) => setMaxUrls(e.target.value)}
          placeholder="No limit"
          error={maxUrlsError ?? undefined}
        />
        <p className="-mt-2 text-[12px] text-[var(--muted)]">
          Optional. Cap the number of URLs the crawler will visit.
        </p>

        {createMutation.isError ? (
          <Alert variant="error" title="Could not start crawl">
            The API rejected this request. Fix any validation issues and retry.
          </Alert>
        ) : null}

        <div className="flex flex-wrap gap-2 pt-2">
          <Button type="submit" variant="primary" loading={createMutation.isPending}>
            Start crawl
          </Button>
          <Link href="/crawls" className="ds-btn ds-btn--secondary no-underline">
            Cancel
          </Link>
        </div>
      </form>
    </div>
  );
}
