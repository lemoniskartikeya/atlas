import { useState, type FormEvent } from "react";
import { Dialog } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/input";
import { useCreateHabit } from "@/hooks/queries";
import { cn } from "@/lib/utils";
import type { Frequency, Priority, TimeOfDay } from "@/lib/types";

const CATEGORIES = ["Mindfulness", "Health", "Work", "Growth", "Social", "Creative", "Other"];
const WEEKDAYS: [string, number][] = [
  ["Mon", 0],
  ["Tue", 1],
  ["Wed", 2],
  ["Thu", 3],
  ["Fri", 4],
  ["Sat", 5],
  ["Sun", 6],
];

function WeekdayPicker({ value, onChange }: { value: number[]; onChange: (v: number[]) => void }) {
  return (
    <div className="flex gap-1">
      {WEEKDAYS.map(([label, n]) => {
        const on = value.includes(n);
        return (
          <button
            type="button"
            key={n}
            onClick={() =>
              onChange(on ? value.filter((v) => v !== n) : [...value, n].sort((a, b) => a - b))
            }
            className={cn(
              "h-8 flex-1 rounded-lg text-[12px] font-medium transition-colors",
              on ? "bg-accent text-white" : "bg-ink/5 text-ink-muted hover:text-ink",
            )}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}

export function CreateHabitDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const create = useCreateHabit();
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("Health");
  const [frequency, setFrequency] = useState<Frequency>("daily");
  const [timePref, setTimePref] = useState<TimeOfDay>("any");
  const [priority, setPriority] = useState<Priority>("medium");
  const [duration, setDuration] = useState("");
  const [customDays, setCustomDays] = useState<number[]>([0, 2, 4]);
  const [desc, setDesc] = useState("");

  const reset = () => {
    setTitle("");
    setDesc("");
    setDuration("");
    setFrequency("daily");
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    await create.mutateAsync({
      title: title.trim(),
      category,
      frequency,
      time_preference: timePref,
      priority,
      estimated_duration_min: duration ? Number(duration) : null,
      custom_days: frequency === "custom" ? customDays : null,
      description: desc.trim() || null,
    });
    reset();
    onClose();
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="New habit"
      description="Track something you want to do consistently."
    >
      <form onSubmit={submit} className="space-y-4">
        <Field label="Title">
          <Input
            autoFocus
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Meditate for 10 minutes"
          />
        </Field>

        <div className="grid grid-cols-2 gap-3">
          <Field label="Category">
            <Select value={category} onChange={(e) => setCategory(e.target.value)}>
              {CATEGORIES.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </Select>
          </Field>
          <Field label="Frequency">
            <Select value={frequency} onChange={(e) => setFrequency(e.target.value as Frequency)}>
              <option value="daily">Daily</option>
              <option value="custom">Specific days</option>
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
            </Select>
          </Field>
        </div>

        {frequency === "custom" && <WeekdayPicker value={customDays} onChange={setCustomDays} />}

        <div className="grid grid-cols-3 gap-3">
          <Field label="Time of day">
            <Select value={timePref} onChange={(e) => setTimePref(e.target.value as TimeOfDay)}>
              <option value="any">Any</option>
              <option value="morning">Morning</option>
              <option value="afternoon">Afternoon</option>
              <option value="evening">Evening</option>
              <option value="night">Night</option>
            </Select>
          </Field>
          <Field label="Priority">
            <Select value={priority} onChange={(e) => setPriority(e.target.value as Priority)}>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="critical">Critical</option>
            </Select>
          </Field>
          <Field label="Est. min">
            <Input
              type="number"
              min={0}
              value={duration}
              onChange={(e) => setDuration(e.target.value)}
              placeholder="10"
            />
          </Field>
        </div>

        <Field label="Notes (optional)">
          <Textarea value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="Why this matters…" />
        </Field>

        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={!title.trim() || create.isPending}>
            {create.isPending ? "Adding…" : "Add habit"}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
