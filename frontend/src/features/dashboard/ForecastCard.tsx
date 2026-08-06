import { Brain, Check, RefreshCw } from "lucide-react";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useMlPredictions, useTrainModel } from "@/hooks/queries";
import { cn } from "@/lib/utils";

export function ForecastCard() {
  const { data, isLoading, isError } = useMlPredictions();
  const train = useTrainModel();

  // ML router unavailable (deps not installed) — stay quiet rather than error.
  if (isError) return null;

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Completion forecast</CardTitle>
        </CardHeader>
        <CardBody>
          <Skeleton className="h-40" />
        </CardBody>
      </Card>
    );
  }

  if (!data?.trained) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Completion forecast</CardTitle>
          <Brain size={15} className="text-accent" />
        </CardHeader>
        <CardBody>
          <p className="text-sm leading-relaxed text-ink-muted">
            Train a model on your history to predict today's completions — with the reasoning
            behind each one.
          </p>
          <Button className="mt-3 w-full" onClick={() => train.mutate()} disabled={train.isPending}>
            <Brain size={15} /> {train.isPending ? "Training…" : "Train model"}
          </Button>
          {train.data && train.data.trained === false && (
            <p className="mt-2 text-[12px] text-ink-faint">{train.data.reason}</p>
          )}
        </CardBody>
      </Card>
    );
  }

  const reliability = data.reliability != null ? Math.round(data.reliability * 100) : null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Completion forecast</CardTitle>
        <div className="flex items-center gap-2">
          {reliability != null && (
            <span
              title="Held-out ROC-AUC — how reliably the model ranks completions"
              className="rounded-full bg-accent-soft px-2 py-0.5 text-[10px] font-semibold text-accent"
            >
              reliability {reliability}%
            </span>
          )}
          <button
            onClick={() => train.mutate()}
            disabled={train.isPending}
            title="Retrain on the latest data"
            aria-label="Retrain model"
            className="text-ink-faint transition-colors hover:text-ink"
          >
            <RefreshCw size={14} className={cn(train.isPending && "animate-spin")} />
          </button>
        </div>
      </CardHeader>
      <CardBody className="space-y-3">
        {data.predictions.length === 0 && (
          <p className="text-sm text-ink-muted">Nothing due today to forecast.</p>
        )}
        {data.predictions.map((p) => {
          const value = Math.round(p.probability * 100);
          return (
            <div key={p.habit_id}>
              <div className="flex items-center gap-2">
                <span
                  className="h-2 w-2 shrink-0 rounded-full"
                  style={{ backgroundColor: p.color ?? "rgb(var(--accent))" }}
                />
                <span
                  className={cn(
                    "min-w-0 flex-1 truncate text-sm",
                    p.done_today ? "text-ink-faint" : "text-ink",
                  )}
                >
                  {p.title}
                </span>
                {p.done_today ? (
                  <span className="flex items-center gap-1 text-[11px] text-success">
                    <Check size={12} /> done
                  </span>
                ) : (
                  <span className="text-[12px] font-semibold tabular-nums text-ink-muted">
                    {value}%
                  </span>
                )}
              </div>
              <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-ink/10">
                <div
                  className="h-full rounded-full bg-accent transition-[width] duration-700"
                  style={{ width: `${value}%`, opacity: p.done_today ? 0.4 : 1 }}
                />
              </div>
              <p className="mt-1 text-[11px] leading-relaxed text-ink-faint">{p.explanation}</p>
            </div>
          );
        })}
        <p className="pt-0.5 text-[10px] text-ink-faint">
          Learned &amp; explainable · {data.model_type}
        </p>
      </CardBody>
    </Card>
  );
}
