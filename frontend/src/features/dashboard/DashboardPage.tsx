import { type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useDashboard } from "@/hooks/queries";
import { useAuth } from "@/features/auth/AuthContext";
import { formatLongDate } from "@/lib/utils";
import { RecommendationsCard, TasksTodayCard, TodayHabitsCard } from "./widgets";
import { LifeScoreCard } from "./LifeScoreCard";

/** One band of the page. Bands enter in sequence rather than all at once. */
function Section({ i, children }: { i: number; children: ReactNode }) {
  return (
    <div className="stagger" style={{ ["--i" as string]: i }}>
      {children}
    </div>
  );
}

function HeroHeader({
  greeting,
  date,
  onQuickAdd,
}: {
  greeting: string;
  date: string;
  onQuickAdd: () => void;
}) {
  const { user } = useAuth();
  // The backend greeting is time-of-day only ("Good evening"); the account
  // supplies the name, so the two are composed here rather than server-side.
  const name = user?.display_name?.trim() || user?.username;

  return (
    <div className="flex flex-wrap items-end justify-between gap-3 pt-1">
      <div>
        <h2 className="text-[28px] font-display font-semibold leading-tight text-ink">
          {greeting}
          {name && <span className="text-accent">, {name}</span>}
        </h2>
        <p className="text-sm text-ink-muted">{formatLongDate(date)}</p>
      </div>
      <Button variant="outline" onClick={onQuickAdd}>
        <Plus size={16} /> Quick add
      </Button>
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className="space-y-5">
      <Skeleton className="h-12 w-64" />
      <Skeleton className="h-72 rounded-2xl" />
      <Skeleton className="h-36 rounded-2xl" />
      <div className="grid gap-4 lg:grid-cols-12">
        <div className="space-y-4 lg:col-span-7">
          <Skeleton className="h-56 rounded-2xl" />
          <Skeleton className="h-44 rounded-2xl" />
        </div>
        <div className="space-y-4 lg:col-span-5">
          <Skeleton className="h-52 rounded-2xl" />
          <Skeleton className="h-48 rounded-2xl" />
        </div>
      </div>
    </div>
  );
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <Card className="mx-auto mt-10 max-w-md p-8 text-center">
      <div className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-danger-soft text-danger">
        <AlertTriangle size={22} />
      </div>
      <h3 className="mt-4 font-display text-lg font-semibold text-ink">Couldn't reach Atlas</h3>
      <p className="mt-1 text-sm text-ink-muted">{message}</p>
      <Button className="mt-4" variant="outline" onClick={onRetry}>
        Retry
      </Button>
    </Card>
  );
}

/**
 * Dashboard reading order, top to bottom:
 *   how am I doing → how consistent have I been → what's on today → what's next
 *
 * The year heatmap sits directly under the headline rather than buried at the
 * bottom: it's the answer to "am I actually keeping this up", which belongs
 * next to the score it explains, not below three columns of detail.
 */
export function DashboardPage() {
  const navigate = useNavigate();
  const { data: d, isLoading, isError, error, refetch } = useDashboard();

  if (isLoading) return <DashboardSkeleton />;
  if (isError || !d)
    return (
      <ErrorState
        message={(error as Error)?.message ?? "Request failed"}
        onRetry={() => refetch()}
      />
    );

  return (
    <div className="space-y-5">
      <Section i={0}>
        <HeroHeader
          greeting={d.greeting}
          date={d.date}
          onQuickAdd={() => navigate("/habits?new=1")}
        />
      </Section>

      <Section i={1}>
        <LifeScoreCard d={d} />
      </Section>

      {/* What today actually asks of you, and one short list of nudges. The
          retrospective views — heatmap, streaks, wellbeing, forecast — moved to
          Analytics and Plan, where you go to look back rather than to act. */}
      <Section i={2}>
        <div className="grid gap-4 lg:grid-cols-12">
          <div className="space-y-4 lg:col-span-7">
            <TodayHabitsCard
              items={d.habits_today}
              completed={d.habits_completed}
              total={d.habits_total}
            />
            <TasksTodayCard
              tasks={d.tasks_today}
              suggested={d.suggested_task ?? null}
              openCount={d.tasks_open}
            />
          </div>
          <div className="lg:col-span-5">
            <RecommendationsCard
              recs={d.recommendations}
              modelBacked={d.recommendations_model_backed}
            />
          </div>
        </div>
      </Section>
    </div>
  );
}
