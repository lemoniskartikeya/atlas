// TypeScript mirrors of the backend Pydantic schemas.

export type Frequency = "daily" | "weekly" | "monthly" | "custom";
export type Priority = "low" | "medium" | "high" | "critical";
export type TimeOfDay = "morning" | "afternoon" | "evening" | "night" | "any";
export type Difficulty = "trivial" | "easy" | "medium" | "hard";
export type HabitLogStatus = "completed" | "partial" | "skipped";
export type TaskStatus = "backlog" | "todo" | "in_progress" | "done" | "cancelled";

export interface Habit {
  id: string;
  title: string;
  description?: string | null;
  category?: string | null;
  frequency: Frequency;
  custom_days?: number[] | null;
  target_per_period: number;
  priority: Priority;
  estimated_duration_min?: number | null;
  difficulty: Difficulty;
  motivation_level: number;
  required_energy: number;
  location?: string | null;
  time_preference: TimeOfDay;
  color?: string | null;
  archived: boolean;
  created_at: string;
  updated_at: string;
}

export interface HabitStats {
  habit_id: string;
  current_streak: number;
  longest_streak: number;
  total_completions: number;
  success_rate: number;
  consistency_30d: number;
  best_weekday?: string | null;
  worst_weekday?: string | null;
  most_productive_hour?: number | null;
  average_duration_min?: number | null;
  last_completed?: string | null;
}

export interface HabitWithStats extends Habit {
  stats: HabitStats;
}

export interface HabitCreate {
  title: string;
  description?: string | null;
  category?: string | null;
  frequency?: Frequency;
  custom_days?: number[] | null;
  target_per_period?: number;
  priority?: Priority;
  estimated_duration_min?: number | null;
  difficulty?: Difficulty;
  motivation_level?: number;
  required_energy?: number;
  location?: string | null;
  time_preference?: TimeOfDay;
  color?: string | null;
}

export interface HabitLog {
  id: string;
  habit_id: string;
  date: string;
  status: HabitLogStatus;
  partial_amount?: number | null;
  reason?: string | null;
  mood_after?: number | null;
  energy_before?: number | null;
  energy_after?: number | null;
  duration_min?: number | null;
  note?: string | null;
  logged_at: string;
}

export interface Task {
  id: string;
  title: string;
  description?: string | null;
  project_id?: string | null;
  parent_id?: string | null;
  status: TaskStatus;
  priority: Priority;
  tags?: string[] | null;
  labels?: string[] | null;
  estimated_effort_min?: number | null;
  actual_effort_min?: number | null;
  due_date?: string | null;
  deadline?: string | null;
  scheduled_for?: string | null;
  context?: string | null;
  energy_required: number;
  focus_required: number;
  location?: string | null;
  completed_at?: string | null;
  created_at: string;
  updated_at: string;
}

/* ------------------------------------------------------------------- learning */

export interface JobRunOut {
  job_id: string;
  started_at: string;
  finished_at?: string | null;
  status: "ok" | "skipped" | "error";
  detail?: string | null;
  duration_ms?: number | null;
}

export interface JobOut {
  id: string;
  label: string;
  description: string;
  interval_hours: number;
  last_run?: JobRunOut | null;
  next_due?: string | null;
  due_now: boolean;
}

export interface JobsResponse {
  enabled: boolean;
  jobs: JobOut[];
  recent: JobRunOut[];
}

export interface ModelVersion {
  version: string;
  trained_at?: string | null;
  model_type?: string | null;
  roc_auc?: number | null;
  /** Range across the rolling-origin folds — the width of the estimate. */
  roc_auc_min?: number | null;
  roc_auc_max?: number | null;
  accuracy?: number | null;
  n_samples?: number | null;
  n_rows?: number | null;
  n_test?: number | null;
  /** Smallest minority-class count across folds — the real limit on trust. */
  n_test_neg_min?: number | null;
  eval?: string | null;
  eval_note?: string | null;
}

export interface ModelHistory {
  versions: ModelVersion[];
  /** How much the score moves between folds of the *same* model. */
  noise_floor?: number | null;
  /** False when the change is smaller than that — i.e. it means nothing. */
  delta_is_meaningful?: boolean | null;
  total: number;
  latest_roc_auc?: number | null;
  best_roc_auc?: number | null;
  delta_vs_previous?: number | null;
}

export interface FamilyEffectiveness {
  family: string;
  label: string;
  shown: number;
  followed: number;
  rate: number;
  weight?: number | null;
  influencing: boolean;
}

export interface EffectivenessResponse {
  families: FamilyEffectiveness[];
  total_resolved: number;
  min_samples: number;
}

