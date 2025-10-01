import * as React from "react";
import { cn } from "@/lib/utils";

export interface LabelProps extends React.LabelHTMLAttributes<HTMLLabelElement> {}

const Label = React.forwardRef<HTMLLabelElement, LabelProps>(({ className, ...props }, ref) => (
  <label
    ref={ref}
    className={cn("block text-xs font-semibold uppercase tracking-[0.18em] text-slate-400", className)}
    {...props}
  />
));
Label.displayName = "Label";

export { Label };
