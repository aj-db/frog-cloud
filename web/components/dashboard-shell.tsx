"use client";

import { UserButton } from "@clerk/nextjs";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { OrgSwitcherWithInvalidation } from "@/components/org-switcher";

const nav = [
  { href: "/crawls", label: "Crawls" },
  { href: "/schedules", label: "Schedules" },
  { href: "/settings", label: "Settings" },
];

export function DashboardShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div
      className="min-h-screen"
      style={{ background: "var(--bg)", color: "var(--text)" }}
    >
      <header
        className="sticky top-0 z-40 border-b"
        style={{
          borderColor: "var(--border)",
          background: "var(--bg)",
        }}
      >
        <div className="mx-auto flex max-w-[1600px] flex-wrap items-center justify-between gap-3 px-4 py-3">
          <div className="flex flex-wrap items-center gap-6">
            <Link
              href="/crawls"
              className="font-soehne text-[13px] font-semibold tracking-tight text-[var(--charcoal)]"
            >
              🦊 Vulpes
            </Link>
            <nav className="flex items-center gap-1">
              {nav.map((item) => {
                const active =
                  item.href === "/crawls"
                    ? pathname.startsWith("/crawls")
                    : pathname === item.href;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className="rounded-[var(--radius-sm)] px-2.5 py-1 text-[12px] font-medium transition-colors"
                    style={{
                      color: active ? "var(--charcoal)" : "var(--muted)",
                      background: active ? "var(--light-grey)" : "transparent",
                    }}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </nav>
          </div>
          <div className="flex items-center gap-3">
            <OrgSwitcherWithInvalidation />
            <UserButton
              appearance={{
                elements: {
                  avatarBox: "h-8 w-8 rounded-[var(--radius-sm)] border border-[var(--border)]",
                },
              }}
            />
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-[1600px] px-4 py-8">{children}</main>
    </div>
  );
}
