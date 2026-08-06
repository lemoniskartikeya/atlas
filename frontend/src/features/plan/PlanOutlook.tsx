import { AlertTriangle, Flame, Gauge, TrendingUp } from "lucide-react";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ProgressRing } from "@/components/ui/progress-ring";
import { usePredictions } from "@/hooks/queries";
import { cn } from "@/lib/utils";
import type { BurnoutSignal, StreakRisk } from "@/lib/types";

const BURNOUT_COLOR: Record<BurnoutSignal["level"], string> = {
  low: "rgb(var(--success))",
  moderate: "rgb(var(--warn))",
  elevated: "#d0605e",
};

function LevelChip({ level }: { level: StreakRisk["level"] | BurnoutSignal["level"] }) {
  const warm = level === "high" || level === "elevated";
  const mid = level === "medium" || level === "moderate";
  return (
    <span
      className="rounded-full px-2 py-0.5 text-[10px] font-semibold capitalize"
      style={{
        color: warm ? "#d0605e" : mid ? "rgb(var(--warn))" : "rgb(var(--success))",
        backgroundColor: warm
          ? "rgb(208 96 94 / 0.12)"
          : mid
            ? "rgb(var(--warn) / 0.12)"
            : "rgb(var(--success) / 0.12)",
      }}
    >
      {level}
    </span>
  );
}

function ExpectedBlock({
  done,
  due,
  expectedTotal,
  expectedRate,
  reason,
}: {
  done: number;
  due: number;
  expectedTotal: number;
  expectedRate: number;
  reason: string;
}) {
  return (
    <div className="flex items-center gap-4">
      <ProgressRing value={expectedRate} primary={expectedTotal.toFixed(1)} caption={`of ${due}`} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5 text-sm font-medium text-ink">
          <TrendingUp size={14} className="text-accent" />
          Expected to finish
        </div>
        <p className="mt-0.5 text-[12px] leading-relaxed text-ink-muted">{reason}</p>
        <p className="mt-1 text-[11px] tabular-nums text-ink-faint">
          {done} done · {due - done} to go
        </p>
      </div>
    </div>
  );
}

export function PlanOutlook() {
  const { data, isLoading } = usePredictions();

  if (isLoading || !data) {
    return <Skeleton className="h-40 rounded-2xl" />;
  }

  const { expected_completion: ec, streak_risks: risks, burnout } = data;
  const burnoutPct = Math.round(burnout.score * 100);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Gauge size={15} className="text-accent" />
          <CardTitle>Outlook</CardTitle>
        </div>
        {data.model_backed && data.reliability != null && (
          <span
            title="Forecasts use your trained completion model"
            className="rounded-full bg-accent-soft px-2 py-0.5 text-[10px] font-semibold text-accent"
          >
            model · {Math.round(data.reliability * 100)}%
          </span>
        )}
      </CardHeader>
      <CardBody className="space-y-4">
        <ExpectedBlock
          done={ec.done}
          due={ec.due}
          expectedTotal={ec.expected_total}
          expectedRate={ec.expected_rate}
          reason={ec.reason}
        />

        {/* Streak-break risk */}
        <div className="border-t border-border/10 pt-3">
          <div className="mb-2 flex items-center gap-1.5 text-[13px] font-medium text-ink">
            <Flame size={13} className="text-accent" />
            Streaks at risk
          </div>
          {risks.length === 0 ? (
            <p className="text-[12px] text-ink-muted">No active streaks are at risk today. Nice.</p>
          ) : (
            <div className="space-y-2">
              {risks.map((r) => (
                <div key={r.habit_id} className="glass-inset rounded-xl p-2.5">
                  <div className="flex items-center gap-2">
                    <span className="min-w-0 flex-1 truncate text-sm text-ink">{r.title}</span>
                    <span className="shrink-0 text-[11px] tabular-nums text-ink-muted">
                      {r.current_streak}d · {Math.round(r.risk * 100)}% risk
                    </span>
                    <LevelChip level={r.level} />
                  </div>
                  <p className="mt-1 text-[11px] leading-relaxed text-ink-faint">{r.reason}</p>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Burnout meter */}
        <div className="border-t border-border/10 pt-3">
          <div className="mb-1.5 flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-[13px] font-medium text-ink">
              <AlertTriangle size={13} className="text-accent" />
              Burnout signal
            </div>
            <LevelChip level={burnout.level} />
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-ink/10">
            <div
              className={cn("h-full rounded-full transition-[width] duration-700")}
              style={{ width: `${burnoutPct}%`, backgroundColor: BURNOUT_COLOR[burnout.level] }}
            />
          </div>
          <p className="mt-1.5 text-[11px] leading-relaxed text-ink-faint">{burnout.reason}</p>
        </div>
      </CardBody>
    </Card>
  );
}
