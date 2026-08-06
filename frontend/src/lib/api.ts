import type {
  AnalyticsSummary,
  CorrelationsResponse,
  Dashboard,
  Habit,
  HabitCreate,
  HabitLog,
  HabitStats,
  HabitWithStats,
  Heatmap,
  JournalEntry,
  MLStatus,
  PredictionsResponse,
  Task,
  TrainOutcome,
  WeeklyResponse,
} from "./types";

// Same-origin by default; the Vite dev server proxies /api -> backend.
const BASE = (import.meta.env.VITE_API_BASE ?? "") + "/api/v1";

async function http<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(`${res.status} ${detail}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  dashboard: () => http<Dashboard>("/dashboard"),

  habits: (includeArchived = false) =>
    http<Habit[]>(`/habits?include_archived=${includeArchived}`),
  habit: (id: string) => http<HabitWithStats>(`/habits/${id}`),
  createHabit: (body: HabitCreate) =>
    http<Habit>("/habits", { method: "POST", body: JSON.stringify(body) }),
  updateHabit: (id: string, body: Partial<Habit>) =>
    http<Habit>(`/habits/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteHabit: (id: string) => http<void>(`/habits/${id}`, { method: "DELETE" }),
  habitStats: (id: string) => http<HabitStats>(`/habits/${id}/stats`),

  logHabit: (id: string, body: Partial<HabitLog> = {}) =>
    http<HabitLog>(`/habits/${id}/logs`, { method: "POST", body: JSON.stringify(body) }),
  unlogHabit: (id: string, date: string) =>
    http<void>(`/habits/${id}/logs/${date}`, { method: "DELETE" }),

  tasks: (scope: "all" | "today" | "upcoming" | "open" = "all") =>
    http<Task[]>(`/tasks?scope=${scope}`),
  createTask: (body: Partial<Task> & { title: string }) =>
    http<Task>("/tasks", { method: "POST", body: JSON.stringify(body) }),
  updateTask: (id: string, body: Partial<Task>) =>
    http<Task>(`/tasks/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  completeTask: (id: string) => http<Task>(`/tasks/${id}/complete`, { method: "POST" }),
  deleteTask: (id: string) => http<void>(`/tasks/${id}`, { method: "DELETE" }),

  heatmap: (days = 365) => http<Heatmap>(`/analytics/heatmap?days=${days}`),
  analyticsSummary: () => http<AnalyticsSummary>("/analytics/summary"),
  analyticsWeekly: (weeks = 12) => http<WeeklyResponse>(`/analytics/weekly?weeks=${weeks}`),
  analyticsCorrelations: (days = 90) =>
    http<CorrelationsResponse>(`/analytics/correlations?days=${days}`),

  mlStatus: () => http<MLStatus>("/ml/status"),
  mlPredictions: () => http<PredictionsResponse>("/ml/predictions"),
  trainModel: () => http<TrainOutcome>("/ml/train", { method: "POST" }),

  journalRecent: (limit = 14) => http<JournalEntry[]>(`/journal?limit=${limit}`),
  journal: (date: string) => http<JournalEntry>(`/journal/${date}`),
  upsertJournal: (date: string, body: Partial<JournalEntry>) =>
    http<JournalEntry>(`/journal/${date}`, { method: "PUT", body: JSON.stringify(body) }),
};
