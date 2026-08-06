import {
  Brain,
  Check,
  Clock,
  Info,
  ListChecks,
  Sparkles,
  Sun,
  Sunrise,
  Sunset,
  type LucideIcon,
} from "lucide-react";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useCompleteTask, useLogHabit, usePlan, useUnlogHabit } from "@/hooks/queries";
import { cn, formatLongDate, todayISO } from "@/lib/utils";
import type { PlanBlock, PlanItem } from "@/lib/types";

const BLOCK_ICON: Record<string, LucideIcon> = {
  morning: Sunrise,
  afternoon: Sun,
  evening: Sunset,
};

function fmtMinutes(min: number): string {
  if (min <= 0) return "0m";
  const h = Math.floor(min / 60);
  const m = min % 60;
  return h ? `${h}h${m ? ` ${m}m` : ""}` : `${m}m`;
}

/* ------------------------------------------------------------- plan item row */

function ItemRow({ item }: { item: PlanItem }) {
  const log = useLogHabit();
  const unlog = useUnlogHabit();
  const complete = useCompleteTask();
  const busy = log.isPending || unlog.isPending || complete.isPending;

  const toggle = () => {
    if (item.done) {
      if (item.kind === "habit") unlog.mutate({ id: item.id, date: todayISO() });
      return; // tasks aren't un-completed from the plan
    }
    if (item.kind === "habit") log.mutate({ id: item.id, body: { status: "completed" } });
    else complete.mutate(item.id);
  };

  const prob = item.probability != null ? Math.round(item.probability * 100) : null;
  const showBar = item.kind === "habit" && prob != null && !item.done;

  return (
    <div className="py-2.5">
      <div className="flex items-center gap-3">
        <button
          onClick={toggle}
          disabled={busy}
          aria-label={item.done ? "Mark not done" : "Mark done"}
          className={cn(
            "grid h-6 w-6 shrink-0 place-items-center rounded-full border transition-all",
            item.done
              ? "border-accent bg-accent text-white"
              : "border-ink/25 text-transparent hover:border-accent hover:text-accent/40",
          )}
        >
          <Check size={14} />
        </button>

        {item.kind === "task" ? (
          <ListChecks size={13} className="shrink-0 text-ink-faint" />
        ) : (
          <span
            className="h-2 w-2 shrink-0 rounded-full"
            style={{ backgroundColor: item.color ?? "rgb(var(--accent))" }}
          />
        )}

        <span
          className={cn(
            "min-w-0 flex-1 truncate text-sm",
            item.done ? "text-ink-faint line-through" : "text-ink",
          )}
        >
          {item.title}
        </span>

        {item.risk === "at-risk" && !item.done && (
          <span
            className="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold"
            style={{
              color: "rgb(var(--warn))",
              backgroundColor: "rgb(var(--warn) / 0.12)",
            }}
          >
            front-load
          </span>
        )}

        {item.done ? (
          <span className="flex shrink-0 items-center gap-1 text-[11px] text-success">
            <Check size={12} /> done
          </span>
        ) : prob != null ? (
          <span className="shrink-0 text-[12px] font-semibold tabular-nums text-ink-muted">
            {prob}%
          </span>
        ) : item.duration_min ? (
          <span className="flex shrink-0 items-center gap-1 text-[11px] tabular-nums text-ink-faint">
            <Clock size={11} />
            {fmtMinutes(item.duration_min)}
          </span>
        ) : null}
      </div>

      {showBar && (
        <div className="ml-9 mt-1.5 h-1 overflow-hidden rounded-full bg-ink/10">
          <div
            className="h-full rounded-full bg-accent transition-[width] duration-700"
            style={{ width: `${prob}%` }}
          />
        </div>
      )}

      <div className="ml-9 mt-1 flex items-start gap-1 text-[11px] leading-relaxed text-ink-faint">
        <Info size={11} className="mt-0.5 shrink-0" />
        <span>{item.reason}</span>
      </div>
    </div>
  );
}

/* --------------------------------------------------------------- plan block */

function BlockCard({ block }: { block: PlanBlock }) {
  const Icon = BLOCK_ICON[block.key] ?? Clock;
  return (
    <Card className={cn(block.is_now && "ring-1 ring-accent/30")}>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Icon size={15} className="text-accent" />
          <CardTitle>{block.label}</CardTitle>
          <span className="text-[11px] text-ink-faint">{block.window}</span>
          {block.is_now && (
            <span className="rounded-full bg-accent-soft px-2 py-0.5 text-[10px] font-semibold text-accent">
              now
            </span>
          )}
        </div>
        {block.minutes > 0 && (
          <span className="text-[11px] tabular-nums text-ink-muted">
            ~{fmtMinutes(block.minutes)}
          </span>
        )}
      </CardHeader>
      <CardBody className="divide-y divide-border/10">
        {block.items.map((item) => (
          <ItemRow key={`${item.kind}-${item.id}`} item={item} />
        ))}
      </CardBody>
    </Card>
  );
}

/* -------------------------------------------------------------- page states */

function PlanSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-10 w-56" />
      <Skeleton className="h-24 rounded-2xl" />
      <div className="space-y-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-44 rounded-2xl" />
        ))}
      </div>
    </div>
  );
}

export function PlanPage() {
  const { data: plan, isLoading } = usePlan();

  if (isLoading || !plan) return <PlanSkeleton />;

  const reliability = plan.reliability != null ? Math.round(plan.reliability * 100) : null;

  return (
    <div className="animate-fade-in space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold tracking-tight text-ink">Today's plan</h2>
          <p className="text-sm text-ink-muted">{formatLongDate(plan.date)}</p>
        </div>
        <span
          className={cn(
            "flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium",
            plan.model_backed ? "bg-accent-soft text-accent" : "bg-ink/[0.06] text-ink-muted",
          )}
          title={
            plan.model_backed
              ? "Ordering shaped by your trained completion model"
              : "Rule-based ordering — train the model on the dashboard to personalize it"
          }
        >
          {plan.model_backed ? <Brain size={13} /> : <Sparkles size={13} />}
          {plan.model_backed
            ? `AI-planned${reliability != null ? ` · reliability ${reliability}%` : ""}`
            : "Rule-based plan"}
        </span>
      </div>

      <Card className="p-4">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-accent-soft text-accent">
            <Sparkles size={16} />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium leading-relaxed text-ink">{plan.summary}</p>
            <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-ink-muted">
              <span className="tabular-nums">{plan.open_count} to do</span>
              {plan.total_minutes > 0 && (
                <span className="tabular-nums">~{fmtMinutes(plan.total_minutes)} of focus</span>
              )}
            </div>
          </div>
        </div>
      </Card>

      {plan.blocks.length === 0 ? (
        <Card className="p-8 text-center">
          <p className="text-sm text-ink-muted">
            Nothing due today. Add a habit or task and your plan will build itself.
          </p>
        </Card>
      ) : (
        plan.blocks.map((block) => <BlockCard key={block.key} block={block} />)
      )}

      <p className="px-1 text-[11px] leading-relaxed text-ink-faint">
        {plan.model_backed
          ? "Ordered so the habits you're most likely to skip surface first — each with its reasoning. Learned & explainable."
          : "Ordered by streaks, time-of-day fit, and priority. Train the completion model to personalize this ordering."}
      </p>
    </div>
  );
}
