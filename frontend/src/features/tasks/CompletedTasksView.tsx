import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { CalendarCheck, CheckCircle2, Trophy } from "lucide-react";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useCompletedTasks } from "@/hooks/queries";
import { cn, parseDate, weekdayShortDate } from "@/lib/utils";
import type { Task } from "@/lib/types";

const WINDOWS: [number, string][] = [
  [7, "7 days"],
  [30, "30 days"],
  [90, "90 days"],
  [365, "1 year"],
];

function StatTile({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Trophy;
  label: string;
  value: number;
}) {
  return (
    <div className="glass-inset flex items-center gap-3 rounded-xl px-3.5 py-3">
      <div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-success-soft text-success">
        <Icon size={17} />
      </div>
      <div className="min-w-0">
        <div className="text-xl font-semibold tnum leading-none text-ink">{value}</div>
        <div className="mt-1 text-[11px] uppercase tracking-wide text-ink-faint">{label}</div>
      </div>
    </div>
  );
}

/** Throughput bars — one column per day in the window. */
function ThroughputBars({ perDay }: { perDay: { date: string; count: number }[] }) {
  const max = Math.max(1, ...perDay.map((d) => d.count));
  return (
    <div className="flex h-14 items-end gap-[2px]">
      {perDay.map((d) => (
        <div
          key={d.date}
          title={`${weekdayShortDate(parseDate(d.date))} · ${d.count} completed`}
          className="group relative flex-1"
          style={{ height: "100%" }}
        >
          <div
            className={cn(
              "absolute bottom-0 w-full rounded-sm transition-colors",
              d.count > 0 ? "bg-success/70 group-hover:bg-success" : "bg-ink/[0.07]",
            )}
            style={{ height: d.count > 0 ? `${Math.max(12, (d.count / max) * 100)}%` : "3px" }}
          />
        </div>
      ))}
    </div>
  );
}

/** Local calendar day of a completion timestamp. */
function completedDay(t: Task): string {
  if (!t.completed_at) return "";
  const d = new Date(t.completed_at);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
    d.getDate(),
  ).padStart(2, "0")}`;
}

function completedTime(t: Task): string {
  if (!t.completed_at) return "";
  return new Date(t.completed_at).toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  });
}

/**
 * Completion archive. Nothing finished is thrown away — this is the record of
 * it, grouped by the day the work actually landed.
 */
export function CompletedTasksView() {
  const [days, setDays] = useState(30);
  const { data, isLoading } = useCompletedTasks(days);

  const groups = useMemo(() => {
    if (!data) return [];
    const map = new Map<string, Task[]>();
    for (const t of data.tasks) {
      const day = completedDay(t);
      if (!day) continue;
      const list = map.get(day);
      if (list) list.push(t);
      else map.set(day, [t]);
    }
    return [...map.entries()].sort((a, b) => (a[0] < b[0] ? 1 : -1));
  }, [data]);

  if (isLoading || !data) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-28 rounded-2xl" />
        <Skeleton className="h-64 rounded-2xl" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Completed work</CardTitle>
          <div className="glass-inset flex rounded-lg p-0.5">
            {WINDOWS.map(([d, label]) => (
              <button
                key={d}
                onClick={() => setDays(d)}
                className={cn(
                  "pressable rounded-md px-2.5 py-1 text-[12px] font-medium",
                  days === d ? "bg-accent-soft text-accent" : "text-ink-muted hover:text-ink",
                )}
              >
                {label}
              </button>
            ))}
          </div>
        </CardHeader>
        <CardBody className="space-y-4">
          <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
            <StatTile icon={CheckCircle2} label="Today" value={data.stats.today} />
            <StatTile icon={CalendarCheck} label="This week" value={data.stats.this_week} />
            <StatTile icon={Trophy} label={`Last ${days}d`} value={data.stats.window} />
            <StatTile icon={Trophy} label="All time" value={data.stats.all_time} />
          </div>
          <div>
            <div className="mb-1.5 text-[11px] uppercase tracking-wide text-ink-muted">
              Throughput
            </div>
            <ThroughputBars perDay={data.stats.per_day} />
          </div>
        </CardBody>
      </Card>

      {groups.length === 0 ? (
        <Card className="grid place-items-center p-12 text-center">
          <div className="grid h-14 w-14 place-items-center rounded-2xl bg-success-soft text-success">
            <CheckCircle2 size={26} />
          </div>
          <h3 className="mt-4 font-display text-lg font-semibold text-ink">Nothing finished yet</h3>
          <p className="mt-1 max-w-xs text-sm text-ink-muted">
            Completed tasks are kept here permanently, grouped by the day you finished them.
          </p>
        </Card>
      ) : (
        <div className="space-y-3">
          <AnimatePresence initial={false}>
            {groups.map(([day, items]) => (
              <motion.div
                key={day}
                layout
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
              >
                <Card>
                  <CardHeader>
                    <CardTitle>{weekdayShortDate(parseDate(day))}</CardTitle>
                    <span className="text-[11px] tnum text-ink-faint">{items.length} done</span>
                  </CardHeader>
                  <CardBody className="divide-y divide-border/10 pt-0">
                    {items.map((t) => (
                      <div key={t.id} className="flex items-center gap-3 py-2">
                        <CheckCircle2 size={15} className="shrink-0 text-success" />
                        <span className="min-w-0 flex-1 truncate text-sm text-ink">{t.title}</span>
                        {(t.tags ?? []).slice(0, 2).map((tag) => (
                          <Badge key={tag}>{tag}</Badge>
                        ))}
                        <span className="shrink-0 text-[11px] tnum text-ink-faint">
                          {completedTime(t)}
                        </span>
                      </div>
                    ))}
                  </CardBody>
                </Card>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}
