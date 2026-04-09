const LOCAL_AUTHORIZED_PARTIES = [
  "http://localhost:3001",
  "http://localhost:3002",
] as const;

function normalizeOrigin(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) return null;

  try {
    return new URL(trimmed).origin;
  } catch {
    try {
      return new URL(`https://${trimmed}`).origin;
    } catch {
      return null;
    }
  }
}

export function getClerkAuthorizedParties(
  env: NodeJS.ProcessEnv = process.env,
): string[] {
  const configured = (env.CLERK_AUTHORIZED_PARTIES ?? "")
    .split(",")
    .map(normalizeOrigin)
    .filter((value): value is string => value !== null);

  const replitPreviewOrigin = env.REPLIT_DEV_DOMAIN
    ? normalizeOrigin(env.REPLIT_DEV_DOMAIN)
    : null;

  return Array.from(
    new Set([
      ...LOCAL_AUTHORIZED_PARTIES,
      ...(replitPreviewOrigin ? [replitPreviewOrigin] : []),
      ...configured,
    ]),
  );
}
