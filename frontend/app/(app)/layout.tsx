"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/app/app-shell";
import { useAuth } from "@/components/auth-provider";

export default function ApplicationLayout({ children }: { children: React.ReactNode }) {
  const { user, initializing } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!initializing && !user) {
      router.replace("/login");
    }
  }, [user, initializing, router]);

  if (!user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-400">
        <p className="text-sm uppercase tracking-[0.3em]">Preparing console...</p>
      </div>
    );
  }

  return <AppShell>{children}</AppShell>;
}
