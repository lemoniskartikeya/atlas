import { clamp } from "@/lib/utils";

interface ProgressRingProps {
  value: number; // 0..1
  size?: number;
  stroke?: number;
  primary?: string; // number, e.g. "72"
  caption?: string; // small label under the number
}

/** A single-value magnitude meter (sequential, one hue). */
export function ProgressRing({
  value,
  size = 108,
  stroke = 9,
  primary,
  caption,
}: ProgressRingProps) {
  const v = clamp(value, 0, 1);
  const r = (size - stroke) / 2;
  const circumference = 2 * Math.PI * r;
  const dash = circumference * v;

  return (
    <div className="relative inline-grid place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="rgb(var(--ink) / 0.09)"
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="rgb(var(--accent))"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${dash} ${circumference - dash}`}
          style={{ transition: "stroke-dasharray 0.8s cubic-bezier(0.22,1,0.36,1)" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        {primary !== undefined && (
          <span className="text-[26px] font-semibold leading-none tracking-tight tabular-nums text-ink">
            {primary}
          </span>
        )}
        {caption && <span className="mt-1 text-[11px] text-ink-muted">{caption}</span>}
      </div>
    </div>
  );
}
