import { useEffect, useRef, useState } from "react";
import { Check, ChevronLeft, ChevronRight } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useJournalRecent, useUpsertJournal } from "@/hooks/queries";
import { cn, formatLongDate, parseDate, relativeDay, todayISO } from "@/lib/utils";
import type { JournalEntry } from "@/lib/types";

interface JForm {
  mood: number | null;
  energy: number | null;
  sleep_hours: string;
  gratitude: string;
  wins: string;
  challenges: string;
  reflection: string;
  lessons: string;
  free_writing: string;
}

const EMPTY: JForm = {
  mood: null,
  energy: null,
  sleep_hours: "",
  gratitude: "",
  wins: "",
  challenges: "",
  reflection: "",
  lessons: "",
  free_writing: "",
};

function entryToForm(e: JournalEntry | null | undefined): JForm {
  if (!e) return { ...EMPTY };
  return {
    mood: e.mood ?? null,
    energy: e.energy ?? null,
    sleep_hours: e.sleep_hours != null ? String(e.sleep_hours) : "",
    gratitude: e.gratitude ?? "",
    wins: e.wins ?? "",
    challenges: e.challenges ?? "",
    reflection: e.reflection ?? "",
    lessons: e.lessons ?? "",
    free_writing: e.free_writing ?? "",
  };
}

function formToBody(f: JForm): Partial<JournalEntry> {
  return {
    mood: f.mood,
    energy: f.energy,
    sleep_hours: f.sleep_hours !== "" ? Number(f.sleep_hours) : null,
    gratitude: f.gratitude || null,
    wins: f.wins || null,
    challenges: f.challenges || null,
    reflection: f.reflection || null,
    lessons: f.lessons || null,
    free_writing: f.free_writing || null,
  };
}

