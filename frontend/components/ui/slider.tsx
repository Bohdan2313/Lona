import * as React from "react";
import { cn } from "@/lib/utils";

export interface SliderProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
}

export const Slider = React.forwardRef<HTMLInputElement, SliderProps>(({ className, ...props }, ref) => {
  return (
    <input
      type="range"
      ref={ref}
      className={cn(
        "h-2 w-full cursor-pointer appearance-none rounded-full bg-slate-800 accent-sky-500", 
        className
      )}
      {...props}
    />
  );
});
Slider.displayName = "Slider";
