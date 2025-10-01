"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";

const links = [
  { href: "/", label: "Dashboard" },
  { href: "/settings", label: "Settings" },
  { href: "/conditions", label: "Conditions" },
  { href: "/keys", label: "API Keys" }
];

export default function LayoutShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  return (
    <div style={{ display: "flex", width: "100%" }}>
      <aside
        style={{
          width: 220,
          padding: "32px 24px",
          borderRight: "1px solid rgba(148,163,184,0.15)",
          minHeight: "100vh"
        }}
      >
        <h1 style={{ fontSize: 20, marginBottom: 32 }}>AI-Lona</h1>
        <nav style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={clsx("nav-link", {
                active: pathname === link.href
              })}
              style={{
                padding: "10px 14px",
                borderRadius: 12,
                background:
                  pathname === link.href ? "rgba(59,130,246,0.2)" : "transparent",
                color: pathname === link.href ? "#38bdf8" : "inherit"
              }}
            >
              {link.label}
            </Link>
          ))}
        </nav>
      </aside>
      <section style={{ flex: 1, padding: "32px", display: "flex", flexDirection: "column", gap: 24 }}>
        {children}
      </section>
    </div>
  );
}
