import { useEffect, useMemo, useState } from "react";
import {
  Brain,
  ChevronDown,
  FlaskConical,
  Moon,
  Sparkles,
  Target,
  TrendingDown,
  TrendingUp,
  Zap,
} from "lucide-react";
import { Card, CardBody } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useSimulation, useTrainModel } from "@/hooks/queries";
import { cn } from "@/lib/utils";
import type { SimHabitRow, SimulationRequest, TimeOfDay } from "@/lib/types";

const TODS: { value: TimeOfDay | ""; label: string }[] = [
  { value: "", label: "Off" },
  { value: "morning", label: "Morning" },
  { value: "afternoon", label: "Afternoon" },
  { value: "evening", label: "Evening" },
];

function deltaColor(delta: number): string {
  if (delta > 0.005) return "rgb(var(--success))";
  if (delta < -0.005) return "rgb(var(--danger))";
  return "rgb(var(--ink-faint))";
}

function useDebounced<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value);
  const key = JSON.stringify(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, ms]);
  return debounced;
}

/* --------------------------------------------------------------- lever control */

function Lever({
  icon: Icon,
  label,
  on,
  onToggle,
  children,
}: {
  icon: typeof Moon;
  label: string;
  on: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className={cn("glass-inset rounded-xl p-3 transition-opacity", !on && "opacity-60")}>
      <button onClick={onToggle} className="flex w-full items-center gap-2 text-left">
        <span
          className={cn(
            "grid h-6 w-6 shrink-0 place-items-center rounded-lg",
            on ? "bg-accent text-white" : "bg-ink/10 text-ink-faint",
          )}
        >
          <Icon size={13} />
        </span>
        <span className="flex-1 text-[13px] font-medium text-ink">{label}</span>
        <span
          className={cn(
            "relative h-4 w-7 rounded-full transition-colors",
            on ? "bg-accent" : "bg-ink/20",
          )}
        >
          <span
            className={cn(
              "absolute top-0.5 h-3 w-3 rounded-full bg-white transition-all",
              on ? "left-3.5" : "left-0.5",
            )}
          />
        </span>
      </button>
      <div className={cn("mt-2.5", !on && "pointer-events-none")}>{children}</div>
    </div>
  );
}

function Range({
  min,
  max,
  step,
  value,
  onChange,
  display,
}: {
  min: number;
  max: number;
  step: number;
  value: number;
  onChange: (v: number) => void;
  display: string;
}) {
  return (
    <div>
      <div className="mb-1 text-right text-[12px] font-semibold tabular-nums text-ink">{display}</div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full"
        style={{ accentColor: "rgb(var(--accent))" }}
      />
    </div>
  );
}

/* -------------------------------------------------------------- result row */

function ResultRow({ row }: { row: SimHabitRow }) {
  const base = Math.round(row.baseline * 100);
  const sim = Math.round(row.simulated * 100);
  const d = Math.round(row.delta * 100);
  const color = deltaColor(row.delta);
  return (
    <div>
      <div className="flex items-center gap-2">
        <span className="min-w-0 flex-1 truncate text-[13px] text-ink">{row.title}</span>
        <span className="text-[12px] tabular-nums text-ink-faint">{base}%</span>
        <span className="text-ink-faint">→</span>
        <span className="text-[12px] font-semibold tabular-nums text-ink">{sim}%</span>
        <span
          className="w-11 rounded-full px-1.5 py-0.5 text-center text-[10px] font-semibold tabular-nums"
          style={{ color, backgroundColor: `${color}1f` }}
        >
          {d > 0 ? "+" : ""}
          {d}%
        </span>
      </div>
      <div className="relative mt-1 h-1.5 overflow-hidden rounded-full bg-ink/10">
        <div
          className="h-full rounded-full transition-[width] duration-500"
          style={{ width: `${sim}%`, backgroundColor: color }}
        />
        <span
          className="absolute top-0 h-full w-0.5 bg-ink/40"
          style={{ left: `${base}%` }}
          title={`was ${base}%`}
        />
      </div>
    </div>
  );
}

/* -------------------------------------------------------------- main card */

