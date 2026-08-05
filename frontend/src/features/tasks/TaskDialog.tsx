import { useEffect, useState, type FormEvent } from "react";
import { Trash2 } from "lucide-react";
import { Dialog } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/input";
import { useCreateTask, useDeleteTask, useUpdateTask } from "@/hooks/queries";
import type { Priority, Task, TaskStatus } from "@/lib/types";

export function TaskDialog({
  open,
  onClose,
  task,
}: {
  open: boolean;
  onClose: () => void;
  task?: Task | null;
}) {
  const create = useCreateTask();
  const update = useUpdateTask();
  const del = useDeleteTask();
  const editing = Boolean(task);

  const [title, setTitle] = useState("");
  const [desc, setDesc] = useState("");
  const [status, setStatus] = useState<TaskStatus>("todo");
  const [priority, setPriority] = useState<Priority>("medium");
  const [due, setDue] = useState("");
  const [effort, setEffort] = useState("");
  const [tags, setTags] = useState("");

  useEffect(() => {
    if (!open) return;
    setTitle(task?.title ?? "");
    setDesc(task?.description ?? "");
    setStatus(task?.status ?? "todo");
    setPriority(task?.priority ?? "medium");
    setDue(task?.due_date ?? "");
    setEffort(task?.estimated_effort_min ? String(task.estimated_effort_min) : "");
    setTags((task?.tags ?? []).join(", "));
  }, [open, task]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    const body: Partial<Task> & { title: string } = {
      title: title.trim(),
      description: desc.trim() || null,
      status,
      priority,
      due_date: due || null,
      estimated_effort_min: effort ? Number(effort) : null,
      tags: tags.trim() ? tags.split(",").map((t) => t.trim()).filter(Boolean) : null,
    };
    if (editing && task) await update.mutateAsync({ id: task.id, body });
    else await create.mutateAsync(body);
    onClose();
  };

  const remove = async () => {
    if (task && window.confirm(`Delete “${task.title}”?`)) {
      await del.mutateAsync(task.id);
      onClose();
    }
  };

  const busy = create.isPending || update.isPending;

  return (
    <Dialog open={open} onClose={onClose} title={editing ? "Edit task" : "New task"}>
      <form onSubmit={submit} className="space-y-4">
        <Field label="Title">
          <Input
            autoFocus
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="What needs doing?"
          />
        </Field>
        <Field label="Notes (optional)">
          <Textarea value={desc} onChange={(e) => setDesc(e.target.value)} />
        </Field>

        <div className="grid grid-cols-2 gap-3">
          <Field label="Status">
            <Select value={status} onChange={(e) => setStatus(e.target.value as TaskStatus)}>
              <option value="todo">To do</option>
              <option value="in_progress">In progress</option>
              <option value="done">Done</option>
              <option value="backlog">Backlog</option>
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
        </div>

        <div className="grid grid-cols-2 gap-3">
          <Field label="Due date">
            <Input type="date" value={due} onChange={(e) => setDue(e.target.value)} />
          </Field>
          <Field label="Est. minutes">
            <Input
              type="number"
              min={0}
              value={effort}
              onChange={(e) => setEffort(e.target.value)}
              placeholder="30"
            />
          </Field>
        </div>

        <Field label="Tags (comma-separated)">
          <Input value={tags} onChange={(e) => setTags(e.target.value)} placeholder="work, deep" />
        </Field>

        <div className="flex items-center justify-between pt-1">
          <div>
            {editing && (
              <Button type="button" variant="danger" onClick={remove}>
                <Trash2 size={15} /> Delete
              </Button>
            )}
          </div>
          <div className="flex gap-2">
            <Button type="button" variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={!title.trim() || busy}>
              {busy ? "Saving…" : editing ? "Save" : "Add task"}
            </Button>
          </div>
        </div>
      </form>
    </Dialog>
  );
}
