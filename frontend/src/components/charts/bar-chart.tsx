import { useState } from "react";
import { cn } from "@/lib/utils";

interface Bar {
  label: string;
  value: number;
}

/** Vertical bars, single accent hue (magnitude). Values on hover, not every bar. */
export function BarChart({
  data,
  height = 150,
  formatValue,
  highlightLast,
}: {
  data: Bar[];
  height?: number;
  formatValue?: (n: number) => string;
  highlightLast?: boolean;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const max = Math.max(1, ...data.map((d) => d.value));

  return (
    <div>
      <div className="flex items-end gap-[3px]" style={{ height }}>
        {data.map((d, i) => {
          const h = (d.value / max) * 100;
          const active = hover === i || (hover === null && highlightLast && i === data.length - 1);
          return (
            <div
              key={i}
              className="group relative flex flex-1 flex-col items-center justify-end"
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover(null)}
            >
              {hover === i && (
                <div className="glass pointer-events-none absolute bottom-full z-10 mb-1 whitespace-nowrap rounded-lg px-2 py-1 text-[11px] font-medium text-ink">
                  {formatValue ? formatValue(d.value) : d.value}
                </div>
              )}
              <div
                className="w-full max-w-[28px] rounded-t-md transition-colors"
                style={{
                  height: `${h}%`,
                  minHeight: d.value > 0 ? 3 : 0,
                  backgroundColor: active ? "rgb(var(--accent))" : "rgb(var(--accent) / 0.5)",
                }}
              />
            </div>
          );
        })}
      </div>
      <div className="mt-2 flex gap-[3px]">
        {data.map((d, i) => (
          <div
            key={i}
            className={cn(
              "flex-1 truncate text-center text-[10px]",
              hover === i ? "text-ink" : "text-ink-faint",
            )}
          >
            {d.label}
          </div>
        ))}
      </div>
    </div>
  );
}
