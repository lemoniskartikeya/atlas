import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowRight,
  Brain,
  Clock,
  Flame,
  HeartPulse,
  Info,
  Lightbulb,
  ListChecks,
  Moon,
  Smile,
  Sparkles,
  Sun,
  Sunrise,
  Sunset,
  Target,
  Zap,
  type LucideIcon,
} from "lucide-react";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { Stat } from "@/components/ui/stat";
import { Skeleton } from "@/components/ui/skeleton";
import { CheckToggle } from "@/components/ui/check-toggle";
import { ContributionHeatmap, HeatmapLegend } from "@/components/charts/heatmap";
import { useCompleteTask, useHeatmap, useLogHabit, useUnlogHabit } from "@/hooks/queries";
import { cn, parseDate, pct, relativeDay, todayISO } from "@/lib/utils";
import type {
  Dashboard,
  HabitTodayItem,
  Priority,
  Recommendation,
  StreakItem,
  Task,
  TimeOfDay,
} from "@/lib/types";

/* --------------------------------------------------------------- helpers */

const TOD: Record<TimeOfDay, { icon: LucideIcon; label: string }> = {
  morning: { icon: Sunrise, label: "Morning" },
  afternoon: { icon: Sun, label: "Afternoon" },
  evening: { icon: Sunset, label: "Evening" },
  night: { icon: Moon, label: "Night" },
  any: { icon: Clock, label: "Any" },
};

const PRIORITY_COLOR: Record<Priority, string> = {
  critical: "rgb(var(--danger))",
  high: "rgb(var(--warn))",
  medium: "rgb(var(--accent))",
  low: "rgb(var(--ink-faint))",
};

const REC_ICON: Record<string, LucideIcon> = {
  habit: Flame,
  task: ListChecks,
  wellbeing: HeartPulse,
  focus: Target,
};

function TimeBadge({ t }: { t: TimeOfDay }) {
  const { icon: Icon, label } = TOD[t];
  return (
    <span className="hidden items-center gap-1 text-[11px] text-ink-faint sm:flex">
      <Icon size={12} />
      {label}
    </span>
  );
}

function isOverdue(due: string): boolean {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return parseDate(due).getTime() < today.getTime();
}

/* The dashboard headline now lives in LifeScoreCard.tsx, which pairs the score
   with the interactive trend chart. */

/* --------------------------------------------------------- today's habits */

function HabitToggleRow({ item }: { item: HabitTodayItem }) {
  const log = useLogHabit();
  const unlog = useUnlogHabit();
  const busy = log.isPending || unlog.isPending;

  // Reflect the click immediately so the tick animates on the user's action
  // rather than waiting on the round-trip; the refetch reconciles it.
  const [optimistic, setOptimistic] = useState<boolean | null>(null);
  const done = optimistic ?? item.done_today;

  const toggle = () => {
    if (item.done_today) {
      setOptimistic(false);
      unlog.mutate({ id: item.id, date: todayISO() }, { onSettled: () => setOptimistic(null) });
    } else {
      setOptimistic(true);
      log.mutate(
        { id: item.id, body: { status: "completed" } },
        { onSettled: () => setOptimistic(null) },
      );
    }
  };

  return (
    <div className="flex items-center gap-3 py-1.5">
      <CheckToggle checked={done} onChange={toggle} disabled={busy} size={24} />
      <span
        className={cn(
          "relative min-w-0 flex-1 truncate text-sm transition-colors",
          done ? "text-ink-faint" : "text-ink",
        )}
      >
        <span className={cn("relative", done && "strike-sweep")}>{item.title}</span>
      </span>
      {item.current_streak > 0 && (
        <span className="flex items-center gap-1 text-[12px] text-ink-muted tnum">
          <Flame size={12} className="text-accent" />
          {item.current_streak}
        </span>
      )}
      <TimeBadge t={item.time_preference} />
    </div>
  );
}

export function TodayHabitsCard({
  items,
  completed,
  total,
}: {
  items: HabitTodayItem[];
  completed: number;
  total: number;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Today's habits</CardTitle>
        <span className="text-[12px] tabular-nums text-ink-muted">
          {completed}/{total}
        </span>
      </CardHeader>
      <CardBody className="divide-y divide-border/10">
        {items.length === 0 ? (
          <p className="py-2 text-sm text-ink-muted">Nothing due today. Enjoy the breathing room.</p>
        ) : (
          items.map((item) => <HabitToggleRow key={item.id} item={item} />)
        )}
      </CardBody>
    </Card>
  );
}