/* ------------------------------------------------------------------- calendar */

export interface CalendarHabit {
  id: string;
  title: string;
  color?: string | null;
  status: "completed" | "partial" | "skipped" | "due";
}

export interface CalendarTask {
  id: string;
  title: string;
  priority: Priority;
  status: TaskStatus;
  completed_here: boolean;
}

export interface CalendarDay {
  date: string;
  in_month: boolean;
  is_today: boolean;
  is_future: boolean;
  habits: CalendarHabit[];
  tasks: CalendarTask[];
  habits_done: number;
  habits_due: number;
  tasks_due: number;
  tasks_completed: number;
  mood?: number | null;
  energy?: number | null;
  sleep_hours?: number | null;
  has_journal: boolean;
  focus_minutes: number;
  focus_sessions: number;
  intensity: number;
}

export interface CalendarMonth {
  year: number;
  month: number;
  label: string;
  days: CalendarDay[];
  total_habits_done: number;
  total_tasks_completed: number;
  total_focus_minutes: number;
  journal_days: number;
  perfect_days: number;
}

/* ------------------------------------------------------------------- accounts */

export interface AtlasUser {
  id: string;
  username: string;
  email?: string | null;
  display_name?: string | null;
  last_login_at?: string | null;
  created_at: string;
}

export interface PasswordPolicy {
  min_length: number;
  requires_number: boolean;
  requires_special: boolean;
  requires_letter: boolean;
  description: string;
}

export interface AuthStatus {
  has_accounts: boolean;
  authenticated: boolean;
  user?: AtlasUser | null;
  policy: PasswordPolicy;
}

export interface AuthResponse {
  token: string;
  user: AtlasUser;
}

export interface RegisterBody {
  username: string;
  password: string;
  email?: string | null;
  display_name?: string | null;
}

export interface CompletionStats {
  today: number;
  this_week: number;
  window: number;
  all_time: number;
  window_days: number;
  per_day: { date: string; count: number }[];
}

export interface CompletedTasks {
  stats: CompletionStats;
  tasks: Task[];
}

export interface JournalEntry {
  id: string;
  date: string;
  mood?: number | null;
  energy?: number | null;
  sleep_hours?: number | null;
  gratitude?: string | null;
  wins?: string | null;
  challenges?: string | null;
  free_writing?: string | null;
  reflection?: string | null;
  lessons?: string | null;
  created_at: string;
  updated_at: string;
}

export interface Recommendation {
  id: string;
  kind: string;
  title: string;
  detail: string;
  confidence: number;
  reason: string;
}

export interface HabitTodayItem {
  id: string;
  title: string;
  category?: string | null;
  color?: string | null;
  time_preference: TimeOfDay;
  priority: Priority;
  estimated_duration_min?: number | null;
  current_streak: number;
  status_today?: HabitLogStatus | null;
  done_today: boolean;
}

export interface StreakItem {
  habit_id: string;
  title: string;
  current_streak: number;
  longest_streak: number;
}

export interface Dashboard {
  date: string;
  greeting: string;
  habits_today: HabitTodayItem[];
  habits_completed: number;
  habits_total: number;
  tasks_today: Task[];
  tasks_open: number;
  suggested_task?: Task | null;
  top_streaks: StreakItem[];
  weekly_consistency: number;
  life_score: number;
  life_score_trend: number[];
  focus_score?: number | null;
  mood?: number | null;
  energy?: number | null;
  sleep_hours?: number | null;
  recent_journal?: JournalEntry | null;
  recommendations: Recommendation[];
  recommendations_model_backed: boolean;
}

export interface HeatmapCell {
  date: string;
  count: number;
  level: number;
}

export interface Heatmap {
  start: string;
  end: string;
  total: number;
  max_count: number;
  cells: HeatmapCell[];
}

export interface CategoryCount {
  category: string;
  count: number;
}

export interface TopHabit {
  id: string;
  title: string;
  current_streak: number;
  longest_streak: number;
  success_rate: number;
  consistency_30d: number;
  total_completions: number;
}

export interface AnalyticsSummary {
  total_completions: number;
  active_habits: number;
  journal_entries: number;
  tasks_completed: number;
  tasks_open: number;
  best_current_streak: number;
  longest_streak_ever: number;
  avg_mood: number | null;
  avg_energy: number | null;
  avg_sleep: number | null;
  deep_work_hours: number;
  by_weekday: number[];
  by_category: CategoryCount[];
  top_habits: TopHabit[];
}

export interface WeeklyPoint {
  week_start: string;
  label: string;
  completions: number;
  rate: number;
}

export interface WeeklyResponse {
  weeks: WeeklyPoint[];
}

