import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  BookOpen,
  Check,
  ChevronLeft,
  ChevronRight,
  CircleDashed,
  Flame,
  ListChecks,
  Minus,
  Moon,
  Target,
  Timer,
  Zap,
} from "lucide-react";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useCalendar } from "@/hooks/queries";
import { cn, parseDate, todayISO, weekdayShortDate } from "@/lib/utils";
import type { CalendarDay } from "@/lib/types";

const WD = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

const HABIT_TONE: Record<string, string> = {
  completed: "text-success",
  partial: "text-warn",
  skipped: "text-ink-faint",
  due: "text-ink-faint",
};

/** Completion density for a day cell — the same language as the heatmap. */
function intensityStyle(day: CalendarDay): string {
  if (day.habits_due === 0) return "transparent";
  const steps = [0.1, 0.28, 0.46, 0.66, 0.9];
  const i = day.intensity >= 1 ? 4 : Math.min(4, Math.floor(day.intensity * 5));
  return `rgb(var(--success) / ${steps[i]})`;
}

function DayCell({
  day,
  selected,
  onSelect,
}: {
  day: CalendarDay;
  selected: boolean;
  onSelect: () => void;
}) {
  const d = parseDate(day.date);
  const hasActivity =
    day.habits_done > 0 || day.tasks_completed > 0 || day.has_journal || day.focus_minutes > 0;

  return (
    <button
      onClick={onSelect}
      aria-label={weekdayShortDate(d)}
      aria-pressed={selected}
      className={cn(
        "pressable group relative flex aspect-square flex-col items-start gap-1 rounded-xl border p-1.5 text-left sm:p-2",
        day.in_month ? "border-border/10" : "border-transparent opacity-35",
        selected ? "border-accent/60 bg-accent/[0.06]" : "hover:border-accent/30",
        day.is_future && "border-dashed",
      )}
    >
      <div className="flex w-full items-center justify-between">
        <span
          className={cn(
            "grid h-5 min-w-5 place-items-center rounded-full px-1 text-[11px] tnum",
            day.is_today
              ? "bg-accent font-semibold text-white"
              : day.in_month
                ? "text-ink"
                : "text-ink-faint",
          )}
        >
          {d.getDate()}
        </span>
        {day.has_journal && <BookOpen size={10} className="shrink-0 text-accent/70" />}
      </div>

      {/* Density block: how much of what was due actually got done. */}
      {day.habits_due > 0 && (
        <div
          className="h-1.5 w-full rounded-full"
          style={{ backgroundColor: intensityStyle(day) }}
          title={`${day.habits_done}/${day.habits_due} habits`}
        />
      )}

      <div className="mt-auto flex w-full flex-wrap items-center gap-x-1.5 gap-y-0.5 text-[10px] text-ink-faint">
        {day.habits_due > 0 && (
          <span className="tnum">
            {day.habits_done}/{day.habits_due}
          </span>
        )}
        {day.tasks_completed > 0 && (
          <span className="flex items-center gap-0.5 text-success">
            <Check size={9} />
            {day.tasks_completed}
          </span>
        )}
        {day.tasks_due > 0 && !day.tasks_completed && (
          <span className="flex items-center gap-0.5">
            <ListChecks size={9} />
            {day.tasks_due}
          </span>
        )}
        {day.focus_minutes > 0 && (
          <span className="flex items-center gap-0.5 text-accent">
            <Timer size={9} />
            {day.focus_minutes}m
          </span>
        )}
      </div>

      {!hasActivity && day.in_month && !day.is_future && day.habits_due === 0 && (
        <span className="sr-only">No activity</span>
      )}
    </button>
  );
}