export function HabitSimulator() {
  const [open, setOpen] = useState(false);
  const [sleepOn, setSleepOn] = useState(true);
  const [sleep, setSleep] = useState(8);
  const [energyOn, setEnergyOn] = useState(false);
  const [energy, setEnergy] = useState(4);
  const [rateOn, setRateOn] = useState(false);
  const [rate, setRate] = useState(90);
  const [tod, setTod] = useState<TimeOfDay | "">("");

  const body: SimulationRequest = useMemo(
    () => ({
      sleep_prev: sleepOn ? sleep : null,
      energy_prev: energyOn ? energy : null,
      min_rate: rateOn ? rate / 100 : null,
      time_of_day: tod || null,
    }),
    [sleepOn, sleep, energyOn, energy, rateOn, rate, tod],
  );
  const debounced = useDebounced(body, 220);
  const { data, isFetching } = useSimulation(debounced, open);
  const train = useTrainModel();

  const notReady = data && data.available === false;
  const movers = (data?.rows ?? []).filter((r) => !r.done_today);
  const deltaExp = data?.delta_expected ?? 0;

  return (
    <Card>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2.5 px-4 py-3 text-left"
      >
        <span className="grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-accent-soft text-accent">
          <FlaskConical size={15} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-semibold text-ink">What-if simulator</div>
          <div className="text-[12px] text-ink-muted">
            Model your day differently and see the predicted impact.
          </div>
        </div>
        <ChevronDown
          size={16}
          className={cn("shrink-0 text-ink-faint transition-transform", open && "rotate-180")}
        />
      </button>

      {open && (
        <CardBody className="border-t border-border/10 pt-4">
          {notReady ? (
            <div className="flex flex-col items-center gap-3 py-6 text-center">
              <Brain size={22} className="text-accent" />
              <p className="max-w-xs text-sm text-ink-muted">
                Train the completion model to run what-if simulations on your habits.
              </p>
              <Button onClick={() => train.mutate()} disabled={train.isPending}>
                <Brain size={15} /> {train.isPending ? "Training…" : "Train model"}
              </Button>
              {/* A dead button with no explanation is worse than no button.
                  Training needs enough settled history, and in a build without
                  the ML extras the endpoint isn't mounted at all. */}
              {train.isError && (
                <p className="bg-danger-soft max-w-xs rounded-xl px-3 py-2 text-[12px] text-danger">
                  {String((train.error as Error)?.message ?? "").includes("404")
                    ? "This build doesn't include the ML layer, so the model can't be trained here."
                    : String((train.error as Error)?.message ?? "Training failed.")}
                </p>
              )}
              {train.isSuccess && train.data && !train.data.trained && (
                <p className="max-w-xs text-[12px] text-ink-faint">{train.data.reason}</p>
              )}
            </div>
          ) : (
            <div className="space-y-4">
              {/* Levers */}
              <div className="grid gap-2.5 sm:grid-cols-3">
                <Lever icon={Moon} label="Sleep" on={sleepOn} onToggle={() => setSleepOn((v) => !v)}>
                  <Range
                    min={4}
                    max={10}
                    step={0.5}
                    value={sleep}
                    onChange={setSleep}
                    display={`${sleep.toFixed(1)}h`}
                  />
                </Lever>
                <Lever
                  icon={Zap}
                  label="Energy"
                  on={energyOn}
                  onToggle={() => setEnergyOn((v) => !v)}
                >
                  <Range
                    min={1}
                    max={5}
                    step={1}
                    value={energy}
                    onChange={setEnergy}
                    display={`${energy}/5`}
                  />
                </Lever>
                <Lever
                  icon={Target}
                  label="Consistency"
                  on={rateOn}
                  onToggle={() => setRateOn((v) => !v)}
                >
                  <Range
                    min={50}
                    max={100}
                    step={5}
                    value={rate}
                    onChange={setRate}
                    display={`≥${rate}%`}
                  />
                </Lever>
              </div>

              {/* Move-all-to time of day */}
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[12px] text-ink-muted">Move habits to</span>
                <div className="flex gap-1 rounded-xl bg-ink/[0.06] p-0.5">
                  {TODS.map((t) => (
                    <button
                      key={t.label}
                      onClick={() => setTod(t.value)}
                      className={cn(
                        "rounded-lg px-2.5 py-1 text-[12px] font-medium transition-colors",
                        tod === t.value
                          ? "bg-accent text-white"
                          : "text-ink-muted hover:text-ink",
                      )}
                    >
                      {t.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Headline */}
              {data && data.levers.length > 0 ? (
                <div className="glass-inset flex items-center gap-3 rounded-xl p-3">
                  <div
                    className="grid h-9 w-9 shrink-0 place-items-center rounded-xl"
                    style={{
                      color: deltaColor(deltaExp),
                      backgroundColor: `${deltaColor(deltaExp)}1f`,
                    }}
                  >
                    {deltaExp >= 0 ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-baseline gap-2 text-sm">
                      <span className="tabular-nums text-ink-faint">
                        {data.baseline_expected.toFixed(1)}
                      </span>
                      <span className="text-ink-faint">→</span>
                      <span className="text-lg font-semibold tabular-nums text-ink">
                        {data.simulated_expected.toFixed(1)}
                      </span>
                      <span className="text-[12px] text-ink-muted">expected completions</span>
                    </div>
                    <p className="mt-0.5 text-[12px] leading-relaxed text-ink-muted">
                      {data.summary}
                    </p>
                  </div>
                </div>
              ) : (
                <p className="flex items-center gap-1.5 text-[12px] text-ink-faint">
                  <Sparkles size={12} /> Toggle a lever to see the predicted impact.
                </p>
              )}

              {/* Lever chips */}
              {data && data.levers.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {data.levers.map((l) => (
                    <span
                      key={l}
                      className="rounded-full bg-accent-soft px-2 py-0.5 text-[11px] font-medium text-accent"
                    >
                      {l}
                    </span>
                  ))}
                </div>
              )}

              {/* Per-habit rows */}
              {movers.length > 0 && (
                <div className={cn("space-y-2.5", isFetching && "opacity-70")}>
                  {movers.map((r) => (
                    <ResultRow key={r.habit_id} row={r} />
                  ))}
                </div>
              )}

              {data?.reliability != null && (
                <p className="text-[10px] text-ink-faint">
                  Counterfactuals from your trained model · reliability{" "}
                  {Math.round(data.reliability * 100)}%
                </p>
              )}
            </div>
          )}
        </CardBody>
      )}
    </Card>
  );
}
