import * as React from "react";
import { cn } from "@/lib/utils";

export interface SwitchProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  checked?: boolean;
}

export const Switch = React.forwardRef<HTMLButtonElement, SwitchProps>(
  ({ checked = false, className, onClick, ...props }, ref) => {
    return (
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        data-state={checked ? "checked" : "unchecked"}
        onClick={(event) => {
          onClick?.(event);
        }}
        ref={ref}
        className={cn(
          "flex h-6 w-11 items-center rounded-full border border-slate-700/60 bg-slate-900 transition-colors data-[state=checked]:bg-sky-500/80",
          className
        )}
        {...props}
      >
        <span
          className={cn(
            "ml-1 inline-block h-4 w-4 transform rounded-full bg-slate-400 transition-transform",
            checked ? "translate-x-5 bg-slate-950" : "translate-x-0"
          )}
        />
      </button>
    );
  }
);
Switch.displayName = "Switch";