export interface CorrelationPoint {
  date: string;
  x: number;
  y: number;
}

export interface CorrelationPair {
  key: string;
  x_label: string;
  y_label: string;
  coefficient: number | null;
  n: number;
  interpretation: string;
  points: CorrelationPoint[];
}

export interface CorrelationsResponse {
  pairs: CorrelationPair[];
}

export interface Insight {
  key: string;
  text: string;
  /** The arithmetic behind the sentence — always present. */
  evidence: string;
  tone: "good" | "watch" | "neutral";
}

export interface InsightsResponse {
  generated_for: string;
  days: number;
  /** Empty until there is enough history to say something true. */
  insights: Insight[];
}

export interface MLMetrics {
  accuracy?: number | null;
  roc_auc?: number | null;
  brier?: number | null;
  n_train?: number | null;
  n_test?: number | null;
  positive_rate?: number | null;
}

export interface MLStatus {
  trained: boolean;
  version?: string | null;
  trained_at?: string | null;
  model_type?: string | null;
  metrics?: MLMetrics | null;
}

export interface TrainOutcome {
  trained: boolean;
  version?: string | null;
  metrics?: MLMetrics | null;
  n_samples?: number | null;
  reason?: string | null;
}

export interface HabitPrediction {
  habit_id: string;
  title: string;
  color?: string | null;
  probability: number;
  done_today: boolean;
  explanation: string;
}

export interface PredictionsResponse {
  trained: boolean;
  version?: string | null;
  model_type?: string | null;
  reliability?: number | null;
  metrics?: MLMetrics | null;
  predictions: HabitPrediction[];
}

export interface PlanItem {
  id: string;
  kind: "habit" | "task";
  title: string;
  color?: string | null;
  duration_min?: number | null;
  priority?: string | null;
  done: boolean;
  probability?: number | null;
  risk?: "at-risk" | "steady" | null;
  reason: string;
  confidence: number;
}

export interface PlanBlock {
  key: string;
  label: string;
  window: string;
  is_now: boolean;
  minutes: number;
  items: PlanItem[];
}

export interface PlanResponse {
  date: string;
  generated_at: string;
  now_hour: number;
  now_block: string;
  model_backed: boolean;
  reliability?: number | null;
  summary: string;
  open_count: number;
  total_minutes: number;
  blocks: PlanBlock[];
}

export interface ExpectedCompletion {
  due: number;
  done: number;
  remaining: number;
  expected_total: number;
  expected_rate: number;
  confidence?: number | null;
  model_backed: boolean;
  reason: string;
}

export interface StreakRisk {
  habit_id: string;
  title: string;
  current_streak: number;
  probability?: number | null;
  risk: number;
  level: "high" | "medium";
  reason: string;
}

export interface BurnoutSignal {
  score: number;
  level: "low" | "moderate" | "elevated";
  drivers: string[];
  reason: string;
}

export interface PredictionReport {
  date: string;
  model_backed: boolean;
  reliability?: number | null;
  expected_completion: ExpectedCompletion;
  streak_risks: StreakRisk[];
  burnout: BurnoutSignal;
}

export interface NotificationItem {
  id: string;
  kind: string; // "brief" | "risk" | "streak" | "task" | "wellbeing" | "eod"
  priority: "high" | "medium" | "low";
  title: string;
  body: string;
  reason: string;
  action_label?: string | null;
  action_route?: string | null;
  read: boolean;
}

export interface SnoozedStream {
  kind: string;
  target?: string | null;
  label: string;
  dismissals: number;
  until: string;
  reason: string;
}

export interface NotificationsResponse {
  generated_at: string;
  unread: number;
  notifications: NotificationItem[];
  /** Nudges Atlas has paused because they kept being dismissed. */
  snoozed: SnoozedStream[];
}

export interface SimulationRequest {
  sleep_prev?: number | null;
  energy_prev?: number | null;
  mood_prev?: number | null;
  min_rate?: number | null;
  streak_in?: number | null;
  time_of_day?: TimeOfDay | null;
  habit_id?: string | null;
  drop_habit_ids?: string[];
}

export interface SimHabitRow {
  habit_id: string;
  title: string;
  color?: string | null;
  done_today: boolean;
  baseline: number;
  simulated: number;
  delta: number;
}

export interface SimulationResponse {
  available: boolean;
  reliability?: number | null;
  due: number;
  baseline_expected: number;
  simulated_expected: number;
  delta_expected: number;
  levers: string[];
  summary: string;
  rows: SimHabitRow[];
}

