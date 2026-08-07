import { useCallback, useLayoutEffect, useMemo, useRef, useState } from "react";
import { cn } from "@/lib/utils";

export interface LinePoint {
  value: number;
  /** Short axis label, e.g. "12 Aug". */
  label: string;
}

interface LineChartProps {
  data: LinePoint[];
  height?: number;
  className?: string;
  /** Renders the big number in the tooltip. */
  formatValue?: (n: number) => string;
  /** Unit suffix shown small next to the tooltip value, e.g. "/100". */
  unit?: string;
  /** Fix the y-domain instead of deriving it from the data. */
  domain?: [number, number];
  /** Called as the cursor moves so the parent can show live context. */
  onHoverChange?: (index: number | null) => void;
}

const PAD = { left: 4, right: 4, top: 14, bottom: 18 };

/**
 * Interactive single-series chart.
 *
 * The whole plot area is the hit target — not just the vertices — so the
 * readout tracks the cursor continuously across the series. Geometry is
 * computed in real pixels (via ResizeObserver) rather than a stretched
 * viewBox, which keeps strokes an even width and makes tooltip placement
 * exact instead of approximate.
 */
export function LineChart({
  data,
  height = 180,
  className,
  formatValue = (n) => String(Math.round(n)),
  unit,
  domain,
  onHoverChange,
}: LineChartProps) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(0);
  const [idx, setIdx] = useState<number | null>(null);

  useLayoutEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => setW(entry.contentRect.width));
    ro.observe(el);
    setW(el.getBoundingClientRect().width);
    return () => ro.disconnect();
  }, []);

  const geom = useMemo(() => {
    if (!w || data.length === 0) return null;
    const innerW = Math.max(1, w - PAD.left - PAD.right);
    const innerH = Math.max(1, height - PAD.top - PAD.bottom);

    const values = data.map((d) => d.value);
    let lo = domain ? domain[0] : Math.min(...values);
    let hi = domain ? domain[1] : Math.max(...values);
    if (!domain) {
      // Breathing room so the line never kisses the frame, and a floor on the
      // span so a flat series renders as a flat line rather than noise.
      const span = Math.max(hi - lo, 1);
      lo -= span * 0.18;
      hi += span * 0.18;
    }
    const span = hi - lo || 1;

    const x = (i: number) =>
      PAD.left + (data.length === 1 ? innerW / 2 : (i / (data.length - 1)) * innerW);
    const y = (v: number) => PAD.top + innerH - ((v - lo) / span) * innerH;

    const pts = data.map((d, i) => [x(i), y(d.value)] as const);
    return { innerW, innerH, x, y, pts, lo, hi };
  }, [w, height, data, domain]);

  /** Monotone-ish cubic through the points — smooth without overshooting. */
  const paths = useMemo(() => {
    if (!geom) return null;
    const p = geom.pts;
    if (p.length === 1) {
      const [px, py] = p[0];
      return { line: `M${px},${py}`, area: `M${px},${py}` };
    }
    let d = `M${p[0][0]},${p[0][1]}`;
    for (let i = 0; i < p.length - 1; i++) {
      const p0 = p[i === 0 ? 0 : i - 1];
      const p1 = p[i];
      const p2 = p[i + 1];
      const p3 = p[i + 2 < p.length ? i + 2 : p.length - 1];
      const t = 0.22; // low tension keeps it honest to the data
      const c1x = p1[0] + (p2[0] - p0[0]) * t;
      const c1y = p1[1] + (p2[1] - p0[1]) * t;
      const c2x = p2[0] - (p3[0] - p1[0]) * t;
      const c2y = p2[1] - (p3[1] - p1[1]) * t;
      d += ` C${c1x},${c1y} ${c2x},${c2y} ${p2[0]},${p2[1]}`;
    }
    const base = height - PAD.bottom;
    const area = `${d} L${p[p.length - 1][0]},${base} L${p[0][0]},${base} Z`;
    return { line: d, area };
  }, [geom, height]);

  const setHover = useCallback(
    (next: number | null) => {
      setIdx((cur) => {
        if (cur !== next) onHoverChange?.(next);
        return next;
      });
    },
    [onHoverChange],
  );

  const onMove = (e: React.PointerEvent) => {
    if (!geom) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const rel = e.clientX - rect.left - PAD.left;
    const ratio = geom.innerW === 0 ? 0 : rel / geom.innerW;
    const i = Math.round(ratio * (data.length - 1));
    setHover(Math.max(0, Math.min(data.length - 1, i)));
  };

  if (data.length === 0) return null;

  const active = idx != null ? data[idx] : null;
  const gradId = "line-fill";

  return (
    <div ref={wrapRef} className={cn("relative select-none", className)} style={{ height }}>
      {geom && paths && (
        <>
          <svg
            width={w}
            height={height}
            className="block touch-none"
            onPointerMove={onMove}
            onPointerLeave={() => setHover(null)}
          >
            <defs>
              <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="rgb(var(--accent))" stopOpacity="0.26" />
                <stop offset="100%" stopColor="rgb(var(--accent))" stopOpacity="0" />
              </linearGradient>
            </defs>

            {/* Baseline grid — three quiet rules, no boxed axes. */}
            {[0, 0.5, 1].map((f) => {
              const gy = PAD.top + geom.innerH * f;
              return (
                <line
                  key={f}
                  x1={PAD.left}
                  x2={w - PAD.right}
                  y1={gy}
                  y2={gy}
                  stroke="rgb(var(--ink) / 0.07)"
                  strokeWidth={1}
                  strokeDasharray={f === 1 ? undefined : "3 5"}
                />
              );
            })}

            <path d={paths.area} fill={`url(#${gradId})`} />
            <path
              d={paths.line}
              fill="none"
              stroke="rgb(var(--accent))"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
            />

            {active && idx != null && (
              <>
                <line
                  x1={geom.x(idx)}
                  x2={geom.x(idx)}
                  y1={PAD.top}
                  y2={height - PAD.bottom}
                  stroke="rgb(var(--accent) / 0.35)"
                  strokeWidth={1}
                />
                <circle
                  cx={geom.x(idx)}
                  cy={geom.y(active.value)}
                  r={7}
                  fill="rgb(var(--accent) / 0.16)"
                />
                <circle
                  cx={geom.x(idx)}
                  cy={geom.y(active.value)}
                  r={3.5}
                  fill="rgb(var(--accent))"
                  stroke="rgb(var(--panel))"
                  strokeWidth={2}
                />
              </>
            )}

            {/* Endpoint marker so the series reads as "now" at rest. */}
            {!active && (
              <circle
                cx={geom.pts[geom.pts.length - 1][0]}
                cy={geom.pts[geom.pts.length - 1][1]}
                r={3.5}
                fill="rgb(var(--accent))"
                stroke="rgb(var(--panel))"
                strokeWidth={2}
              />
            )}
          </svg>

          {/* Compact tooltip: value large, date small underneath. Sized to its
              content and clamped inside the plot so it never runs off-edge. */}
          {active && idx != null && (
            <div
              className="glass pointer-events-none absolute z-10 rounded-lg px-2 py-1 text-center leading-tight shadow-sm"
              style={{
                left: Math.min(Math.max(geom.x(idx), 30), Math.max(w - 30, 30)),
                top: Math.max(geom.y(active.value) - 46, 0),
                transform: "translateX(-50%)",
              }}
            >
              <div className="text-[13px] font-semibold tnum text-ink">
                {formatValue(active.value)}
                {unit && <span className="text-[10px] font-normal text-ink-faint">{unit}</span>}
              </div>
              <div className="text-[10px] text-ink-faint">{active.label}</div>
            </div>
          )}

          {/* x-axis: first and last only — a dated series doesn't need a ruler. */}
          <div className="pointer-events-none absolute inset-x-0 bottom-0 flex justify-between px-1 text-[10px] text-ink-faint">
            <span>{data[0].label}</span>
            <span>{data[data.length - 1].label}</span>
          </div>
        </>
      )}
    </div>
  );
}
