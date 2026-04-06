import { Show } from "@clerk/nextjs";
import { Alert } from "@/components/alert";
import { SettingsClient } from "./settings-client";

export default async function SettingsPage() {
  return (
    <Show
      when={{ role: "org:admin" }}
      fallback={
        <div className="ds-card ds-card--lg">
          <Alert variant="warning" title="Administrators only">
            Crawl profile management is limited to organization admins. Ask an admin to update
            profiles or grant you the <span className="font-mono">org:admin</span> role.
          </Alert>
        </div>
      }
    >
      <SettingsClient />
    </Show>
  );
}
