import type {
  AnalyticsSummary,
  BackupDoc,
  BackupResult,
  CoachMessage,
  CoachResponse,
  CoachStatus,
  GoogleConfigStatus,
  GoogleResult,
  GoogleStartResponse,
  KeyTestResult,
  ObsidianSyncResult,
  ObsidianVaultCheck,
  CorrelationsResponse,
  Dashboard,
  FocusSession,
  FocusSessionCreate,
  FocusStats,
  Habit,
  HabitCreate,
  HabitLog,
  HabitStats,
  HabitWithStats,
  Heatmap,
  JournalEntry,
  MLStatus,
  NotificationsResponse,
  PlanResponse,
  PredictionReport,
  PredictionsResponse,
  SearchResponse,
  SimulationRequest,
  SimulationResponse,
  AuthResponse,
  AuthStatus,
  CalendarMonth,
  EffectivenessResponse,
  JobRunOut,
  JobsResponse,
  ModelHistory,
  CompletedTasks,
  RegisterBody,
  Task,
  TimelineResponse,
  WeeklyReview,
  TrainOutcome,
  WeeklyResponse,
} from "./types";

// Same-origin by default; the Vite dev server proxies /api -> backend.
const BASE = (import.meta.env.VITE_API_BASE ?? "") + "/api/v1";

const TOKEN_KEY = "atlas-session-token";

/** Session token lives in localStorage so a relaunch stays signed in. */
export const session = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (token: string) => localStorage.setItem(TOKEN_KEY, token),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

/** Thrown for 401s so callers can distinguish "signed out" from a real failure. */
export class UnauthorizedError extends Error {}

type ExpiryHandler = () => void;
let onExpired: ExpiryHandler | null = null;

/**
 * Register what to do when the backend rejects a token we actually sent.
 *
 * Every data endpoint requires an account, so a session that expires mid-use
 * would otherwise turn the whole app into a wall of errors. AuthProvider uses
 * this to drop the dead token and fall back to the sign-in screen.
 */
export function onSessionExpired(handler: ExpiryHandler | null): void {
  onExpired = handler;
}

