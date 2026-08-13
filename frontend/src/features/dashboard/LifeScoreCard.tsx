import { useMemo, useState } from "react";
import { ArrowDownRight, ArrowRight, ArrowUpRight } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Stat } from "@/components/ui/stat";
import { ProgressRing } from "@/components/ui/progress-ring";
import { LineChart, type LinePoint } from "@/components/charts/line-chart";
import { cn, pct, trailingDayLabels } from "@/lib/utils";
import type { Dashboard } from "@/lib/types";

/** One readout line. Reads as prose, not a legend. */
function Insight({
  tone = "flat",
  children,
}: {
  tone?: "up" | "down" | "flat";
  children: React.ReactNode;
}) {
  const Icon = tone === "up" ? ArrowUpRight : tone === "down" ? ArrowDownRight : ArrowRight;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 text-[12px]",
        tone === "up" && "text-success",
        tone === "down" && "text-danger",
        tone === "flat" && "text-ink-muted",
      )}
    >
      <Icon size={13} className="shrink-0" />
      {children}
    </span>
  );
}

/**
 * The dashboard's headline: composite life score, supporting stats, and the
 * trend as a fully interactive chart.
 *
 * The insight line under the chart is the point of the interaction — at rest
 * it summarises the whole window; while the cursor is anywhere over the plot
 * it reports that specific day in context (day-over-day move, distance from
 * the window average). So the reading is continuous, not just at vertices.
 */
export function LifeScoreCard({ d }: { d: Dashboard }) {
  const [hover, setHover] = useState<number | null>(null);
  const leader = d.top_streaks[0];

  const points: LinePoint[] = useMemo(() => {
    const labels = trailingDayLabels(d.life_score_trend.length);
    return d.life_score_trend.map((value, i) => ({ value, label: labels[i] }));
  }, [d.life_score_trend]);

  const stats = useMemo(() => {
    const v = d.life_score_trend;
    if (v.length === 0) return null;
    const avg = v.reduce((a, b) => a + b, 0) / v.length;
    let bestI = 0;
    let worstI = 0;
    v.forEach((n, i) => {
      if (n > v[bestI]) bestI = i;
      if (n < v[worstI]) worstI = i;
    });
    return { avg, bestI, worstI, change: v[v.length - 1] - v[0] };
  }, [d.life_score_trend]);

  const insight = (() => {
    if (!stats || points.length === 0) return null;

    if (hover != null) {
      // `hover` is a continuous position in the series, so the reading between
      // two days is interpolated rather than snapped to whichever is closer.
      const lo = Math.floor(hover);
      const hi = Math.min(lo + 1, points.length - 1);
      const frac = hover - lo;
      const value = points[lo].value + (points[hi].value - points[lo].value) * frac;

      const nearest = Math.min(points.length - 1, Math.max(0, Math.round(hover)));
      const prev = nearest > 0 ? points[nearest - 1] : null;
      const delta = prev ? points[nearest].value - prev.value : 0;
      const vsAvg = value - stats.avg;
      const between = frac > 0.02 && frac < 0.98 && lo !== hi;

      return (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="text-[12px] font-medium text-ink">
            {between ? `${points[lo].label} → ${points[hi].label}` : points[nearest].label}
          </span>
          <span className="text-[12px] tnum text-ink-muted">{value.toFixed(1)}</span>
          {prev && (
            <Insight tone={delta > 0.5 ? "up" : delta < -0.5 ? "down" : "flat"}>
              {delta > 0 ? "+" : ""}
              {delta.toFixed(1)} day over day
            </Insight>
          )}
          <Insight tone={vsAvg > 0 ? "up" : vsAvg < 0 ? "down" : "flat"}>
            {Math.abs(vsAvg).toFixed(1)} {vsAvg >= 0 ? "above" : "below"} the {points.length}-day
            average
          </Insight>
        </div>
      );
    }

    return (
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <Insight tone={stats.change > 0.5 ? "up" : stats.change < -0.5 ? "down" : "flat"}>
          {stats.change > 0 ? "+" : ""}
          {stats.change.toFixed(1)} over {points.length} days
        </Insight>
        <span className="text-[12px] text-ink-faint">
          avg {stats.avg.toFixed(1)} · best {Math.round(points[stats.bestI].value)} on{" "}
          {points[stats.bestI].label}
        </span>
      </div>
    );
  })();

  return (
    <Card className="p-5">
      <div className="flex flex-col gap-6 sm:flex-row sm:items-center">
        <div className="flex shrink-0 items-center gap-4">
          <ProgressRing
            value={d.life_score / 100}
            primary={String(Math.round(d.life_score))}
            caption="Life Score"
          />
        </div>
        <div className="grid flex-1 grid-cols-2 gap-x-4 gap-y-4 sm:grid-cols-4">
          <Stat label="Weekly" value={pct(d.weekly_consistency)} sub="consistency" />
          <Stat
            label="Focus"
            value={d.focus_score != null ? Math.round(d.focus_score) : "—"}
            sub="today"
          />
          <Stat label="Habits" value={`${d.habits_completed}/${d.habits_total}`} sub="done today" />
          <Stat
            label="Top streak"
            value={leader ? `${leader.current_streak}d` : "0"}
            sub={leader?.title ?? "—"}
            accent
          />
        </div>
      </div>

      {points.length > 1 && (
        <div className="mt-5 border-t border-border/10 pt-4">
          {/* No "hover for details" hint: the whole plot is the hit target, and
              anyone who moves the pointer over it finds that out immediately.
              A label explaining an interaction costs more than it teaches. */}
          <div className="mb-1">
            <span className="text-[11px] font-medium uppercase tracking-[0.06em] text-ink-muted">
              Trend
            </span>
          </div>
          <LineChart
            data={points}
            height={168}
            unit="/100"
            onHoverChange={setHover}
            // One decimal, so a reading between two days visibly moves with the
            // cursor instead of stepping between whole numbers.
            formatValue={(n) => n.toFixed(1)}
          />
          <div className="mt-2 min-h-[20px]">{insight}</div>
        </div>
      )}
    </Card>
  );
}
