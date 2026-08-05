import type { CorrelationPoint } from "@/lib/types";

/** Scatter with a least-squares trend line. Single series, round HTML markers. */
export function Scatter({
  points,
  xLabel,
  yLabel,
  height = 170,
}: {
  points: CorrelationPoint[];
  xLabel: string;
  yLabel: string;
  height?: number;
}) {
  if (points.length < 2) {
    return (
      <div
        className="grid place-items-center rounded-xl border border-border/10 bg-ink/[0.02] text-[12px] text-ink-faint"
        style={{ height }}
      >
        Not enough data yet
      </div>
    );
  }

  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  const xmin = Math.min(...xs);
  const xmax = Math.max(...xs);
  const ymin = Math.min(...ys);
  const ymax = Math.max(...ys);
  const xr = xmax - xmin || 1;
  const yr = ymax - ymin || 1;
  const px = (x: number) => ((x - xmin) / xr) * 100;
  const py = (y: number) => 100 - ((y - ymin) / yr) * 100;

  // Least-squares slope/intercept for the trend line.
  const n = points.length;
  const mx = xs.reduce((a, b) => a + b, 0) / n;
  const my = ys.reduce((a, b) => a + b, 0) / n;
  const denom = xs.reduce((a, x) => a + (x - mx) ** 2, 0);
  const slope = denom ? points.reduce((a, p) => a + (p.x - mx) * (p.y - my), 0) / denom : 0;
  const intercept = my - slope * mx;

  return (
    <div className="relative rounded-xl border border-border/10 bg-ink/[0.02]" style={{ height }}>
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 h-full w-full">
        <line
          x1={px(xmin)}
          y1={py(slope * xmin + intercept)}
          x2={px(xmax)}
          y2={py(slope * xmax + intercept)}
          stroke="rgb(var(--accent))"
          strokeWidth={2}
          strokeDasharray="4 3"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      {points.map((p, i) => (
        <div
          key={i}
          title={`${xLabel}: ${p.x} · ${yLabel}: ${p.y}%`}
          className="absolute h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-accent/70 ring-1 ring-panel"
          style={{ left: `${px(p.x)}%`, top: `${py(p.y)}%` }}
        />
      ))}
      <span className="absolute bottom-1 right-2 text-[10px] text-ink-faint">{xLabel} →</span>
      <span className="absolute left-2 top-1 text-[10px] text-ink-faint">↑ {yLabel}</span>
    </div>
  );
}
