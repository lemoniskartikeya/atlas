import { Gauge, Sparkles } from "lucide-react";
import { useEffectsLevel, type EffectsLevel } from "@/hooks/useEffects";
import { cn } from "@/lib/utils";

const OPTIONS: { id: EffectsLevel; label: string; icon: typeof Sparkles; hint: string }[] = [
  { id: "full", label: "Full", icon: Sparkles, hint: "Frosted panels over a drifting backdrop." },
  { id: "lite", label: "Lite", icon: Gauge, hint: "Flat panels, no blur. Much lighter to draw." },
];

/**
 * Visual-effects level.
 *
 * The frosted material and the ambient backdrop are the two expensive things
 * in this design — both make the GPU re-composite large areas on every frame.
 * Lite drops them and keeps the palette, layout and type, so the app still
 * looks like itself. Atlas picks Lite on its own for machines that report few
 * cores or little memory; this is where that gets overridden.
 */
export function EffectsToggle() {
  const { level, setLevel, autoDetected } = useEffectsLevel();
  const active = OPTIONS.find((o) => o.id === level) ?? OPTIONS[0];

  return (
    <div className="flex items-start justify-between gap-4">
      <div className="min-w-0">
        <div className="text-sm text-ink">Visual effects</div>
        <div className="text-[12px] text-ink-muted">
          {active.hint}
          {autoDetected && level === "lite" && (
            <> Chosen automatically for this machine — switch to Full any time.</>
          )}
        </div>
      </div>

      <div
        role="radiogroup"
        aria-label="Visual effects"
        className="flex shrink-0 rounded-xl border border-border/10 p-0.5"
      >
        {OPTIONS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            role="radio"
            aria-checked={level === id}
            onClick={() => setLevel(id)}
            className={cn(
              "pressable flex items-center gap-1.5 rounded-[10px] px-2.5 py-1.5 text-[12px] transition-colors",
              level === id
                ? "bg-accent/[0.12] text-ink"
                : "text-ink-muted hover:text-ink",
            )}
          >
            <Icon size={13} />
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}
