import { useNavigate } from "react-router-dom";
import { AlertTriangle, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useDashboard } from "@/hooks/queries";
import { formatLongDate } from "@/lib/utils";
import {
  HeatmapCard,
  HeroStats,
  RecommendationsCard,
  StreaksCard,
  TasksTodayCard,
  TodayHabitsCard,
  WellbeingCard,
} from "./widgets";
import { ForecastCard } from "./ForecastCard";

function HeroHeader({
  greeting,
  date,
  onQuickAdd,
}: {
  greeting: string;
  date: string;
  onQuickAdd: () => void;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3 pt-1">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight text-ink">{greeting}</h2>
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
    <div className="space-y-4">
      <Skeleton className="h-10 w-56" />
      <Skeleton className="h-44 rounded-2xl" />
      <div className="grid gap-4 lg:grid-cols-12">
        <div className="space-y-4 lg:col-span-7">
          <Skeleton className="h-56 rounded-2xl" />
          <Skeleton className="h-40 rounded-2xl" />
        </div>
        <div className="space-y-4 lg:col-span-5">
          <Skeleton className="h-64 rounded-2xl" />
          <Skeleton className="h-32 rounded-2xl" />
        </div>
      </div>
      <Skeleton className="h-40 rounded-2xl" />
    </div>
  );
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <Card className="mx-auto mt-10 max-w-md p-8 text-center">
      <div className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-red-500/10 text-red-500">
        <AlertTriangle size={22} />
      </div>
      <h3 className="mt-4 text-lg font-semibold text-ink">Couldn't reach Atlas</h3>
      <p className="mt-1 text-sm text-ink-muted">{message}</p>
      <p className="mt-2 text-[12px] text-ink-faint">
        Is the backend running on <code>http://127.0.0.1:8000</code>?
      </p>
      <Button className="mt-4" variant="outline" onClick={onRetry}>
        Retry
      </Button>
    </Card>
  );
}

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
    <div className="animate-fade-in space-y-4">
      <HeroHeader greeting={d.greeting} date={d.date} onQuickAdd={() => navigate("/habits?new=1")} />
      <HeroStats d={d} />

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
        <div className="space-y-4 lg:col-span-5">
          <ForecastCard />
          <RecommendationsCard
            recs={d.recommendations}
            modelBacked={d.recommendations_model_backed}
          />
          <WellbeingCard mood={d.mood} energy={d.energy} sleep={d.sleep_hours} />
          <StreaksCard streaks={d.top_streaks} />
        </div>
      </div>

      <HeatmapCard />
    </div>
  );
}
