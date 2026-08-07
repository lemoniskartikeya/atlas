import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  Brain,
  Check,
  Clock,
  Loader2,
  Minus,
  Play,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { LineChart, type LinePoint } from "@/components/charts/line-chart";
import { api } from "@/lib/api";
import { cn, pct } from "@/lib/utils";

/** "in 3 days" / "2 hours ago" — relative, because exact times don't matter here. */
function relativeTime(iso?: string | null): string {
  if (!iso) return "—";
  const diff = new Date(iso).getTime() - Date.now();
  const abs = Math.abs(diff);
  const mins = Math.round(abs / 60_000);
  const hours = Math.round(abs / 3_600_000);
  const days = Math.round(abs / 86_400_000);
  const size = days >= 1 ? `${days}d` : hours >= 1 ? `${hours}h` : `${mins}m`;
  return diff >= 0 ? `in ${size}` : `${size} ago`;
}

const STATUS_TONE: Record<string, string> = {
  ok: "text-success",
  skipped: "text-ink-faint",
  error: "text-danger",
};

/* ------------------------------------------------------------ model quality */

function ModelQuality() {
  const { data, isLoading } = useQuery({
    queryKey: ["ml", "history"],
    queryFn: () => api.modelHistory(),
  });

  if (isLoading) return <Skeleton className="h-40 rounded-xl" />;
  if (!data || data.total === 0) {
    return (
      <p className="text-[13px] text-ink-muted">
        No model trained yet. Once you have a few weeks of history, Atlas trains one and its
        accuracy shows up here.
      </p>
    );
  }

  const scored = data.versions.filter((v) => v.roc_auc != null);
  const points: LinePoint[] = scored.map((v, i) => ({
    value: (v.roc_auc as number) * 100,
    label: v.trained_at ? new Date(v.trained_at).toLocaleDateString() : `v${i + 1}`,
  }));

  const delta = data.delta_vs_previous;
  const DeltaIcon = delta == null ? Minus : delta > 0 ? TrendingUp : TrendingDown;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <div>
          <span className="text-xl font-semibold tnum text-ink">
            {data.latest_roc_auc != null ? pct(data.latest_roc_auc, 1) : "—"}
          </span>
          <span className="ml-1.5 text-[11px] uppercase tracking-wide text-ink-faint">
            current accuracy
          </span>
        </div>
        {delta != null && (
          <span
            className={cn(
              "flex items-center gap-1 text-[12px]",
              delta > 0 ? "text-success" : delta < 0 ? "text-danger" : "text-ink-muted",
            )}
          >
            <DeltaIcon size={13} />
            {delta > 0 ? "+" : ""}
            {(delta * 100).toFixed(1)} pts vs previous
          </span>
        )}
        <span className="text-[12px] text-ink-faint">
          {data.total} version{data.total !== 1 ? "s" : ""} trained
        </span>
      </div>

      {points.length > 1 ? (
        <LineChart data={points} height={120} unit="%" formatValue={(n) => n.toFixed(1)} />
      ) : (
        <p className="text-[12px] text-ink-faint">
          One version so far — the trend appears after the next retrain.
        </p>
      )}

      <p className="text-[11px] leading-relaxed text-ink-faint">
        Held-out accuracy (ROC-AUC) on days the model never saw during training. A flat line
        across versions means more data has stopped helping.
      </p>
    </div>
  );
}

/* --------------------------------------------------------- advice that works */

