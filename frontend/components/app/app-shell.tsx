"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { LogOut, Settings, User, LineChart, LayoutDashboard } from "lucide-react";
import { useAuth } from "@/components/auth-provider";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

const NAVIGATION = [
  { href: "/app/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/app/settings", label: "Settings", icon: Settings },
  { href: "/app/trades", label: "Trades", icon: LineChart },
  { href: "/app/profile", label: "Profile", icon: User },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { logout, user } = useAuth();
  const router = useRouter();

  const handleLogout = () => {
    logout();
    router.push("/login");
  };

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-40 border-b border-slate-800/70 bg-slate-950/80 backdrop-blur-xl">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-4">
          <Link href="/app/dashboard" className="flex items-center gap-2 text-sm font-semibold tracking-[0.45em] text-slate-200">
            LONAMIND
          </Link>
          <nav className="hidden items-center gap-1 rounded-full border border-slate-800/60 bg-slate-900/60 p-1 text-sm text-slate-300 md:flex">
            {NAVIGATION.map((item) => {
              const active = pathname?.startsWith(item.href);
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex items-center gap-2 rounded-full px-4 py-2 font-medium transition",
                    active
                      ? "bg-slate-800/80 text-slate-50 shadow-[0_0_0_1px_rgba(56,189,248,0.3)]"
                      : "text-slate-400 hover:text-slate-100"
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {item.label}
                </Link>
              );
            })}
          </nav>
          <div className="flex items-center gap-3">
            <div className="hidden flex-col text-right text-xs text-slate-400 sm:flex">
              <span className="font-semibold text-slate-200">{user?.name ?? "Operator"}</span>
              <span>{user?.email}</span>
            </div>
            <Button variant="outline" size="sm" onClick={handleLogout} className="gap-2">
              <LogOut className="h-4 w-4" />
              Logout
            </Button>
          </div>
        </div>
        <nav className="mx-auto mt-3 flex w-full max-w-6xl gap-2 px-6 pb-4 md:hidden">
          {NAVIGATION.map((item) => {
            const active = pathname?.startsWith(item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex flex-1 items-center justify-center gap-2 rounded-full border px-3 py-2 text-xs font-medium uppercase tracking-[0.2em]",
                  active
                    ? "border-sky-500/40 bg-sky-500/10 text-sky-200"
                    : "border-slate-800/70 bg-slate-950/40 text-slate-400"
                )}
              >
                <Icon className="h-3.5 w-3.5" />
                {item.label}
              </Link>
            );
          })}
        </nav>
      </header>
      <main className="flex-1">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-6 py-10">
          {children}
        </div>
      </main>
    </div>
  );
}