export interface ReviewMetric {
  key: string;
  label: string;
  value: string;
  delta?: number | null;
  direction?: "up" | "down" | "flat" | null;
  hint?: string | null;
}

export interface ReviewItem {
  title: string;
  detail: string;
  habit_id?: string | null;
}

export interface TimelineEvent {
  id: string;
  kind: "habit" | "streak" | "task" | "journal" | "habit_created";
  timestamp: string;
  date: string;
  title: string;
  detail?: string | null;
  status?: string | null;
  color?: string | null;
  route?: string | null;
}

export interface TimelineResponse {
  events: TimelineEvent[];
  offset: number;
  limit: number;
  total: number;
  has_more: boolean;
}

export interface SearchResult {
  type: "habit" | "task" | "journal" | "note" | "log";
  id: string;
  title: string;
  snippet?: string | null;
  date?: string | null;
  status?: string | null;
  route?: string | null;
  score: number;
}

export interface SearchResponse {
  query: string;
  interpretation: string;
  total: number;
  results: SearchResult[];
}

export interface CoachProviderOption {
  id: string;
  label: string;
  default_model: string;
  /** Where to get a key. Atlas cannot obtain one on the user's behalf. */
  key_url?: string | null;
  /** Honest one-liner about cost, shown next to the choice. */
  cost_note: string;
  /** A model running on this machine: no key, nothing leaves the device. */
  local: boolean;
  needs_key: boolean;
  suggested_models: string[];
  /** Local providers only: models actually pulled on this machine. */
  installed_models?: string[] | null;
  available?: boolean | null;
}

export interface CoachStatus {
  ai_available: boolean;
  provider?: string | null;
  provider_label?: string | null;
  model?: string | null;
  local_provider: boolean;
  needs_key: boolean;
  sdk_installed: boolean;
  has_key: boolean;
  /** Masked hint only — the full key is never returned by the API. */
  key_hint?: string | null;
  providers: CoachProviderOption[];
}

export interface KeyTestResult {
  ok: boolean;
  detail: string;
}

export interface CoachMessage {
  role: "user" | "assistant";
  content: string;
}

export interface CoachResponse {
  reply: string;
  mode: "ai" | "local";
  model?: string | null;
  grounded_on?: string | null;
}

export interface FocusSession {
  id: string;
  started_at: string;
  duration_min: number;
  distractions: number;
  note?: string | null;
  task_id?: string | null;
  created_at: string;
}

export interface FocusSessionCreate {
  duration_min: number;
  distractions?: number;
  note?: string | null;
  task_id?: string | null;
  started_at?: string | null;
}

export interface FocusStats {
  sessions_today: number;
  minutes_today: number;
  sessions_week: number;
  minutes_week: number;
  avg_distractions?: number | null;
  best_day_minutes: number;
}

export interface BackupDoc {
  atlas_backup: boolean;
  version: number;
  exported_at?: string;
  data: Record<string, unknown[]>;
}

export interface BackupResult {
  imported: Record<string, number>;
  total: number;
}

export interface WeeklyReview {
  start: string;
  end: string;
  label: string;
  offset: number;
  is_current: boolean;
  can_go_forward: boolean;
  completion_rate: number;
  prev_completion_rate?: number | null;
  completions: number;
  due: number;
  tasks_completed: number;
  metrics: ReviewMetric[];
  wins: ReviewItem[];
  watchouts: ReviewItem[];
  focus: string[];
  narrative: string;
}

export interface ObsidianVaultCheck {
  exists: boolean;
  is_vault: boolean;
  detail: string;
}

export interface ObsidianSyncResult {
  exported: number;
  imported: number;
  updated_in_atlas: number;
  /** Left alone because the vault's copy was newer. */
  skipped: number;
  /** Human-readable notes about anything that changed in both places. */
  conflicts: string[];
  vault_path: string;
}

export interface GoogleConfigStatus {
  configured: boolean;
  /** Must be registered verbatim in the Google Cloud console. */
  redirect_uri: string;
  client_id_hint?: string | null;
}

export interface GoogleStartResponse {
  authorize_url: string;
  state: string;
}

export interface GoogleResult {
  status: "pending" | "ready" | "error";
  detail?: string | null;
  token?: string | null;
  username?: string | null;
}

/* ------------------------------------------------------------- email sign-in */

export type OtpPurpose = "login" | "signup";

export interface EmailStatus {
  /** False when no mail provider is configured on the backend. */
  email_configured: boolean;
}

export interface SendOtpResponse {
  email: string;
  purpose: OtpPurpose;
  detail: string;
  expires_in_seconds: number;
  resend_in_seconds: number;
  /** Development only; the backend returns this nowhere else. */
  dev_code?: string | null;
}
