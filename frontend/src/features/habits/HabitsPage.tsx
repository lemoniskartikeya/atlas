import { useEffect, useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Check, Clock, Flame, Plus, Repeat2, Trash2 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useDeleteHabit, useHabits, useLogHabit, useUnlogHabit } from "@/hooks/queries";
import { cn, pct, todayISO } from "@/lib/utils";
import type { Habit } from "@/lib/types";
import { CreateHabitDialog } from "./CreateHabitDialog";

const WD = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function MiniStat({ label, value, icon }: { label: string; value: string; icon?: ReactNode }) {
  return (
    <div className="glass-inset rounded-xl px-2.5 py-2 text-center">
      <div className="flex items-center justify-center gap-1 text-sm font-semibold tabular-nums text-ink">
        {icon}
        {value}
      </div>
      <div className="mt-0.5 text-[10px] uppercase tracking-wide text-ink-faint">{label}</div>
    </div>
  );
}

function HabitCard({ habit }: { habit: Habit }) {
  const { data: stats } = useQuery({
    queryKey: ["habit", habit.id, "stats"],
    queryFn: () => api.habitStats(habit.id),
  });
  const log = useLogHabit();
  const unlog = useUnlogHabit();
  const del = useDeleteHabit();

  const today = todayISO();
  const done = stats?.last_completed === today;
  const busy = log.isPending || unlog.isPending;

  const toggle = () => {
    if (done) unlog.mutate({ id: habit.id, date: today });
    else log.mutate({ id: habit.id, body: { status: "completed" } });
  };

  const schedule =
    habit.frequency === "custom"
      ? (habit.custom_days ?? []).map((d) => WD[d]).join(" ") || "Custom"
      : habit.frequency[0].toUpperCase() + habit.frequency.slice(1);

  return (
    <Card className="group flex flex-col p-4">
      <div className="flex items-start gap-3">
        <span
          className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full"
          style={{ backgroundColor: habit.color ?? "rgb(var(--accent))" }}
        />
        <div className="min-w-0 flex-1">
          <div className="truncate font-medium text-ink">{habit.title}</div>
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
            {habit.category && <Badge>{habit.category}</Badge>}
            <Badge>{schedule}</Badge>
            {habit.estimated_duration_min ? (
              <Badge>
                <Clock size={11} />
                {habit.estimated_duration_min}m
              </Badge>
            ) : null}
          </div>
        </div>
        <button
          onClick={() => {
            if (window.confirm(`Delete “${habit.title}”? This removes its history.`))
              del.mutate(habit.id);
          }}
          className="text-ink-faint opacity-0 transition-opacity hover:text-danger group-hover:opacity-100"
          aria-label="Delete habit"
        >
          <Trash2 size={15} />
        </button>
      </div>

      <div className="mt-4 grid grid-cols-3 gap-2">
        <MiniStat label="Streak" value={stats ? String(stats.current_streak) : "—"} icon={<Flame size={13} />} />
        <MiniStat label="Best" value={stats ? String(stats.longest_streak) : "—"} />
        <MiniStat label="30-day" value={stats ? pct(stats.consistency_30d) : "—"} />
      </div>

      <Button
        onClick={toggle}
        disabled={busy}
        variant={done ? "subtle" : "outline"}
        className="mt-4 w-full"
      >
        <Check size={15} />
        {done ? "Done today" : "Mark done"}
      </Button>
    </Card>
  );
}

function EmptyState({ onNew }: { onNew: () => void }) {
  return (
    <Card className="grid place-items-center p-12 text-center">
      <div className="grid h-14 w-14 place-items-center rounded-2xl bg-accent-soft text-accent">
        <Repeat2 size={26} />
      </div>
      <h3 className="mt-4 text-lg font-semibold text-ink">No habits yet</h3>
      <p className="mt-1 max-w-xs text-sm text-ink-muted">
        Start with one small, repeatable habit. Atlas will learn your patterns from here.
      </p>
      <Button className="mt-5" onClick={onNew}>
        <Plus size={16} /> Create your first habit
      </Button>
    </Card>
  );
}

export function HabitsPage() {
  const [params, setParams] = useSearchParams();
  const { data: habits, isLoading } = useHabits();
  const [open, setOpen] = useState(false);

  // The command palette can deep-link "New habit" via ?new=1.
  useEffect(() => {
    if (params.get("new") === "1") {
      setOpen(true);
      params.delete("new");
      setParams(params, { replace: true });
    }
  }, [params, setParams]);

  return (
    <div className="animate-fade-in space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-display font-semibold text-ink">Your habits</h2>
          <p className="text-sm text-ink-muted">{habits ? `${habits.length} active` : "Loading…"}</p>
        </div>
        <Button onClick={() => setOpen(true)}>
          <Plus size={16} /> New habit
        </Button>
      </div>

      {isLoading ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-44 rounded-2xl" />
          ))}
        </div>
      ) : habits && habits.length > 0 ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {habits.map((h) => (
            <HabitCard key={h.id} habit={h} />
          ))}
        </div>
      ) : (
        <EmptyState onNew={() => setOpen(true)} />
      )}

      <CreateHabitDialog open={open} onClose={() => setOpen(false)} />
    </div>
  );
}
