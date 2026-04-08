import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Default local development uses .next so IDEs recognize generated output.
  // Explicit parallel dev sessions can still isolate themselves with NEXT_DIST_DIR.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  typescript: {
    tsconfigPath: process.env.NEXT_TS_CONFIG_PATH || "tsconfig.json",
  },
  turbopack: {
    // Keep Turbopack rooted in the web app directory even when parent folders have lockfiles.
    root: path.join(__dirname),
  },
};

export default nextConfig;
