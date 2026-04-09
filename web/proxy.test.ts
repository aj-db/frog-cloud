import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const clerkMiddlewareMock = vi.fn(() => "mocked-middleware");
const createRouteMatcherMock = vi.fn(() => () => false);

vi.mock("@clerk/nextjs/server", () => ({
  clerkMiddleware: clerkMiddlewareMock,
  createRouteMatcher: createRouteMatcherMock,
}));

const originalAuthorizedParties = process.env.CLERK_AUTHORIZED_PARTIES;
const originalReplitDevDomain = process.env.REPLIT_DEV_DOMAIN;

type ClerkOptionsCallback = (request: unknown) =>
  | { authorizedParties?: string[] }
  | Promise<{ authorizedParties?: string[] }>;

describe("frontend clerk proxy", () => {
  beforeEach(() => {
    vi.resetModules();
    clerkMiddlewareMock.mockClear();
    createRouteMatcherMock.mockClear();

    process.env.CLERK_AUTHORIZED_PARTIES = " https://frog.replit.app/ , https://app.example.com/ ";
    process.env.REPLIT_DEV_DOMAIN = "frog-dev.username.replit.dev";
  });

  afterEach(() => {
    if (originalAuthorizedParties === undefined) {
      delete process.env.CLERK_AUTHORIZED_PARTIES;
    } else {
      process.env.CLERK_AUTHORIZED_PARTIES = originalAuthorizedParties;
    }

    if (originalReplitDevDomain === undefined) {
      delete process.env.REPLIT_DEV_DOMAIN;
    } else {
      process.env.REPLIT_DEV_DOMAIN = originalReplitDevDomain;
    }
  });

  it("passes a Clerk authorizedParties allowlist with local and configured origins", async () => {
    await import("./proxy");

    expect(clerkMiddlewareMock).toHaveBeenCalledTimes(1);

    const calls = clerkMiddlewareMock.mock.calls as unknown[][];
    const options = calls[0]?.[1] as
      | ClerkOptionsCallback
      | undefined;
    expect(typeof options).toBe("function");
    if (!options) {
      throw new Error("Expected middleware options callback");
    }

    const resolved = await options({} as never);
    expect(resolved).toMatchObject({
      authorizedParties: [
        "http://localhost:3001",
        "http://localhost:3002",
        "https://frog-dev.username.replit.dev",
        "https://frog.replit.app",
        "https://app.example.com",
      ],
    });
  });
});
