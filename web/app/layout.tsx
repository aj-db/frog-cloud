import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "Vulpes",
  description:
    "Multi-tenant SEO crawl platform powered by Screaming Frog.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <ClerkProvider>
      <html lang="en">
        <body
          className="min-h-screen antialiased"
          style={{
            fontFamily: "var(--font)",
            background: "var(--bg)",
            color: "var(--text)",
          }}
        >
          <Providers>{children}</Providers>
        </body>
      </html>
    </ClerkProvider>
  );
}
