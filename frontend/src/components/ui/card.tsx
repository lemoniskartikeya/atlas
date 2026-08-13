import { forwardRef, type HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

/**
 * A page section.
 *
 * `flat` is the default: same spacing as before, no border and no frosted
 * material. A page where every section is a bordered panel reads as a grid of
 * containers rather than a document — the boxes end up carrying more visual
 * weight than the numbers inside them.
 *
 * `glass` keeps the frosted material, for things that genuinely sit above the
 * page: popovers, the login card, the sidebar, and the one panel a screen is
 * actually about. Spacing is identical either way, so switching a section
 * between them never reflows its contents.
 */
type Variant = "flat" | "glass";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  variant?: Variant;
}

export const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ className, variant = "flat", ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "rounded-2xl",
        variant === "glass"
          ? "glass"
          : // A hairline only where a section needs separating from the next;
            // the warm canvas does the rest of the work.
            "bg-surface/40 dark:bg-ink/[0.02]",
        className,
      )}
      {...props}
    />
  ),
);
Card.displayName = "Card";

export function CardHeader({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("flex items-center justify-between gap-3 px-5 pt-4 pb-1.5", className)}
      {...props}
    />
  );
}

export function CardTitle({ className, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3
      className={cn(
        "text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-muted",
        className,
      )}
      {...props}
    />
  );
}

export function CardBody({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("px-5 pb-5", className)} {...props} />;
}