async function http<T>(path: string, options?: RequestInit): Promise<T> {
  const token = session.get();
  const res = await fetch(BASE + path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : detail;
    } catch {
      /* non-JSON error body */
    }
    if (res.status === 401) {
      // Only a token that was sent and refused means "expired". A 401 with no
      // token is just an unauthenticated probe (the boot-time status check).
      if (token) onExpired?.();
      throw new UnauthorizedError(detail);
    }
    throw new Error(`${res.status} ${detail}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  /** Liveness probe — used to gate the UI while the backend boots. */
  health: () => http<{ status: string }>("/health"),

  calendar: (year: number, month: number) =>
    http<CalendarMonth>(`/calendar?year=${year}&month=${month}`),

  authStatus: () => http<AuthStatus>("/auth/status"),
  register: (body: RegisterBody) =>
    http<AuthResponse>("/auth/register", { method: "POST", body: JSON.stringify(body) }),
  login: (identifier: string, password: string) =>
    http<AuthResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ identifier, password }),
    }),
  logout: () => http<void>("/auth/logout", { method: "POST" }),
  changePassword: (current_password: string, new_password: string) =>
    http<void>("/auth/change-password", {
      method: "POST",
      body: JSON.stringify({ current_password, new_password }),
    }),

  googleStatus: () => http<GoogleConfigStatus>("/auth/google/status"),
  setGoogleConfig: (client_id: string, client_secret?: string | null) =>
    http<GoogleConfigStatus>("/auth/google/config", {
      method: "PUT",
      body: JSON.stringify({ client_id, client_secret: client_secret ?? null }),
    }),
  googleStart: () => http<GoogleStartResponse>("/auth/google/start", { method: "POST" }),
  googleResult: (state: string) =>
    http<GoogleResult>(`/auth/google/result?state=${encodeURIComponent(state)}`),

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
  completedTasks: (days = 30, limit = 200) =>
    http<CompletedTasks>(`/tasks/completed?days=${days}&limit=${limit}`),
  deleteTask: (id: string) => http<void>(`/tasks/${id}`, { method: "DELETE" }),

  heatmap: (days = 365) => http<Heatmap>(`/analytics/heatmap?days=${days}`),
  analyticsSummary: () => http<AnalyticsSummary>("/analytics/summary"),
  analyticsWeekly: (weeks = 12) => http<WeeklyResponse>(`/analytics/weekly?weeks=${weeks}`),
  analyticsCorrelations: (days = 90) =>
    http<CorrelationsResponse>(`/analytics/correlations?days=${days}`),

  mlStatus: () => http<MLStatus>("/ml/status"),
  mlPredictions: () => http<PredictionsResponse>("/ml/predictions"),
  trainModel: () => http<TrainOutcome>("/ml/train", { method: "POST" }),

  plan: () => http<PlanResponse>("/planner/today"),
  predictions: () => http<PredictionReport>("/predictions"),

  notifications: () => http<NotificationsResponse>("/notifications"),
  notifRead: (id: string) =>
    http<void>("/notifications/read", { method: "POST", body: JSON.stringify({ id }) }),
  notifDismiss: (id: string) =>
    http<void>("/notifications/dismiss", { method: "POST", body: JSON.stringify({ id }) }),
  notifReadAll: () => http<void>("/notifications/read-all", { method: "POST" }),
  notifResume: (kind: string, target?: string | null) =>
    http<void>("/notifications/resume", {
      method: "POST",
      body: JSON.stringify({ kind, target: target ?? null }),
    }),

  jobs: () => http<JobsResponse>("/jobs"),
  runJob: (id: string) => http<JobRunOut>(`/jobs/${id}/run`, { method: "POST" }),
  modelHistory: () => http<ModelHistory>("/ml/history"),
  effectiveness: () => http<EffectivenessResponse>("/feedback/effectiveness"),

  simulate: (body: SimulationRequest) =>
    http<SimulationResponse>("/simulator", { method: "POST", body: JSON.stringify(body) }),

  review: (offset = 0) => http<WeeklyReview>(`/review?offset=${offset}`),

  exportBackup: () => http<BackupDoc>("/backup/export"),
  importBackup: (doc: BackupDoc) =>
    http<BackupResult>("/backup/import", { method: "POST", body: JSON.stringify(doc) }),

  focusStats: () => http<FocusStats>("/focus/stats"),
  focusRecent: (limit = 10) => http<FocusSession[]>(`/focus/sessions?limit=${limit}`),
  createFocus: (body: FocusSessionCreate) =>
    http<FocusSession>("/focus/sessions", { method: "POST", body: JSON.stringify(body) }),

  coachStatus: () => http<CoachStatus>("/coach/status"),
  setCoachProvider: (provider: string, model?: string | null) =>
    http<CoachStatus>("/coach/provider", {
      method: "PUT",
      body: JSON.stringify({ provider, model: model ?? null }),
    }),
  setCoachKey: (api_key: string, provider?: string) =>
    http<CoachStatus>("/coach/key", {
      method: "PUT",
      body: JSON.stringify({ api_key, provider: provider ?? null }),
    }),
  clearCoachKey: (provider?: string) =>
    http<CoachStatus>(
      provider ? `/coach/key?provider=${encodeURIComponent(provider)}` : "/coach/key",
      { method: "DELETE" },
    ),
  testCoachKey: () => http<KeyTestResult>("/coach/key/test", { method: "POST" }),
  coachAsk: (messages: CoachMessage[], useAi: boolean) =>
    http<CoachResponse>("/coach/ask", {
      method: "POST",
      body: JSON.stringify({ messages, use_ai: useAi }),
    }),

  checkObsidianVault: (vault_path: string) =>
    http<ObsidianVaultCheck>("/obsidian/check", {
      method: "POST",
      body: JSON.stringify({ vault_path }),
    }),
  syncObsidian: (vault_path: string) =>
    http<ObsidianSyncResult>("/obsidian/sync", {
      method: "POST",
      body: JSON.stringify({ vault_path }),
    }),

  search: (q: string, limit = 8) =>
    http<SearchResponse>(`/search?q=${encodeURIComponent(q)}&limit=${limit}`),

  timeline: (params: { limit?: number; offset?: number; kinds?: string } = {}) => {
    const q = new URLSearchParams();
    if (params.limit != null) q.set("limit", String(params.limit));
    if (params.offset != null) q.set("offset", String(params.offset));
    if (params.kinds) q.set("kinds", params.kinds);
    return http<TimelineResponse>(`/timeline?${q.toString()}`);
  },

  journalRecent: (limit = 14) => http<JournalEntry[]>(`/journal?limit=${limit}`),
  journal: (date: string) => http<JournalEntry>(`/journal/${date}`),
  upsertJournal: (date: string, body: Partial<JournalEntry>) =>
    http<JournalEntry>(`/journal/${date}`, { method: "PUT", body: JSON.stringify(body) }),
};
