import { useState } from "react";
import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Minus,
  Sparkles,
  Target,
  TrendingDown,
  TrendingUp,
  Trophy,
} from "lucide-react";
import { Card, CardBody } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useWeeklyReview } from "@/hooks/queries";
import { cn } from "@/lib/utils";
import type { ReviewItem, ReviewMetric } from "@/lib/types";

function fmtDelta(m: ReviewMetric): string | null {
  if (m.delta == null || m.direction === "flat") return null;
  const sign = m.delta > 0 ? "+" : "";
  if (m.key === "completion") return `${sign}${Math.round(m.delta * 100)} pts`;
  if (m.key === "sleep") return `${sign}${m.delta.toFixed(1)}h`;
  return `${sign}${m.delta.toFixed(1)}`;
}

function MetricTile({ m }: { m: ReviewMetric }) {
  const delta = fmtDelta(m);
  const up = m.direction === "up";
  const down = m.direction === "down";
  const color = up ? "rgb(var(--success))" : down ? "#d0605e" : "rgb(var(--ink-faint))";
  return (
    <div className="glass-inset rounded-xl p-3">
      <div className="text-[10px] uppercase tracking-wide text-ink-faint">{m.label}</div>
      <div className="mt-1 flex items-baseline gap-1.5">
        <span className="text-lg font-semibold tabular-nums text-ink">{m.value}</span>
        {delta && (
          <span className="flex items-center gap-0.5 text-[11px] font-medium tabular-nums" style={{ color }}>
            {up ? <TrendingUp size={11} /> : down ? <TrendingDown size={11} /> : <Minus size={11} />}
            {delta}
          </span>
        )}
      </div>
    </div>
  );
}

function ItemList({
  items,
  tone,
}: {
  items: ReviewItem[];
  tone: "win" | "watch";
}) {
  const isWin = tone === "win";
  const color = isWin ? "rgb(var(--success))" : "#d0605e";
  return (
    <div>
      <div className="mb-1.5 flex items-center gap-1.5 text-[12px] font-semibold text-ink">
        {isWin ? (
          <Trophy size={13} style={{ color }} />
        ) : (
          <AlertTriangle size={13} style={{ color }} />
        )}
        {isWin ? "Wins" : "Watch-outs"}
      </div>
      {items.length === 0 ? (
        <p className="text-[12px] text-ink-faint">
          {isWin ? "No standout wins yet this week." : "Nothing slipping — nice."}
        </p>
      ) : (
        <div className="space-y-1.5">
          {items.map((it) => (
            <div key={(it.habit_id ?? "") + it.title} className="glass-inset rounded-lg p-2">
              <div className="flex items-center gap-1.5">
                <span
                  className="h-1.5 w-1.5 shrink-0 rounded-full"
                  style={{ backgroundColor: color }}
                />
                <span className="truncate text-[13px] font-medium text-ink">{it.title}</span>
              </div>
              <p className="mt-0.5 pl-3 text-[11px] leading-relaxed text-ink-muted">{it.detail}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function WeeklyReviewCard() {
  const [offset, setOffset] = useState(0);
  const { data, isFetching } = useWeeklyReview(offset);

  return (
    <Card>
      <div className="flex items-center justify-between px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-accent-soft text-accent">
            <Sparkles size={15} />
          </span>
          <div>
            <div className="text-sm font-semibold text-ink">Weekly review</div>
            <div className="text-[12px] text-ink-muted">
              {data ? data.label : "—"}
              {data && !data.is_current && (
                <span className="text-ink-faint">
                  {" · "}
                  {data.start} → {data.end}
                </span>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setOffset((o) => o + 1)}
            aria-label="Previous week"
            title="Previous week"
            className="grid h-8 w-8 place-items-center rounded-lg text-ink-muted transition-colors hover:bg-ink/5 hover:text-ink"
          >
            <ChevronLeft size={16} />
          </button>
          <button
            onClick={() => setOffset((o) => Math.max(0, o - 1))}
            disabled={!data?.can_go_forward}
            aria-label="Next week"
            title="Next week"
            className="grid h-8 w-8 place-items-center rounded-lg text-ink-muted transition-colors enabled:hover:bg-ink/5 enabled:hover:text-ink disabled:opacity-30"
          >
            <ChevronRight size={16} />
          </button>
        </div>
      </div>

      <CardBody className={cn("border-t border-border/10 pt-4", isFetching && "opacity-70")}>
        {!data ? (
          <Skeleton className="h-40" />
        ) : (
          <div className="space-y-4">
            <p className="text-[13px] leading-relaxed text-ink">{data.narrative}</p>

            <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
              {data.metrics.map((m) => (
                <MetricTile key={m.key} m={m} />
              ))}
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <ItemList items={data.wins} tone="win" />
              <ItemList items={data.watchouts} tone="watch" />
            </div>

            {data.focus.length > 0 && (
              <div>
                <div className="mb-1.5 flex items-center gap-1.5 text-[12px] font-semibold text-ink">
                  <Target size={13} className="text-accent" />
                  Next week
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {data.focus.map((f) => (
                    <span
                      key={f}
                      className="rounded-full bg-accent-soft px-2.5 py-1 text-[11px] font-medium text-accent"
                    >
                      {f}
                    </span>
                  ))}
                </div>
              </div>
            )}

            <p className="text-[10px] text-ink-faint">
              Generated from your own data — private, and every number is yours to check.
            </p>
          </div>
        )}
      </CardBody>
    </Card>
  );
}
