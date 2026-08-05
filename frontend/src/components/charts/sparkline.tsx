import { useRef, useState, type MouseEvent } from "react";
import { cn } from "@/lib/utils";

interface SparklineProps {
  data: number[];
  height?: number;
  className?: string;
  formatY?: (n: number) => string;
  labels?: string[];
}

/** Compact single-series line over time. 2px non-scaling stroke, hover readout. */
export function Sparkline({ data, height = 46, className, formatY, labels }: SparklineProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [idx, setIdx] = useState<number | null>(null);

  if (!data.length) return null;

  const W = 100;
  const H = height;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const span = max - min || 1;
  const x = (i: number) => (data.length === 1 ? 0 : (i / (data.length - 1)) * W);
  const y = (v: number) => H - 3 - ((v - min) / span) * (H - 6);

  const line = data.map((v, i) => `${x(i)},${y(v)}`).join(" ");
  const area = `0,${H} ${line} ${W},${H}`;

  const onMove = (e: MouseEvent) => {
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const ratio = (e.clientX - rect.left) / rect.width;
    setIdx(Math.max(0, Math.min(data.length - 1, Math.round(ratio * (data.length - 1)))));
  };

  return (
    <div
      ref={ref}
      className={cn("relative", className)}
      style={{ height: H }}
      onMouseMove={onMove}
      onMouseLeave={() => setIdx(null)}
    >
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="h-full w-full">
        <defs>
          <linearGradient id="spark-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgb(var(--accent))" stopOpacity="0.2" />
            <stop offset="100%" stopColor="rgb(var(--accent))" stopOpacity="0" />
          </linearGradient>
        </defs>
        <polygon points={area} fill="url(#spark-fill)" />
        <polyline
          points={line}
          fill="none"
          stroke="rgb(var(--accent))"
          strokeWidth={2}
          vectorEffect="non-scaling-stroke"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
      </svg>

      {idx !== null && (
        <>
          <div
            className="pointer-events-none absolute bottom-0 top-0 w-px bg-accent/25"
            style={{ left: `${x(idx)}%` }}
          />
          <div
            className="pointer-events-none absolute h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-accent ring-2 ring-panel"
            style={{ left: `${x(idx)}%`, top: `${(y(data[idx]) / H) * 100}%` }}
          />
          <div
            className="glass pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-[130%] whitespace-nowrap rounded-lg px-2 py-1 text-[11px] font-medium text-ink"
            style={{ left: `${clampPct(x(idx))}%`, top: `${(y(data[idx]) / H) * 100}%` }}
          >
            {formatY ? formatY(data[idx]) : data[idx]}
            {labels?.[idx] && <span className="text-ink-faint"> · {labels[idx]}</span>}
          </div>
        </>
      )}
    </div>
  );
}

function clampPct(n: number): number {
  return Math.max(8, Math.min(92, n));
}
