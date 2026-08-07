import { cn } from "@/lib/utils";

/** Loading placeholder. A light sweep reads as "loading"; a blunt opacity
 *  pulse reads as "broken", so this uses the shared `shimmer` gradient. */
export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("shimmer rounded-lg", className)} />;
}
