import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-full text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-60 ring-offset-slate-950",
  {
    variants: {
      variant: {
        default: "bg-gradient-to-r from-sky-500 to-indigo-500 text-slate-950 shadow-elevated hover:shadow-glow",
        secondary: "bg-slate-900/60 text-slate-100 hover:bg-slate-900/80 border border-slate-700",
        outline:
          "border border-slate-700/70 bg-transparent text-slate-100 hover:bg-slate-900/50 hover:border-slate-600",
        ghost: "hover:bg-slate-900/70 text-slate-200",
      },
      size: {
        default: "h-10 px-5",
        sm: "h-9 px-4",
        lg: "h-11 px-6 text-base",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp ref={ref} className={cn(buttonVariants({ variant, size, className }))} {...props} />
    );
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
