import { describe, expect, it } from "vitest";

import { getClerkProviderProps } from "./clerk-provider-config";

describe("getClerkProviderProps", () => {
  it("builds ClerkProvider props for deployed origins and crawl redirects", () => {
    const props = getClerkProviderProps({
      NEXT_PUBLIC_CLERK_SIGN_IN_URL: "/sign-in",
      NEXT_PUBLIC_CLERK_SIGN_UP_URL: "/sign-up",
      NEXT_PUBLIC_CLERK_SIGN_IN_FALLBACK_REDIRECT_URL: "/crawls",
      NEXT_PUBLIC_CLERK_SIGN_UP_FALLBACK_REDIRECT_URL: "/crawls",
      CLERK_AUTHORIZED_PARTIES: "https://vulpes-crawler.replit.app",
    });

    expect(props).toEqual({
      signInUrl: "/sign-in",
      signUpUrl: "/sign-up",
      signInFallbackRedirectUrl: "/crawls",
      signUpFallbackRedirectUrl: "/crawls",
      allowedRedirectOrigins: [
        "http://localhost:3001",
        "http://localhost:3002",
        "https://vulpes-crawler.replit.app",
      ],
    });
  });
});
