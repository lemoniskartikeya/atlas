import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Habit, HabitCreate, HabitLog, JournalEntry, Task } from "@/lib/types";

export const keys = {
  dashboard: ["dashboard"] as const,
  habits: ["habits"] as const,
  habit: (id: string) => ["habit", id] as const,
  tasks: (scope: string) => ["tasks", scope] as const,
  heatmap: (days: number) => ["heatmap", days] as const,
  journal: ["journal"] as const,
};

export function useDashboard() {
  return useQuery({ queryKey: keys.dashboard, queryFn: api.dashboard });
}

export function useHabits(includeArchived = false) {
  return useQuery({
    queryKey: [...keys.habits, includeArchived],
    queryFn: () => api.habits(includeArchived),
  });
}

export function useHeatmap(days = 365) {
  return useQuery({ queryKey: keys.heatmap(days), queryFn: () => api.heatmap(days) });
}

export function useTasks(scope: "all" | "today" | "upcoming" | "open" = "all") {
  return useQuery({ queryKey: keys.tasks(scope), queryFn: () => api.tasks(scope) });
}

/** Habit logging touches streaks, the dashboard, and the heatmap — refresh all three. */
function useRefreshEverything() {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: keys.dashboard });
    qc.invalidateQueries({ queryKey: keys.habits });
    qc.invalidateQueries({ queryKey: ["heatmap"] });
    qc.invalidateQueries({ queryKey: ["habit"] });
    qc.invalidateQueries({ queryKey: ["tasks"] });
  };
}

export function useCreateHabit() {
  const refresh = useRefreshEverything();
  return useMutation({ mutationFn: (b: HabitCreate) => api.createHabit(b), onSuccess: refresh });
}

export function useLogHabit() {
  const refresh = useRefreshEverything();
  return useMutation({
    mutationFn: (v: { id: string; body?: Partial<HabitLog> }) => api.logHabit(v.id, v.body),
    onSuccess: refresh,
  });
}

export function useUnlogHabit() {
  const refresh = useRefreshEverything();
  return useMutation({
    mutationFn: (v: { id: string; date: string }) => api.unlogHabit(v.id, v.date),
    onSuccess: refresh,
  });
}

export function useUpdateHabit() {
  const refresh = useRefreshEverything();
  return useMutation({
    mutationFn: (v: { id: string; body: Partial<Habit> }) => api.updateHabit(v.id, v.body),
    onSuccess: refresh,
  });
}

export function useDeleteHabit() {
  const refresh = useRefreshEverything();
  return useMutation({ mutationFn: (id: string) => api.deleteHabit(id), onSuccess: refresh });
}

export function useCreateTask() {
  const refresh = useRefreshEverything();
  return useMutation({
    mutationFn: (b: Partial<Task> & { title: string }) => api.createTask(b),
    onSuccess: refresh,
  });
}

export function useCompleteTask() {
  const refresh = useRefreshEverything();
  return useMutation({ mutationFn: (id: string) => api.completeTask(id), onSuccess: refresh });
}

export function useUpdateTask() {
  const refresh = useRefreshEverything();
  return useMutation({
    mutationFn: (v: { id: string; body: Partial<Task> }) => api.updateTask(v.id, v.body),
    onSuccess: refresh,
  });
}

export function useDeleteTask() {
  const refresh = useRefreshEverything();
  return useMutation({ mutationFn: (id: string) => api.deleteTask(id), onSuccess: refresh });
}

export function useJournalRecent(limit = 30) {
  return useQuery({
    queryKey: [...keys.journal, limit],
    queryFn: () => api.journalRecent(limit),
  });
}

export function useUpsertJournal() {
  const qc = useQueryClient();
  const refresh = useRefreshEverything();
  return useMutation({
    mutationFn: (v: { date: string; body: Partial<JournalEntry> }) =>
      api.upsertJournal(v.date, v.body),
    onSuccess: () => {
      refresh();
      qc.invalidateQueries({ queryKey: keys.journal });
    },
  });
}
