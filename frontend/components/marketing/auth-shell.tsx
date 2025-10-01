import { MarketingTopBar } from "./top-bar";

export function AuthShell({ children, title, subtitle }: { children: React.ReactNode; title: string; subtitle?: string }) {
  return (
    <div className="flex min-h-screen flex-col">
      <MarketingTopBar />
      <main className="flex flex-1 items-center justify-center px-4 py-20">
        <div className="w-full max-w-md rounded-3xl border border-slate-800/60 bg-slate-900/70 p-8 shadow-[0_32px_60px_-38px_rgba(56,189,248,0.45)] backdrop-blur-2xl">
          <div className="mb-8 space-y-2 text-center">
            <p className="text-xs uppercase tracking-[0.45em] text-sky-300">Secure console</p>
            <h1 className="text-2xl font-semibold text-slate-50">{title}</h1>
            {subtitle && <p className="text-sm text-slate-400">{subtitle}</p>}
          </div>
          {children}
        </div>
      </main>
    </div>
  );
}
