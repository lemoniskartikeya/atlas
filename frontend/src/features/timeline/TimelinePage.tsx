import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  BookOpen,
  Check,
  CheckCheck,
  Flame,
  Plus,
  SkipForward,
  Zap,
  type LucideIcon,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useTimeline } from "@/hooks/queries";
import { cn, formatLongDate, parseDate } from "@/lib/utils";
import type { TimelineEvent } from "@/lib/types";

const FILTERS: { label: string; kinds?: string }[] = [
  { label: "All" },
  { label: "Habits", kinds: "habit,habit_created" },
  { label: "Streaks", kinds: "streak" },
  { label: "Tasks", kinds: "task" },
  { label: "Journal", kinds: "journal" },
  { label: "Focus", kinds: "focus" },
];

const KIND: Record<string, { icon: LucideIcon; color: string }> = {
  habit: { icon: Check, color: "rgb(var(--accent))" },
  streak: { icon: Flame, color: "rgb(var(--warn))" },
  task: { icon: CheckCheck, color: "rgb(var(--success))" },
  journal: { icon: BookOpen, color: "rgb(var(--accent))" },
  habit_created: { icon: Plus, color: "rgb(var(--ink-faint))" },
  focus: { icon: Zap, color: "rgb(var(--accent))" },
};

function dayLabel(iso: string): string {
  const d = parseDate(iso);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diff = Math.round((d.getTime() - today.getTime()) / 86_400_000);
  if (diff === 0) return "Today";
  if (diff === -1) return "Yesterday";
  const base = formatLongDate(iso);
  return d.getFullYear() === today.getFullYear() ? base : `${base}, ${d.getFullYear()}`;
}

function fmtTime(iso: string): string {
  const dt = new Date(/[zZ]$/.test(iso) ? iso : `${iso}Z`);
  return dt.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function EventRow({ event, last }: { event: TimelineEvent; last: boolean }) {
  const navigate = useNavigate();
  const meta = KIND[event.kind] ?? KIND.habit;
  const skipped = event.status === "skipped";
  const dot = event.color ?? meta.color;
  const Icon = skipped ? SkipForward : meta.icon;
  const showTime = event.kind === "habit" || event.kind === "task";

  return (
    <div className="flex gap-3">
      <div className="flex flex-col items-center">
        <span
          className="grid h-6 w-6 shrink-0 place-items-center rounded-full text-white"
          style={{ backgroundColor: skipped ? "rgb(var(--ink-faint))" : dot }}
        >
          <Icon size={12} />
        </span>
        {!last && <span className="mt-1 w-px flex-1 bg-border/20" />}
      </div>
      <button
        onClick={() => event.route && navigate(event.route)}
        className={cn(
          "mb-3 min-w-0 flex-1 rounded-lg px-2 py-1 text-left transition-colors",
          event.route && "hover:bg-ink/5",
        )}
      >
        <div className="flex items-baseline gap-2">
          <span
            className={cn(
              "min-w-0 flex-1 truncate text-[13px]",
              skipped ? "text-ink-muted line-through" : "text-ink",
            )}
          >
            {event.title}
          </span>
          {showTime && (
            <span className="shrink-0 text-[11px] tabular-nums text-ink-faint">
              {fmtTime(event.timestamp)}
            </span>
          )}
        </div>
        {event.detail && (
          <p className="mt-0.5 truncate text-[11px] text-ink-muted">{event.detail}</p>
        )}
      </button>
    </div>
  );
}

export function TimelinePage() {
  const [filter, setFilter] = useState(0);
  const { data, isLoading, hasNextPage, isFetchingNextPage, fetchNextPage } = useTimeline(
    FILTERS[filter].kinds,
  );

  const groups = useMemo(() => {
    const events = data?.pages.flatMap((p) => p.events) ?? [];
    const map = new Map<string, TimelineEvent[]>();
    for (const e of events) {
      const arr = map.get(e.date) ?? [];
      arr.push(e);
      map.set(e.date, arr);
    }
    return [...map.entries()]; // insertion order preserves reverse-chron
  }, [data]);

  return (
    <div className="animate-fade-in space-y-4">
      <div>
        <h2 className="text-xl font-display font-semibold text-ink">Timeline</h2>
        <p className="text-sm text-ink-muted">Everything you've done, in order.</p>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {FILTERS.map((f, i) => (
          <button
            key={f.label}
            onClick={() => setFilter(i)}
            className={cn(
              "rounded-full px-3 py-1 text-[12px] font-medium transition-colors",
              i === filter
                ? "bg-accent text-white"
                : "bg-ink/[0.06] text-ink-muted hover:text-ink",
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <Card className="space-y-3 p-5">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-8" />
          ))}
        </Card>
      ) : groups.length === 0 ? (
        <Card className="p-10 text-center">
          <p className="text-sm text-ink-muted">Nothing here yet. Log a habit to start your story.</p>
        </Card>
      ) : (
        <div className="space-y-5">
          {groups.map(([day, events]) => (
            <Card key={day} className="p-4">
              <div className="mb-3 text-[12px] font-semibold uppercase tracking-wide text-ink-muted">
                {dayLabel(day)}
              </div>
              <div>
                {events.map((e, i) => (
                  <EventRow key={e.id} event={e} last={i === events.length - 1} />
                ))}
              </div>
            </Card>
          ))}

          {hasNextPage && (
            <div className="flex justify-center pt-1">
              <Button
                variant="outline"
                onClick={() => fetchNextPage()}
                disabled={isFetchingNextPage}
              >
                {isFetchingNextPage ? "Loading…" : "Load more"}
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
