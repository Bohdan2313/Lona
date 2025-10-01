import { cn } from "@/lib/utils";

export function Badge({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border border-slate-700 bg-slate-900/80 px-3 py-1 text-xs font-medium uppercase tracking-[0.18em] text-slate-300",
        className
      )}
    >
      {children}
    </span>
  );
}