function Metric({
  icon: Icon,
  value,
  label,
}: {
  icon: typeof Flame;
  value: string | number;
  label: string;
}) {
  return (
    <div className="glass-inset flex items-center gap-2.5 rounded-xl px-3 py-2.5">
      <Icon size={15} className="shrink-0 text-accent" />
      <div className="min-w-0">
        <div className="text-[15px] font-semibold leading-none tnum text-ink">{value}</div>
        <div className="mt-0.5 truncate text-[10px] uppercase tracking-wide text-ink-faint">
          {label}
        </div>
      </div>
    </div>
  );
}

function DayDetail({ day }: { day: CalendarDay }) {
  const d = parseDate(day.date);
  const wellbeing = [
    day.mood != null && { icon: Flame, label: "Mood", value: `${day.mood}/5` },
    day.energy != null && { icon: Zap, label: "Energy", value: `${day.energy}/5` },
    day.sleep_hours != null && { icon: Moon, label: "Sleep", value: `${day.sleep_hours}h` },
  ].filter(Boolean) as { icon: typeof Flame; label: string; value: string }[];

  return (
    <Card>
      <CardHeader>
        <CardTitle>{weekdayShortDate(d)}</CardTitle>
        {day.is_today ? (
          <span className="rounded-full bg-accent-soft px-2 py-0.5 text-[10px] font-semibold text-accent">
            Today
          </span>
        ) : day.is_future ? (
          <span className="text-[11px] text-ink-faint">Scheduled</span>
        ) : null}
      </CardHeader>
      <CardBody className="space-y-4">
        {day.habits.length === 0 && day.tasks.length === 0 && !day.has_journal && (
          <p className="py-4 text-center text-[13px] text-ink-muted">
            {day.is_future ? "Nothing scheduled yet." : "Nothing recorded for this day."}
          </p>
        )}

        {day.habits.length > 0 && (
          <div>
            <div className="mb-1.5 flex items-center justify-between">
              <span className="text-[11px] font-medium uppercase tracking-wide text-ink-muted">
                Habits
              </span>
              <span className="text-[11px] tnum text-ink-faint">
                {day.habits_done}/{day.habits_due}
              </span>
            </div>
            <div className="space-y-1">
              {day.habits.map((h) => (
                <div key={h.id} className="flex items-center gap-2 py-0.5">
                  <span className={HABIT_TONE[h.status]}>
                    {h.status === "completed" ? (
                      <Check size={13} />
                    ) : h.status === "partial" ? (
                      <Target size={13} />
                    ) : h.status === "skipped" ? (
                      <Minus size={13} />
                    ) : (
                      <CircleDashed size={13} />
                    )}
                  </span>
                  <span
                    className={cn(
                      "min-w-0 flex-1 truncate text-[13px]",
                      h.status === "completed" ? "text-ink" : "text-ink-muted",
                    )}
                  >
                    {h.title}
                  </span>
                  <span className="shrink-0 text-[10px] capitalize text-ink-faint">
                    {h.status}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {day.tasks.length > 0 && (
          <div>
            <div className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-ink-muted">
              Tasks
            </div>
            <div className="space-y-1">
              {day.tasks.map((t) => (
                <div key={t.id} className="flex items-center gap-2 py-0.5">
                  <span className={t.status === "done" ? "text-success" : "text-ink-faint"}>
                    {t.status === "done" ? <Check size={13} /> : <ListChecks size={13} />}
                  </span>
                  <span
                    className={cn(
                      "min-w-0 flex-1 truncate text-[13px]",
                      t.status === "done" ? "text-ink-muted line-through" : "text-ink",
                    )}
                  >
                    {t.title}
                  </span>
                  <span className="shrink-0 text-[10px] text-ink-faint">
                    {t.completed_here ? "finished" : "due"}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {(wellbeing.length > 0 || day.focus_minutes > 0) && (
          <div className="grid grid-cols-2 gap-2">
            {wellbeing.map((w) => (
              <Metric key={w.label} icon={w.icon} value={w.value} label={w.label} />
            ))}
            {day.focus_minutes > 0 && (
              <Metric
                icon={Timer}
                value={`${day.focus_minutes}m`}
                label={`Focus · ${day.focus_sessions}`}
              />
            )}
          </div>
        )}
      </CardBody>
    </Card>
  );
}

export function CalendarPage() {
  const today = todayISO();
  const now = parseDate(today);
  const [cursor, setCursor] = useState({ year: now.getFullYear(), month: now.getMonth() + 1 });
  const [selected, setSelected] = useState<string>(today);

  const { data, isLoading } = useCalendar(cursor.year, cursor.month);

  const step = (delta: number) => {
    const m = cursor.month + delta;
    const year = cursor.year + Math.floor((m - 1) / 12);
    const month = ((((m - 1) % 12) + 12) % 12) + 1;
    setCursor({ year, month });
  };

  const goToday = () => {
    setCursor({ year: now.getFullYear(), month: now.getMonth() + 1 });
    setSelected(today);
  };

  const selectedDay = useMemo(
    () => data?.days.find((d) => d.date === selected) ?? null,
    [data, selected],
  );

  const isCurrentMonth =
    cursor.year === now.getFullYear() && cursor.month === now.getMonth() + 1;

  return (
    <div className="animate-fade-in space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-display font-semibold text-ink">
            {data?.label ?? "Calendar"}
          </h2>
          <p className="text-sm text-ink-muted">Everything you did, day by day.</p>
        </div>
        <div className="flex items-center gap-2">
          {!isCurrentMonth && (
            <Button variant="ghost" size="sm" onClick={goToday}>
              Today
            </Button>
          )}
          <div className="glass-inset flex rounded-xl p-0.5">
            <button
              onClick={() => step(-1)}
              aria-label="Previous month"
              className="pressable grid h-8 w-8 place-items-center rounded-lg text-ink-muted hover:text-ink"
            >
              <ChevronLeft size={16} />
            </button>
            <button
              onClick={() => step(1)}
              aria-label="Next month"
              className="pressable grid h-8 w-8 place-items-center rounded-lg text-ink-muted hover:text-ink"
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      </div>

      {data && (
        <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-5">
          <Metric icon={Check} value={data.total_habits_done} label="Habits done" />
          <Metric icon={ListChecks} value={data.total_tasks_completed} label="Tasks done" />
          <Metric
            icon={Timer}
            value={`${Math.round(data.total_focus_minutes / 60)}h`}
            label="Focused"
          />
          <Metric icon={BookOpen} value={data.journal_days} label="Journalled" />
          <Metric icon={Target} value={data.perfect_days} label="Perfect days" />
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-12">
        <div className="lg:col-span-8">
          <Card className="p-3 sm:p-4">
            <div className="mb-2 grid grid-cols-7 gap-1.5">
              {WD.map((d) => (
                <div
                  key={d}
                  className="text-center text-[10px] font-medium uppercase tracking-wide text-ink-faint"
                >
                  {d}
                </div>
              ))}
            </div>
            {isLoading || !data ? (
              <div className="grid grid-cols-7 gap-1.5">
                {Array.from({ length: 35 }).map((_, i) => (
                  <Skeleton key={i} className="aspect-square rounded-xl" />
                ))}
              </div>
            ) : (
              <AnimatePresence mode="wait">
                <motion.div
                  key={`${data.year}-${data.month}`}
                  initial={{ opacity: 0, x: 8 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -8 }}
                  transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
                  className="grid grid-cols-7 gap-1.5"
                >
                  {data.days.map((day) => (
                    <DayCell
                      key={day.date}
                      day={day}
                      selected={day.date === selected}
                      onSelect={() => setSelected(day.date)}
                    />
                  ))}
                </motion.div>
              </AnimatePresence>
            )}
          </Card>
        </div>

        <div className="lg:col-span-4">
          {selectedDay ? (
            <DayDetail day={selectedDay} />
          ) : (
            <Card>
              <CardBody className="py-10 text-center text-[13px] text-ink-muted">
                Pick a day to see what happened.
              </CardBody>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
