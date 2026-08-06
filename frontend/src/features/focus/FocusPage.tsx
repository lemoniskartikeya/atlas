import { useCallback, useEffect, useRef, useState } from "react";
import {
  Check,
  Maximize2,
  Minimize2,
  Pause,
  Play,
  RotateCcw,
  Square,
  Zap,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Stat } from "@/components/ui/stat";
import { useCreateFocus, useFocusRecent, useFocusStats, useTasks } from "@/hooks/queries";
import { cn, relativeDay } from "@/lib/utils";

const PRESETS = [15, 25, 50];
type Phase = "idle" | "running" | "paused" | "done";

function fmt(seconds: number): string {
  const s = Math.max(0, seconds);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

function TimerRing({ fraction, children }: { fraction: number; children: React.ReactNode }) {
  const size = 260;
  const stroke = 12;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const dash = c * Math.max(0, Math.min(1, fraction));
  return (
    <div className="relative grid place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgb(var(--ink) / 0.08)" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="rgb(var(--accent))"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${dash} ${c - dash}`}
          style={{ transition: "stroke-dasharray 0.95s linear" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">{children}</div>
    </div>
  );
}

export function FocusPage() {
  const [durationMin, setDurationMin] = useState(25);
  const [phase, setPhase] = useState<Phase>("idle");
  const [secondsLeft, setSecondsLeft] = useState(25 * 60);
  const [distractions, setDistractions] = useState(0);
  const [taskId, setTaskId] = useState("");
  const [note, setNote] = useState("");
  const [fs, setFs] = useState(false);

  const endsAtRef = useRef<number>(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  const create = useCreateFocus();
  const { data: stats } = useFocusStats();
  const { data: recent } = useFocusRecent(8);
  const { data: openTasks } = useTasks("open");

  const total = durationMin * 60;

  const clear = () => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    intervalRef.current = null;
  };

  const log = useCallback(
    (minutes: number) => {
      if (minutes >= 1) {
        create.mutate({
          duration_min: minutes,
          distractions,
          note: note.trim() || null,
          task_id: taskId || null,
        });
      }
      setPhase("done");
    },
    [create, distractions, note, taskId],
  );

  const tick = useCallback(() => {
    const left = Math.round((endsAtRef.current - Date.now()) / 1000);
    if (left <= 0) {
      clear();
      setSecondsLeft(0);
      log(durationMin);
    } else {
      setSecondsLeft(left);
    }
  }, [durationMin, log]);

  const start = () => {
    endsAtRef.current = Date.now() + secondsLeft * 1000;
    setPhase("running");
    clear();
    intervalRef.current = setInterval(tick, 500);
  };

  const pause = () => {
    clear();
    setPhase("paused");
  };

  const reset = (mins = durationMin) => {
    clear();
    setPhase("idle");
    setSecondsLeft(mins * 60);
    setDistractions(0);
    setNote("");
  };

  const finishEarly = () => {
    clear();
    log(Math.round((total - secondsLeft) / 60));
  };

  const pickPreset = (m: number) => {
    if (phase === "running") return;
    setDurationMin(m);
    setSecondsLeft(m * 60);
    setPhase("idle");
  };

  useEffect(() => () => clear(), []);
  useEffect(() => {
    const onChange = () => setFs(!!document.fullscreenElement);
    document.addEventListener("fullscreenchange", onChange);
    return () => document.removeEventListener("fullscreenchange", onChange);
  }, []);

  const toggleFs = () => {
    if (document.fullscreenElement) document.exitFullscreen();
    else rootRef.current?.requestFullscreen?.();
  };

  const running = phase === "running";
  const fraction = phase === "idle" ? 1 : secondsLeft / total;
  const phaseLabel =
    phase === "running"
      ? "Focusing"
      : phase === "paused"
        ? "Paused"
        : phase === "done"
          ? "Nice work"
          : "Ready";

  return (
    <div className="animate-fade-in space-y-4">
      <div>
        <h2 className="text-xl font-semibold tracking-tight text-ink">Focus</h2>
        <p className="text-sm text-ink-muted">Protect a block of deep work. Log it when you're done.</p>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Card className="p-4"><Stat label="Today" value={`${stats?.minutes_today ?? 0}m`} sub={`${stats?.sessions_today ?? 0} sessions`} /></Card>
        <Card className="p-4"><Stat label="This week" value={`${stats?.minutes_week ?? 0}m`} sub={`${stats?.sessions_week ?? 0} sessions`} accent /></Card>
        <Card className="p-4"><Stat label="Best day" value={`${stats?.best_day_minutes ?? 0}m`} /></Card>
        <Card className="p-4"><Stat label="Avg distractions" value={stats?.avg_distractions ?? "—"} sub="per session" /></Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-5">
        <Card
          ref={rootRef}
          className={cn(
            "flex flex-col items-center gap-6 p-8 lg:col-span-3",
            fs && "fixed inset-0 z-50 justify-center rounded-none",
          )}
        >
          <div className="flex gap-1.5 rounded-xl bg-ink/[0.06] p-1">
            {PRESETS.map((m) => (
              <button
                key={m}
                onClick={() => pickPreset(m)}
                disabled={running}
                className={cn(
                  "rounded-lg px-3 py-1 text-[13px] font-medium transition-colors disabled:opacity-40",
                  durationMin === m ? "bg-accent text-white" : "text-ink-muted hover:text-ink",
                )}
              >
                {m}m
              </button>
            ))}
          </div>

          <TimerRing fraction={fraction}>
            <span className="text-5xl font-semibold tabular-nums tracking-tight text-ink">
              {fmt(secondsLeft)}
            </span>
            <span className="mt-1 text-[12px] uppercase tracking-wide text-ink-faint">{phaseLabel}</span>
          </TimerRing>

          <div className="flex items-center gap-2">
            {phase === "idle" || phase === "done" ? (
              <button
                onClick={phase === "done" ? () => reset() : start}
                className="flex items-center gap-2 rounded-xl bg-accent px-5 py-2.5 text-sm font-medium text-white"
              >
                {phase === "done" ? <RotateCcw size={16} /> : <Play size={16} />}
                {phase === "done" ? "New session" : "Start"}
              </button>
            ) : (
              <>
                <button
                  onClick={running ? pause : start}
                  className="flex items-center gap-2 rounded-xl bg-accent px-5 py-2.5 text-sm font-medium text-white"
                >
                  {running ? <Pause size={16} /> : <Play size={16} />}
                  {running ? "Pause" : "Resume"}
                </button>
                <button
                  onClick={finishEarly}
                  className="flex items-center gap-2 rounded-xl bg-ink/[0.06] px-4 py-2.5 text-sm font-medium text-ink-muted transition-colors hover:text-ink"
                >
                  <Square size={14} /> Finish
                </button>
                <button
                  onClick={() => reset()}
                  aria-label="Reset"
                  className="grid h-10 w-10 place-items-center rounded-xl text-ink-faint transition-colors hover:bg-ink/5 hover:text-ink"
                >
                  <RotateCcw size={16} />
                </button>
              </>
            )}
          </div>

          {(running || phase === "paused") && (
            <button
              onClick={() => setDistractions((d) => d + 1)}
              className="flex items-center gap-2 rounded-full bg-warn/10 px-4 py-1.5 text-[13px] font-medium text-[color:rgb(var(--warn))] transition-transform active:scale-95"
            >
              <Zap size={14} /> Distracted{distractions > 0 ? ` · ${distractions}` : ""}
            </button>
          )}

          {phase === "done" && create.data && (
            <p className="flex items-center gap-1.5 text-sm text-success">
              <Check size={15} /> Logged {create.data.duration_min} min of focus.
            </p>
          )}

          <button
            onClick={toggleFs}
            aria-label="Toggle fullscreen"
            className="absolute right-4 top-4 grid h-8 w-8 place-items-center rounded-lg text-ink-faint transition-colors hover:bg-ink/5 hover:text-ink"
          >
            {fs ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
          </button>
        </Card>

        <div className="space-y-4 lg:col-span-2">
          <Card className="space-y-3 p-4">
            <div className="text-[13px] font-semibold text-ink">Session</div>
            <div>
              <label className="text-[11px] uppercase tracking-wide text-ink-faint">Working on (optional)</label>
              <select
                value={taskId}
                onChange={(e) => setTaskId(e.target.value)}
                className="mt-1 h-9 w-full rounded-lg bg-ink/[0.05] px-2.5 text-sm text-ink outline-none"
              >
                <option value="">— No task —</option>
                {(openTasks ?? []).map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.title}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-[11px] uppercase tracking-wide text-ink-faint">Note (optional)</label>
              <input
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="What are you focusing on?"
                className="mt-1 h-9 w-full rounded-lg bg-ink/[0.05] px-2.5 text-sm text-ink outline-none placeholder:text-ink-faint"
              />
            </div>
          </Card>

          <Card className="p-4">
            <div className="mb-2 text-[13px] font-semibold text-ink">Recent sessions</div>
            {recent && recent.length > 0 ? (
              <div className="space-y-2">
                {recent.map((s) => (
                  <div key={s.id} className="flex items-center gap-2 text-sm">
                    <span className="grid h-6 w-6 shrink-0 place-items-center rounded-lg bg-accent-soft text-accent">
                      <Zap size={12} />
                    </span>
                    <span className="text-ink">{s.duration_min}m</span>
                    {s.distractions > 0 && (
                      <span className="text-[12px] text-ink-faint">· {s.distractions} distraction{s.distractions !== 1 ? "s" : ""}</span>
                    )}
                    <span className="ml-auto text-[11px] text-ink-faint">{relativeDay(s.started_at)}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-ink-muted">No sessions yet — start your first focus block.</p>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
