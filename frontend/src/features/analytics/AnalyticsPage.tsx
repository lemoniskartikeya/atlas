import { type ReactNode } from "react";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { Stat } from "@/components/ui/stat";
import { Skeleton } from "@/components/ui/skeleton";
import { BarChart } from "@/components/charts/bar-chart";
import { Scatter } from "@/components/charts/scatter";
import { ContributionHeatmap, HeatmapLegend } from "@/components/charts/heatmap";
import {
  useAnalyticsCorrelations,
  useAnalyticsSummary,
  useAnalyticsWeekly,
  useHeatmap,
} from "@/hooks/queries";
import { cn, pct } from "@/lib/utils";
import type { CorrelationPair } from "@/lib/types";
import { WeeklyReviewCard } from "./WeeklyReviewCard";
import { InsightsCard } from "./InsightsCard";
import { HeatmapCard, StreaksCard, WellbeingCard } from "@/features/dashboard/widgets";
import { useDashboard } from "@/hooks/queries";

const WD = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function KpiTile({ label, value, sub }: { label: string; value: ReactNode; sub?: ReactNode }) {
  return (
    <Card className="p-4">
      <Stat label={label} value={value} sub={sub} />
    </Card>
  );
}

function CorrelationCard({ pair }: { pair: CorrelationPair }) {
  const r = pair.coefficient;
  const chip = r == null ? "—" : `${r > 0 ? "+" : ""}${r.toFixed(2)}`;
  const tone =
    r == null ? "text-ink-faint" : Math.abs(r) >= 0.5 ? "text-accent" : "text-ink-muted";
  return (
    <Card className="p-4">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-sm font-medium text-ink">{pair.x_label} → completion</span>
        <span
          className={cn(
            "rounded-full bg-ink/[0.06] px-2 py-0.5 text-[11px] font-semibold tabular-nums",
            tone,
          )}
        >
          r {chip}
        </span>
      </div>
      <Scatter points={pair.points} xLabel={pair.x_label} yLabel="Completion" />
      <p className="mt-2 text-[12px] leading-relaxed text-ink-muted">{pair.interpretation}</p>
    </Card>
  );
}

function AnalyticsSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-10 w-48" />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton key={i} className="h-20 rounded-2xl" />
        ))}
      </div>
      <Skeleton className="h-56 rounded-2xl" />
      <div className="grid gap-3 lg:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-64 rounded-2xl" />
        ))}
      </div>
    </div>
  );
}

export function AnalyticsPage() {
  const { data: s } = useAnalyticsSummary();
  const { data: weekly } = useAnalyticsWeekly(12);
  const { data: corr } = useAnalyticsCorrelations(90);
  const { data: heat } = useHeatmap(365);
  // Wellbeing and streaks moved off the dashboard; they are retrospective,
  // and this is where you come to look back.
  const { data: dash } = useDashboard();

  if (!s) return <AnalyticsSkeleton />;

  const maxCat = Math.max(1, ...s.by_category.map((c) => c.count));

  return (
    <div className="animate-fade-in space-y-4">
      <div>
        <h2 className="text-xl font-display font-semibold text-ink">Analytics</h2>
        <p className="text-sm text-ink-muted">Patterns across your history.</p>
      </div>

      <WeeklyReviewCard />

      <InsightsCard />

      <HeatmapCard />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <KpiTile label="Completions" value={s.total_completions} />
        <KpiTile label="Best streak" value={`${s.best_current_streak}d`} sub={`longest ${s.longest_streak_ever}d`} />
        <KpiTile label="Deep work" value={`${s.deep_work_hours}h`} />
        <KpiTile
          label="Avg mood"
          value={s.avg_mood ?? "—"}
          sub={s.avg_energy != null ? `energy ${s.avg_energy}` : undefined}
        />
        <KpiTile label="Avg sleep" value={s.avg_sleep != null ? `${s.avg_sleep}h` : "—"} />
        <KpiTile label="Tasks done" value={s.tasks_completed} sub={`${s.tasks_open} open`} />
        <KpiTile label="Active habits" value={s.active_habits} />
        <KpiTile label="Journal days" value={s.journal_entries} />
      </div>

      {dash && (
        <div className="grid gap-4 sm:grid-cols-2">
          <WellbeingCard mood={dash.mood} energy={dash.energy} sleep={dash.sleep_hours} />
          <StreaksCard streaks={dash.top_streaks} />
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Weekly productivity</CardTitle>
          <span className="text-[11px] text-ink-muted">completions / week</span>
        </CardHeader>
        <CardBody>
          {weekly ? (
            <BarChart
              data={weekly.weeks.map((w) => ({ label: w.label, value: w.completions }))}
              highlightLast
              formatValue={(n) => `${n} completions`}
            />
          ) : (
            <Skeleton className="h-40" />
          )}
        </CardBody>
      </Card>

      <div>
        <h3 className="mb-2 px-1 text-[13px] font-semibold text-ink">
          What moves your completion rate
        </h3>
        <div className="grid gap-3 lg:grid-cols-3">
          {corr
            ? corr.pairs.map((p) => <CorrelationCard key={p.key} pair={p} />)
            : Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-64 rounded-2xl" />
              ))}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>By weekday</CardTitle>
          </CardHeader>
          <CardBody>
            <BarChart
              data={s.by_weekday.map((v, i) => ({ label: WD[i], value: v }))}
              formatValue={(n) => `${n} completions`}
            />
          </CardBody>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>By category</CardTitle>
          </CardHeader>
          <CardBody className="space-y-2.5">
            {s.by_category.map((c) => (
              <div key={c.category}>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-ink">{c.category}</span>
                  <span className="tabular-nums text-ink-muted">{c.count}</span>
                </div>
                <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-ink/10">
                  <div
                    className="h-full rounded-full bg-accent"
                    style={{ width: `${(c.count / maxCat) * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Top habits</CardTitle>
        </CardHeader>
        <CardBody>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-wide text-ink-faint">
                  <th className="pb-2 font-medium">Habit</th>
                  <th className="pb-2 text-right font-medium">Streak</th>
                  <th className="pb-2 text-right font-medium">Best</th>
                  <th className="pb-2 text-right font-medium">Success</th>
                  <th className="pb-2 text-right font-medium">30-day</th>
                  <th className="pb-2 text-right font-medium">Total</th>
                </tr>
              </thead>
              <tbody>
                {s.top_habits.map((h) => (
                  <tr key={h.id} className="border-t border-border/10">
                    <td className="py-2 text-ink">{h.title}</td>
                    <td className="py-2 text-right tabular-nums text-ink-muted">{h.current_streak}</td>
                    <td className="py-2 text-right tabular-nums text-ink-muted">{h.longest_streak}</td>
                    <td className="py-2 text-right tabular-nums text-ink-muted">{pct(h.success_rate)}</td>
                    <td className="py-2 text-right tabular-nums text-ink-muted">{pct(h.consistency_30d)}</td>
                    <td className="py-2 text-right tabular-nums text-ink-muted">{h.total_completions}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Consistency</CardTitle>
          {heat && (
            <span className="text-[11px] text-ink-muted">{heat.total} completions · last year</span>
          )}
        </CardHeader>
        <CardBody>
          {heat ? (
            <>
              <ContributionHeatmap data={heat} />
              <div className="mt-3 flex justify-end">
                <HeatmapLegend />
              </div>
            </>
          ) : (
            <Skeleton className="h-24 w-full" />
          )}
        </CardBody>
      </Card>
    </div>
  );
}