/* ---------------------------------------------------------- today's tasks */

function TaskRow({ task }: { task: Task }) {
  const complete = useCompleteTask();
  const [optimistic, setOptimistic] = useState(false);
  const done = optimistic || task.status === "done";

  return (
    // Completing a task shouldn't feel like deletion: the tick draws, the title
    // strikes through, and only then does the row lift, blur, and collapse out
    // of the list. AnimatePresence in the parent keeps it mounted to do that.
    <motion.div
      layout
      initial={false}
      exit={{ opacity: 0, height: 0, marginTop: 0, x: 14, filter: "blur(3px)" }}
      transition={{ duration: 0.42, ease: [0.22, 1, 0.36, 1] }}
      className="flex items-center gap-3 overflow-hidden py-1.5"
    >
      <CheckToggle
        checked={done}
        disabled={done || complete.isPending}
        onChange={() => {
          if (done) return;
          setOptimistic(true);
          complete.mutate(task.id);
        }}
        label="Complete task"
      />
      <span
        className="h-1.5 w-1.5 shrink-0 rounded-full"
        style={{ backgroundColor: PRIORITY_COLOR[task.priority] }}
      />
      <span
        className={cn(
          "min-w-0 flex-1 truncate text-sm transition-colors",
          done ? "text-ink-faint" : "text-ink",
        )}
      >
        <span className={cn("relative", done && "strike-sweep")}>{task.title}</span>
      </span>
      {task.due_date && (
        <span
          className={cn(
            "shrink-0 text-[11px] tnum",
            isOverdue(task.due_date) ? "text-danger" : "text-ink-faint",
          )}
        >
          {relativeDay(task.due_date)}
        </span>
      )}
    </motion.div>
  );
}

export function TasksTodayCard({
  tasks,
  suggested,
  openCount,
}: {
  tasks: Task[];
  suggested: Task | null;
  openCount: number;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Today's tasks</CardTitle>
        <span className="text-[12px] tabular-nums text-ink-muted">{openCount} open</span>
      </CardHeader>
      <CardBody>
        {suggested && (
          <div className="mb-3 flex items-center gap-2.5 rounded-xl bg-accent-soft px-3 py-2">
            <Sparkles size={14} className="shrink-0 text-accent" />
            <span className="min-w-0 flex-1 truncate text-[13px] text-ink">
              <span className="text-ink-muted">Suggested next · </span>
              {suggested.title}
            </span>
            <ArrowRight size={14} className="shrink-0 text-accent" />
          </div>
        )}
        <div className="divide-y divide-border/10">
          <AnimatePresence initial={false} mode="popLayout">
            {tasks.length === 0 ? (
              <p key="empty" className="py-2 text-sm text-ink-muted">
                No tasks scheduled for today.
              </p>
            ) : (
              tasks.map((t) => <TaskRow key={t.id} task={t} />)
            )}
          </AnimatePresence>
        </div>
      </CardBody>
    </Card>
  );
}

/* -------------------------------------------------------- recommendations */

