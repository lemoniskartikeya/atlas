import { useEffect, useRef, useState } from "react";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

interface CheckToggleProps {
  checked: boolean;
  onChange: () => void;
  disabled?: boolean;
  label?: string;
  /** Diameter in px. 20 for dense rows, 24 for primary lists. */
  size?: number;
  /** Sage for "achieved" (habits/tasks); accent for neutral selection. */
  tone?: "success" | "accent";
}

/**
 * The single completion affordance used everywhere in Atlas.
 *
 * Checking it is meant to feel earned: the tick draws itself on, a ring pulses
 * outward once, and the whole control springs. Unchecking is deliberately
 * quiet — undo shouldn't celebrate. The celebration only fires on a real user
 * transition, never on mount, so a list of already-done items doesn't erupt.
 */
export function CheckToggle({
  checked,
  onChange,
  disabled,
  label,
  size = 20,
  tone = "success",
}: CheckToggleProps) {
  const [celebrating, setCelebrating] = useState(false);
  const prev = useRef(checked);
  const mounted = useRef(false);

  useEffect(() => {
    if (mounted.current && checked && !prev.current) {
      setCelebrating(true);
      const t = setTimeout(() => setCelebrating(false), 650);
      return () => clearTimeout(t);
    }
    prev.current = checked;
    mounted.current = true;
  }, [checked]);

  const filled =
    tone === "success"
      ? "border-success bg-success text-white"
      : "border-accent bg-accent text-white";
  const hollow =
    tone === "success"
      ? "border-ink/25 text-transparent hover:border-success hover:text-success/30"
      : "border-ink/25 text-transparent hover:border-accent hover:text-accent/30";

  return (
    <button
      type="button"
      onClick={onChange}
      disabled={disabled}
      aria-pressed={checked}
      aria-label={label ?? (checked ? "Mark not done" : "Mark done")}
      style={{ width: size, height: size }}
      className={cn(
        "pressable relative grid shrink-0 place-items-center rounded-full border",
        checked ? filled : hollow,
        celebrating && "complete-ping",
        disabled && "opacity-50",
      )}
    >
      <Check
        size={Math.round(size * 0.6)}
        strokeWidth={3}
        className={cn(celebrating && "draw-check")}
      />
    </button>
  );
}