function AdviceEffectiveness() {
  const { data, isLoading } = useQuery({
    queryKey: ["feedback", "effectiveness"],
    queryFn: () => api.effectiveness(),
  });

  if (isLoading) return <Skeleton className="h-24 rounded-xl" />;
  if (!data || data.families.length === 0) {
    return (
      <p className="text-[13px] text-ink-muted">
        Nothing scored yet. Atlas records each suggestion it shows and checks the next day
        whether you acted on it — after a few days, the ones that work for you start ranking
        higher.
      </p>
    );
  }

  return (
    <div className="space-y-2.5">
      {data.families.map((f) => (
        <div key={f.family}>
          <div className="flex items-center justify-between gap-2 text-sm">
            <span className="min-w-0 truncate text-ink">{f.label}</span>
            <span className="flex shrink-0 items-center gap-2">
              {f.influencing && (
                <span className="rounded-full bg-accent-soft px-1.5 py-0.5 text-[10px] font-semibold text-accent">
                  ranking
                </span>
              )}
              <span className="tnum text-ink-muted">{pct(f.rate)}</span>
            </span>
          </div>
          <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-ink/10">
            <div
              className={cn(
                "h-full rounded-full transition-[width] duration-700",
                f.rate >= 0.5 ? "bg-success" : "bg-warn",
              )}
              style={{ width: `${Math.max(3, f.rate * 100)}%` }}
            />
          </div>
          <div className="mt-0.5 text-[11px] text-ink-faint">
            followed {f.followed} of {f.shown}
            {!f.influencing && ` · needs ${data.min_samples} to count`}
          </div>
        </div>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------- jobs */

function Jobs() {
  const qc = useQueryClient();
  const [running, setRunning] = useState<string | null>(null);
  const { data, isLoading } = useQuery({ queryKey: ["jobs"], queryFn: () => api.jobs() });

  const run = useMutation({
    mutationFn: (id: string) => api.runJob(id),
    onMutate: (id) => setRunning(id),
    onSettled: () => {
      setRunning(null);
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["ml"] });
    },
  });

  if (isLoading) return <Skeleton className="h-32 rounded-xl" />;
  if (!data) return null;

  return (
    <div className="space-y-2.5">
      {!data.enabled && (
        <div className="flex items-start gap-2 rounded-xl bg-warn/10 px-3 py-2 text-[12px] text-warn">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" />
          <span>
            Background jobs are disabled, so Atlas won't retrain itself. You can still run them
            by hand below.
          </span>
        </div>
      )}

      {data.jobs.map((job) => {
        const last = job.last_run;
        return (
          <div key={job.id} className="glass-inset rounded-xl p-3">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="text-sm font-medium text-ink">{job.label}</div>
                <div className="mt-0.5 text-[12px] leading-relaxed text-ink-muted">
                  {job.description}
                </div>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => run.mutate(job.id)}
                disabled={running !== null}
              >
                {running === job.id ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : (
                  <Play size={14} />
                )}
                Run
              </Button>
            </div>

            <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-ink-faint">
              <span className="flex items-center gap-1">
                <Clock size={11} />
                every {Math.round(job.interval_hours / 24) || 1}d
              </span>
              {last ? (
                <span className={cn("flex items-center gap-1", STATUS_TONE[last.status])}>
                  <Check size={11} />
                  {last.status} · {relativeTime(last.started_at)}
                </span>
              ) : (
                <span>never run</span>
              )}
              {job.next_due && !job.due_now && <span>next {relativeTime(job.next_due)}</span>}
              {job.due_now && <span className="text-accent">due now</span>}
            </div>

            {last?.detail && (
              <p className="mt-1.5 text-[11px] leading-relaxed text-ink-muted">{last.detail}</p>
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------------------- card */

/**
 * "How Atlas is getting better" — made visible.
 *
 * Three loops in one place: the model's accuracy across retrains, whether its
 * advice is actually being acted on, and the jobs that keep both moving
 * without the user remembering to run anything.
 */
export function LearningCard() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Learning</CardTitle>
        <Brain size={15} className="text-accent" />
      </CardHeader>
      <CardBody className="space-y-5">
        <section>
          <div className="mb-2 flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-ink-muted">
            <Activity size={12} /> Model quality
          </div>
          <ModelQuality />
        </section>

        <section className="border-t border-border/10 pt-4">
          <div className="mb-2 text-[11px] font-medium uppercase tracking-wide text-ink-muted">
            Which advice works for you
          </div>
          <AdviceEffectiveness />
        </section>

        <section className="border-t border-border/10 pt-4">
          <div className="mb-2 text-[11px] font-medium uppercase tracking-wide text-ink-muted">
            Automatic upkeep
          </div>
          <Jobs />
        </section>
      </CardBody>
    </Card>
  );
}
