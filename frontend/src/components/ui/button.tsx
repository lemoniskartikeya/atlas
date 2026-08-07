import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  // `pressable` carries the shared press/spring timing from the design system,
  // so every button in the app depresses with the same weight.
  "pressable inline-flex items-center justify-center gap-2 rounded-xl text-sm font-medium disabled:opacity-50 disabled:pointer-events-none select-none focus-visible:outline-none",
  {
    variants: {
      variant: {
        default:
          "bg-accent text-white shadow-[0_1px_2px_rgb(58_42_28/0.2),0_6px_16px_-8px_rgb(var(--accent)/0.55)] hover:brightness-[1.06] hover:shadow-[0_1px_2px_rgb(58_42_28/0.2),0_10px_22px_-8px_rgb(var(--accent)/0.6)]",
        subtle: "bg-accent-soft text-accent hover:bg-accent/20",
        outline:
          "border border-border/15 bg-panel/40 text-ink hover:bg-panel/70 hover:border-accent/25",
        ghost: "text-ink-muted hover:text-ink hover:bg-ink/5",
        danger: "text-danger hover:bg-danger-soft",
      },
      size: {
        sm: "h-8 px-3 text-[13px]",
        md: "h-9 px-4",
        lg: "h-11 px-5 text-[15px]",
        icon: "h-9 w-9",
        "icon-sm": "h-7 w-7",
      },
    },
    defaultVariants: { variant: "default", size: "md" },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button ref={ref} className={cn(buttonVariants({ variant, size }), className)} {...props} />
  ),
);
Button.displayName = "Button";

export { buttonVariants };
