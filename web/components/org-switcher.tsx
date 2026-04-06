"use client";

import { OrganizationSwitcher, useOrganization } from "@clerk/nextjs";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

export function OrgSwitcherWithInvalidation() {
  const { organization } = useOrganization();
  const queryClient = useQueryClient();
  const prevOrgId = useRef<string | undefined>(undefined);

  useEffect(() => {
    const id = organization?.id;
    if (prevOrgId.current && id && prevOrgId.current !== id) {
      queryClient.clear();
    }
    prevOrgId.current = id;
  }, [organization?.id, queryClient]);

  return (
    <OrganizationSwitcher
      hidePersonal
      afterSelectOrganizationUrl="/crawls"
      afterCreateOrganizationUrl="/crawls"
      appearance={{
        elements: {
          rootBox: "flex items-center",
          organizationSwitcherTrigger:
            "border border-[var(--border)] rounded-[var(--radius-sm)] px-2 py-1 text-[12px] font-medium text-[var(--charcoal)] bg-[var(--card)]",
        },
      }}
    />
  );
}
