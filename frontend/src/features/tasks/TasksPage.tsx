import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Clock, Plus } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { CheckToggle } from "@/components/ui/check-toggle";
import { useCompleteTask, useTasks } from "@/hooks/queries";
import { cn, parseDate, relativeDay } from "@/lib/utils";
import type { Priority, Task, TaskStatus } from "@/lib/types";
import { TaskDialog } from "./TaskDialog";
import { CompletedTasksView } from "./CompletedTasksView";

type Scope = "all" | "today" | "upcoming" | "open" | "completed";

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
  ["completed", "Completed"],
];

const PRIORITY_COLOR: Record<Priority, string> = {
  critical: "rgb(var(--danger))",
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
    // `layoutId` is what makes a completed card *travel* to the Done column
    // instead of blinking out of one list and into another.
    <motion.div
      layoutId={`task-${task.id}`}
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.96, filter: "blur(4px)" }}
      transition={{ type: "spring", stiffness: 420, damping: 34 }}
      onClick={() => onEdit(task)}
      className={cn(
        "glass-inset lift group cursor-pointer rounded-xl p-3 hover:border-accent/30",
        done && "opacity-70",
      )}
    >
      <div className="flex items-start gap-2.5">
        <div className="mt-0.5" onClick={(e) => e.stopPropagation()}>
          <CheckToggle
            checked={done}
            disabled={done || complete.isPending}
            onChange={() => !done && complete.mutate(task.id)}
            label="Complete task"
          />
        </div>
        <div className="min-w-0 flex-1">
          <div
            className={cn(
              "relative inline-block text-sm",
              done ? "strike-sweep text-ink-faint" : "text-ink",
            )}
          >
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
                  isOverdue(task.due_date) && !done ? "text-danger" : "text-ink-faint",
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
    </motion.div>
  );
}

function Board({ tasks, onEdit }: { tasks: Task[]; onEdit: (t: Task) => void }) {
  const byStatus = (s: TaskStatus) =>
    tasks.filter((t) =>
      s === "todo" ? t.status === "todo" || t.status === "backlog" : t.status === s,
    );

  return (
    <div className="grid gap-4 md:grid-cols-3">
      {COLUMNS.map((col) => {
        const items = byStatus(col.key);
        return (
          <Card key={col.key} className="flex flex-col p-3">
            <div className="mb-2 flex items-center justify-between px-1">
              <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-muted">
                {col.label}
              </span>
              <span className="text-[11px] tnum text-ink-faint">{items.length}</span>
            </div>
            <div className="space-y-2">
              <AnimatePresence initial={false} mode="popLayout">
                {items.length === 0 ? (
                  <p key="empty" className="px-1 py-6 text-center text-[13px] text-ink-faint">
                    Nothing here
                  </p>
                ) : (
                  items.map((t) => <TaskCard key={t.id} task={t} onEdit={onEdit} />)
                )}
              </AnimatePresence>
            </div>
          </Card>
        );
      })}
    </div>
  );
}

export function TasksPage() {
  const [scope, setScope] = useState<Scope>("all");
  const boardScope = scope === "completed" ? "all" : scope;
  const { data: tasks, isLoading } = useTasks(boardScope);
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

  return (
    <div className="animate-fade-in space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-display font-semibold text-ink">Tasks</h2>
          <p className="text-sm text-ink-muted">
            {scope === "completed"
              ? "Everything you've finished."
              : tasks
                ? `${tasks.length} in view`
                : "Loading…"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="glass-inset flex rounded-xl p-0.5">
            {SCOPES.map(([k, l]) => (
              <button
                key={k}
                onClick={() => setScope(k)}
                className={cn(
                  "pressable rounded-lg px-3 py-1.5 text-[13px] font-medium",
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

      {scope === "completed" ? (
        <CompletedTasksView />
      ) : isLoading ? (
        <div className="grid gap-4 md:grid-cols-3">
          {COLUMNS.map((c) => (
            <Skeleton key={c.key} className="h-64 rounded-2xl" />
          ))}
        </div>
      ) : (
        <Board tasks={tasks ?? []} onEdit={openEdit} />
      )}

      <TaskDialog open={dialogOpen} onClose={() => setDialogOpen(false)} task={editing} />
    </div>
  );
}
