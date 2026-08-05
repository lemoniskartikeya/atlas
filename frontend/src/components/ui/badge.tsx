import { type HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export function Badge({ className, ...props }: HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border border-border/10 bg-ink/[0.06] px-2 py-0.5 text-[11px] font-medium text-ink-muted",
        className,
      )}
      {...props}
    />
  );
}