export function RecommendationsCard({
  recs,
  modelBacked = false,
}: {
  recs: Recommendation[];
  modelBacked?: boolean;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Insights for today</CardTitle>
        {modelBacked ? (
          <span
            title="The riskiest habits are ranked by your trained completion model"
            className="flex items-center gap-1 rounded-full bg-accent-soft px-2 py-0.5 text-[10px] font-semibold text-accent"
          >
            <Brain size={11} /> model
          </span>
        ) : (
          <Sparkles size={15} className="text-accent" />
        )}
      </CardHeader>
      <CardBody className="space-y-2.5">
        {recs.length === 0 && (
          <p className="text-sm text-ink-muted">No suggestions right now — you're on track.</p>
        )}
        {recs.map((r) => {
          const Icon = REC_ICON[r.kind] ?? Lightbulb;
          return (
            <div key={r.id} className="glass-inset rounded-xl p-3">
              <div className="flex items-start gap-2.5">
                <div className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-accent-soft text-accent">
                  <Icon size={14} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-sm font-medium text-ink">{r.title}</div>
                    <span className="shrink-0 rounded-full bg-ink/[0.06] px-1.5 py-0.5 text-[10px] tabular-nums text-ink-muted">
                      {Math.round(r.confidence * 100)}%
                    </span>
                  </div>
                  <div className="mt-0.5 text-[13px] text-ink-muted">{r.detail}</div>
                  <div className="mt-1.5 flex items-start gap-1 text-[11px] text-ink-faint">
                    <Info size={11} className="mt-0.5 shrink-0" />
                    <span>{r.reason}</span>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
        <p className="pt-1 text-[10px] leading-relaxed text-ink-faint">
          {modelBacked
            ? "Model-driven — the riskiest habits lead, each with the reasoning behind it."
            : "Rule-based insights, each with its reasoning — train the model to personalize them."}
        </p>
      </CardBody>
    </Card>
  );
}

/* -------------------------------------------------------------- wellbeing */

function WellbeingTile({
  icon: Icon,
  label,
  value,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
}) {
  return (
    <div className="glass-inset flex flex-col items-center rounded-xl py-3">
      <Icon size={16} className="text-accent" />
      <div className="mt-1.5 text-lg font-semibold tabular-nums text-ink">{value}</div>
      <div className="text-[10px] uppercase tracking-wide text-ink-faint">{label}</div>
    </div>
  );
}

export function WellbeingCard({
  mood,
  energy,
  sleep,
}: {
  mood?: number | null;
  energy?: number | null;
  sleep?: number | null;
}) {
  const has = mood != null || energy != null || sleep != null;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Wellbeing</CardTitle>
        <span className="text-[11px] text-ink-faint">latest journal</span>
      </CardHeader>
      <CardBody>
        {has ? (
          <div className="grid grid-cols-3 gap-2">
            <WellbeingTile icon={Smile} label="Mood" value={mood != null ? `${mood}/5` : "—"} />
            <WellbeingTile icon={Zap} label="Energy" value={energy != null ? `${energy}/5` : "—"} />
            <WellbeingTile icon={Moon} label="Sleep" value={sleep != null ? `${sleep}h` : "—"} />
          </div>
        ) : (
          <p className="text-sm text-ink-muted">No journal entry yet. Log today to track mood, energy, and sleep.</p>
        )}
      </CardBody>
    </Card>
  );
}

/* ---------------------------------------------------------------- streaks */

export function StreaksCard({ streaks }: { streaks: StreakItem[] }) {
  const max = Math.max(1, ...streaks.map((s) => s.current_streak));
  return (
    <Card>
      <CardHeader>
        <CardTitle>Active streaks</CardTitle>
        <Flame size={15} className="text-accent" />
      </CardHeader>
      <CardBody className="space-y-2.5">
        {streaks.length === 0 ? (
          <p className="text-sm text-ink-muted">No active streaks — complete a habit to begin one.</p>
        ) : (
          streaks.map((s) => (
            <div key={s.habit_id}>
              <div className="flex items-center justify-between text-sm">
                <span className="min-w-0 truncate text-ink">{s.title}</span>
                <span className="shrink-0 tabular-nums text-ink-muted">{s.current_streak}d</span>
              </div>
              <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-ink/10">
                <div
                  className="h-full rounded-full bg-accent transition-[width] duration-700"
                  style={{ width: `${(s.current_streak / max) * 100}%` }}
                />
              </div>
            </div>
          ))
        )}
      </CardBody>
    </Card>
  );
}

/* ---------------------------------------------------------------- heatmap */

export function HeatmapCard() {
  const { data } = useHeatmap(365);
  return (
    <Card>
      <CardHeader>
        <CardTitle>Consistency</CardTitle>
        {data && (
          <span className="text-[11px] text-ink-muted">
            {data.total} completions · last year
          </span>
        )}
      </CardHeader>
      <CardBody>
        {data ? (
          <>
            <ContributionHeatmap data={data} />
            <div className="mt-3 flex justify-end">
              <HeatmapLegend />
            </div>
          </>
        ) : (
          <Skeleton className="h-24 w-full" />
        )}
      </CardBody>
    </Card>
  );
}
