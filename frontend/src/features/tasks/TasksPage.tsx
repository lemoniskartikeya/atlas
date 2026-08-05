import { useState } from "react";
import { Check, Clock, Plus } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useCompleteTask, useTasks } from "@/hooks/queries";
import { cn, parseDate, relativeDay } from "@/lib/utils";
import type { Priority, Task, TaskStatus } from "@/lib/types";
import { TaskDialog } from "./TaskDialog";

type Scope = "all" | "today" | "upcoming" | "open";

const COLUMNS: { key: TaskStatus; label: string }[] = [
  { key: "todo", label: "To do" },
  { key: "in_progress", label: "In progress" },
  { key: "done", label: "Done" },
];

const SCOPES: [Scope, string][] = [
  ["all", "All"],
  ["today", "Today"],
  ["upcoming", "Upcoming"],
  ["open", "Open"],
];

const PRIORITY_COLOR: Record<Priority, string> = {
  critical: "#d0605e",
  high: "rgb(var(--warn))",
  medium: "rgb(var(--accent))",
  low: "rgb(var(--ink-faint))",
};

function isOverdue(due: string): boolean {
  const t = new Date();
  t.setHours(0, 0, 0, 0);
  return parseDate(due).getTime() < t.getTime();
}

function TaskCard({ task, onEdit }: { task: Task; onEdit: (t: Task) => void }) {
  const complete = useCompleteTask();
  const done = task.status === "done";
  return (
    <div
      onClick={() => onEdit(task)}
      className="glass-inset group cursor-pointer rounded-xl p-3 transition-colors hover:border-accent/30"
    >
      <div className="flex items-start gap-2.5">
        <button
          onClick={(e) => {
            e.stopPropagation();
            if (!done) complete.mutate(task.id);
          }}
          disabled={done || complete.isPending}
          aria-label="Complete task"
          className={cn(
            "mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full border transition-colors",
            done
              ? "border-accent bg-accent text-white"
              : "border-ink/25 text-transparent hover:border-accent",
          )}
        >
          <Check size={12} />
        </button>
        <div className="min-w-0 flex-1">
          <div className={cn("text-sm", done ? "text-ink-faint line-through" : "text-ink")}>
            {task.title}
          </div>
          <div className="mt-1.5 flex flex-wrap items-center gap-x-2.5 gap-y-1">
            <span className="flex items-center gap-1 text-[11px] capitalize text-ink-muted">
              <span
                className="h-1.5 w-1.5 rounded-full"
                style={{ backgroundColor: PRIORITY_COLOR[task.priority] }}
              />
              {task.priority}
            </span>
            {task.due_date && (
              <span
                className={cn(
                  "flex items-center gap-1 text-[11px]",
                  isOverdue(task.due_date) && !done ? "text-red-500" : "text-ink-faint",
                )}
              >
                <Clock size={11} />
                {relativeDay(task.due_date)}
              </span>
            )}
            {task.estimated_effort_min ? (
              <span className="text-[11px] text-ink-faint">{task.estimated_effort_min}m</span>
            ) : null}
            {(task.tags ?? []).slice(0, 3).map((t) => (
              <Badge key={t}>{t}</Badge>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export function TasksPage() {
  const [scope, setScope] = useState<Scope>("all");
  const { data: tasks, isLoading } = useTasks(scope);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Task | null>(null);

  const openNew = () => {
    setEditing(null);
    setDialogOpen(true);
  };
  const openEdit = (t: Task) => {
    setEditing(t);
    setDialogOpen(true);
  };

  const byStatus = (s: TaskStatus) =>
    (tasks ?? []).filter((t) =>
      s === "todo" ? t.status === "todo" || t.status === "backlog" : t.status === s,
    );

  return (
    <div className="animate-fade-in space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold tracking-tight text-ink">Tasks</h2>
          <p className="text-sm text-ink-muted">{tasks ? `${tasks.length} in view` : "Loading…"}</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="glass-inset flex rounded-xl p-0.5">
            {SCOPES.map(([k, l]) => (
              <button
                key={k}
                onClick={() => setScope(k)}
                className={cn(
                  "rounded-lg px-3 py-1.5 text-[13px] font-medium transition-colors",
                  scope === k ? "bg-accent-soft text-accent" : "text-ink-muted hover:text-ink",
                )}
              >
                {l}
              </button>
            ))}
          </div>
          <Button onClick={openNew}>
            <Plus size={16} /> New task
          </Button>
        </div>
      </div>

      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-3">
          {COLUMNS.map((c) => (
            <Skeleton key={c.key} className="h-64 rounded-2xl" />
          ))}
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-3">
          {COLUMNS.map((col) => {
            const items = byStatus(col.key);
            return (
              <Card key={col.key} className="flex flex-col p-3">
                <div className="mb-2 flex items-center justify-between px-1">
                  <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-muted">
                    {col.label}
                  </span>
                  <span className="text-[11px] tabular-nums text-ink-faint">{items.length}</span>
                </div>
                <div className="space-y-2">
                  {items.length === 0 ? (
                    <p className="px-1 py-6 text-center text-[13px] text-ink-faint">Nothing here</p>
                  ) : (
                    items.map((t) => <TaskCard key={t.id} task={t} onEdit={openEdit} />)
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      )}

      <TaskDialog open={dialogOpen} onClose={() => setDialogOpen(false)} task={editing} />
    </div>
  );
}