function isoOf(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
    d.getDate(),
  ).padStart(2, "0")}`;
}

function Scale({
  value,
  onChange,
  label,
}: {
  value: number | null;
  onChange: (n: number) => void;
  label: string;
}) {
  return (
    <div>
      <div className="mb-1.5 text-[13px] font-medium text-ink-muted">{label}</div>
      <div className="flex gap-1.5">
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            onClick={() => onChange(n)}
            className={cn(
              "h-9 flex-1 rounded-lg text-sm font-medium tabular-nums transition-colors",
              value === n ? "bg-accent text-white" : "bg-ink/5 text-ink-muted hover:text-ink",
            )}
          >
            {n}
          </button>
        ))}
      </div>
    </div>
  );
}

const STATUS_TEXT: Record<string, string> = {
  idle: "",
  dirty: "Unsaved changes",
  saving: "Saving…",
  saved: "All changes saved",
};

export function JournalPage() {
  const [selectedDate, setSelectedDate] = useState(todayISO());
  const { data: recent, isLoading } = useJournalRecent(90);
  const upsert = useUpsertJournal();

  const entry = recent?.find((e) => e.date === selectedDate) ?? null;

  const [form, setForm] = useState<JForm>(EMPTY);
  const [status, setStatus] = useState<"idle" | "dirty" | "saving" | "saved">("idle");
  const savedRef = useRef("");
  const formRef = useRef(form);
  formRef.current = form;

  // (Re)load the form whenever the selected day — or its server copy — changes.
  useEffect(() => {
    const f = entryToForm(entry);
    setForm(f);
    savedRef.current = JSON.stringify(f);
    setStatus("idle");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedDate, entry?.id, entry?.updated_at]);

  const persist = async () => {
    const snapshot = JSON.stringify(formRef.current);
    if (snapshot === savedRef.current) return;
    setStatus("saving");
    try {
      await upsert.mutateAsync({ date: selectedDate, body: formToBody(formRef.current) });
      savedRef.current = snapshot;
      setStatus("saved");
    } catch {
      setStatus("dirty");
    }
  };

  // Debounced autosave.
  useEffect(() => {
    if (JSON.stringify(form) === savedRef.current) return;
    setStatus("dirty");
    const id = setTimeout(persist, 1000);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form]);

  // ⌘S / Ctrl+S saves immediately.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        persist();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedDate]);

  const set = <K extends keyof JForm>(key: K, value: JForm[K]) =>
    setForm((f) => ({ ...f, [key]: value }));

  const shiftDay = (days: number) => {
    const d = parseDate(selectedDate);
    d.setDate(d.getDate() + days);
    setSelectedDate(isoOf(d));
  };

  const isToday = selectedDate === todayISO();

  return (
    <div className="animate-fade-in space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold tracking-tight text-ink">Journal</h2>
          <p className="text-sm text-ink-muted">A page for every day.</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="glass-inset flex items-center rounded-xl">
            <button
              onClick={() => shiftDay(-1)}
              className="grid h-9 w-9 place-items-center rounded-l-xl text-ink-muted hover:text-ink"
              aria-label="Previous day"
            >
              <ChevronLeft size={16} />
            </button>
            <span className="min-w-[130px] px-1 text-center text-[13px] font-medium text-ink">
              {formatLongDate(selectedDate)}
            </span>
            <button
              onClick={() => shiftDay(1)}
              disabled={isToday}
              className="grid h-9 w-9 place-items-center rounded-r-xl text-ink-muted hover:text-ink disabled:opacity-40"
              aria-label="Next day"
            >
              <ChevronRight size={16} />
            </button>
          </div>
          {!isToday && (
            <Button variant="outline" size="sm" onClick={() => setSelectedDate(todayISO())}>
              Today
            </Button>
          )}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-12">
        {/* Editor */}
        <div className="lg:col-span-8">
          <Card className="p-5">
            <div className="mb-4 flex items-center justify-between">
              <span className="text-[13px] text-ink-muted">
                {isToday ? "Today" : relativeDay(selectedDate)}
              </span>
              <span
                className={cn(
                  "flex items-center gap-1.5 text-[12px]",
                  status === "saved" ? "text-success" : "text-ink-faint",
                )}
              >
                {status === "saved" && <Check size={12} />}
                {STATUS_TEXT[status]}
              </span>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              <Scale label="Mood" value={form.mood} onChange={(n) => set("mood", n)} />
              <Scale label="Energy" value={form.energy} onChange={(n) => set("energy", n)} />
              <div>
                <div className="mb-1.5 text-[13px] font-medium text-ink-muted">Sleep (hours)</div>
                <Input
                  type="number"
                  min={0}
                  max={24}
                  step={0.5}
                  value={form.sleep_hours}
                  onChange={(e) => set("sleep_hours", e.target.value)}
                  placeholder="7.5"
                />
              </div>
            </div>

            <div className="my-5 border-t border-border/10" />

            <div className="grid gap-4 sm:grid-cols-2">
              <JField label="Grateful for" value={form.gratitude} onChange={(v) => set("gratitude", v)} />
              <JField label="Wins" value={form.wins} onChange={(v) => set("wins", v)} />
              <JField label="Challenges" value={form.challenges} onChange={(v) => set("challenges", v)} />
              <JField label="Lessons" value={form.lessons} onChange={(v) => set("lessons", v)} />
            </div>

            <div className="mt-4">
              <JField label="Reflection" value={form.reflection} onChange={(v) => set("reflection", v)} rows={4} />
            </div>
            <div className="mt-4">
              <JField
                label="Free writing"
                value={form.free_writing}
                onChange={(v) => set("free_writing", v)}
                rows={5}
              />
            </div>

            <div className="mt-5 flex items-center justify-between">
              <span className="text-[11px] text-ink-faint">
                Autosaves as you type · <kbd className="rounded bg-ink/10 px-1 py-0.5">⌘S</kbd> to save now
              </span>
              <Button onClick={persist} disabled={status === "saving" || status === "idle"}>
                {status === "saving" ? "Saving…" : "Save"}
              </Button>
            </div>
          </Card>
        </div>

        {/* Recent entries */}
        <div className="lg:col-span-4">
          <Card className="p-3">
            <div className="mb-1 px-2 pt-1 text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-muted">
              Recent
            </div>
            <div className="space-y-1">
              {isLoading ? (
                Array.from({ length: 6 }).map((_, i) => (
                  <Skeleton key={i} className="h-12 rounded-xl" />
                ))
              ) : recent && recent.length > 0 ? (
                recent.map((e) => (
                  <button
                    key={e.id}
                    onClick={() => setSelectedDate(e.date)}
                    className={cn(
                      "w-full rounded-xl px-3 py-2 text-left transition-colors",
                      e.date === selectedDate ? "bg-accent-soft" : "hover:bg-ink/5",
                    )}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-ink">{formatLongDate(e.date)}</span>
                      <span className="text-[11px] tabular-nums text-ink-faint">
                        {e.mood ? `♥${e.mood}` : ""} {e.energy ? `⚡${e.energy}` : ""}
                      </span>
                    </div>
                    {(e.wins || e.gratitude) && (
                      <div className="mt-0.5 truncate text-[12px] text-ink-muted">
                        {e.wins || e.gratitude}
                      </div>
                    )}
                  </button>
                ))
              ) : (
                <p className="px-2 py-6 text-center text-[13px] text-ink-faint">
                  No entries yet. Start with today.
                </p>
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

function JField({
  label,
  value,
  onChange,
  rows = 2,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  rows?: number;
}) {
  return (
    <label className="block space-y-1.5">
      <span className="text-[13px] font-medium text-ink-muted">{label}</span>
      <Textarea rows={rows} value={value} onChange={(e) => onChange(e.target.value)} className="min-h-0" />
    </label>
  );
}
