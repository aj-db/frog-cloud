"use client";

import { useAuth } from "@clerk/nextjs";
import { useMemo } from "react";
import { createCrawlApi } from "./api-client";

export function useCrawlApi() {
  const { getToken } = useAuth();
  return useMemo(() => createCrawlApi(() => getToken()), [getToken]);
}
