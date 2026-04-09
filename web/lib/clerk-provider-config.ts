import { getClerkAuthorizedParties } from "./clerk-authorized-parties";

type ClerkEnv = Record<string, string | undefined>;

export function getClerkProviderProps(env: ClerkEnv = process.env) {
  return {
    signInUrl: env.NEXT_PUBLIC_CLERK_SIGN_IN_URL || "/sign-in",
    signUpUrl: env.NEXT_PUBLIC_CLERK_SIGN_UP_URL || "/sign-up",
    signInFallbackRedirectUrl:
      env.NEXT_PUBLIC_CLERK_SIGN_IN_FALLBACK_REDIRECT_URL || "/crawls",
    signUpFallbackRedirectUrl:
      env.NEXT_PUBLIC_CLERK_SIGN_UP_FALLBACK_REDIRECT_URL || "/crawls",
    allowedRedirectOrigins: getClerkAuthorizedParties(env),
  };
}
