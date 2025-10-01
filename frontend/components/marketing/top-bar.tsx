import Link from "next/link";
import { Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";

export function MarketingTopBar() {
  return (
    <header className="sticky top-0 z-30 border-b border-slate-800/60 bg-slate-950/80 backdrop-blur-xl">
      <div className="mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-5">
        <div className="flex items-center gap-2 text-lg font-semibold tracking-[0.4em] text-slate-200">
          <Sparkles className="h-5 w-5 text-sky-400" />
          LONAMIND
        </div>
        <nav className="flex items-center gap-3">
          <Button asChild variant="ghost" className="px-5 text-slate-200">
            <Link href="/login">Login</Link>
          </Button>
          <Button asChild className="shadow-glow">
            <Link href="/register">Register</Link>
          </Button>
        </nav>
      </div>
    </header>
  );
}
