import { useMemo } from "react";
import type { Heatmap } from "@/lib/types";
import { parseDate } from "@/lib/utils";

const LEVEL_ALPHA = [0, 0.3, 0.5, 0.72, 1];

function cellColor(level: number): string {
  if (level <= 0) return "rgb(var(--ink) / 0.07)";
  return `rgb(var(--accent) / ${LEVEL_ALPHA[level] ?? 1})`;
}

/** GitHub-style contribution calendar. Sequential single hue, light -> dark. */
export function ContributionHeatmap({ data }: { data: Heatmap }) {
  const firstRow = useMemo(
    () => (data.cells.length ? parseDate(data.cells[0].date).getDay() : 0),
    [data],
  );

  return (
    <div className="overflow-x-auto pb-1">
      <div
        className="inline-grid gap-[3px]"
        style={{
          gridTemplateRows: "repeat(7, 12px)",
          gridAutoFlow: "column",
          gridAutoColumns: "12px",
        }}
      >
        {data.cells.map((c, i) => (
          <div
            key={c.date}
            title={`${c.count} completion${c.count === 1 ? "" : "s"} · ${c.date}`}
            className="h-3 w-3 rounded-[3px] transition-transform hover:scale-[1.18] hover:ring-1 hover:ring-accent/50"
            style={{
              backgroundColor: cellColor(c.level),
              ...(i === 0 ? { gridRowStart: firstRow + 1 } : null),
            }}
          />
        ))}
      </div>
    </div>
  );
}

export function HeatmapLegend() {
  return (
    <div className="flex items-center gap-1.5 text-[11px] text-ink-muted">
      <span>Less</span>
      {[0, 1, 2, 3, 4].map((l) => (
        <span
          key={l}
          className="h-3 w-3 rounded-[3px]"
          style={{ backgroundColor: cellColor(l) }}
        />
      ))}
      <span>More</span>
    </div>
  );
}
