import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { MarketingTopBar } from "@/components/marketing/top-bar";
import { Button } from "@/components/ui/button";

export default function LandingPage() {
  const highlights = [
    {
      title: "Autonomous execution",
      description: "Deploy AI-curated trade flows that adapt to volatility, liquidity, and sentiment in real time.",
    },
    {
      title: "Configurable intelligence",
      description: "Fine-tune leverage, risk ceilings, and market scanners with human-readable controls backed by JSON schemas.",
    },
    {
      title: "Unified operations",
      description: "A premium-grade control room for monitoring bots, editing strategies, and collaborating with your team.",
    },
  ];

  return (
    <div className="flex min-h-screen flex-col">
      <MarketingTopBar />

      <main className="relative flex flex-1 items-center justify-center overflow-hidden">
        <div className="absolute inset-0 -z-10 bg-[radial-gradient(circle_at_top,_rgba(56,189,248,0.15),transparent_60%)]" />
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-20 px-6 py-24">
          <div className="grid gap-12 lg:grid-cols-[3fr,2fr] lg:items-center">
            <div className="space-y-8">
              <span className="inline-flex items-center gap-2 rounded-full border border-sky-500/40 bg-sky-500/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.3em] text-sky-300">
                AI-native crypto execution
              </span>
              <h1 className="text-4xl font-semibold leading-tight text-slate-50 sm:text-6xl">
                Operate the AI-Lona trading intelligence with human-grade clarity.
              </h1>
              <p className="max-w-2xl text-lg text-slate-300">
                LonaMind distills billions of signals into tangible actions. Monitor live bot performance, calibrate leverage,
                and deploy proprietary alpha in minutes.
              </p>
              <div className="flex flex-wrap gap-3">
                <Button asChild size="lg">
                  <Link href="/register" className="flex items-center gap-2">
                    Launch your console
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                </Button>
                <Button asChild variant="secondary" size="lg">
                  <Link href="/login">I already have access</Link>
                </Button>
              </div>
            </div>
            <div className="grid gap-4 rounded-3xl border border-slate-800/60 bg-slate-900/50 p-8 shadow-[0_32px_60px_-38px_rgba(56,189,248,0.55)] backdrop-blur-2xl">
              <div className="flex items-baseline justify-between text-sm text-slate-400">
                <span>Bot uptime</span>
                <span className="text-2xl font-semibold text-slate-100">99.98%</span>
              </div>
              <div className="flex items-center justify-between text-sm text-slate-400">
                <span>Capital deployed</span>
                <span className="text-2xl font-semibold text-emerald-300">$4.2M</span>
              </div>
              <div className="flex items-center justify-between text-sm text-slate-400">
                <span>Signals analysed / min</span>
                <span className="text-2xl font-semibold text-sky-300">11,284</span>
              </div>
              <div className="mt-4 h-32 rounded-2xl border border-slate-800/60 bg-[linear-gradient(135deg,rgba(56,189,248,0.25),rgba(14,116,144,0.25))]" />
            </div>
          </div>
          <section className="grid gap-6 md:grid-cols-3">
            {highlights.map((item) => (
              <div
                key={item.title}
                className="rounded-3xl border border-slate-800/60 bg-slate-900/50 p-6 backdrop-blur-xl transition hover:border-sky-500/60 hover:shadow-glow"
              >
                <h3 className="text-lg font-semibold text-slate-50">{item.title}</h3>
                <p className="mt-3 text-sm text-slate-400">{item.description}</p>
              </div>
            ))}
          </section>
        </div>
      </main>
    </div>
  );
}
