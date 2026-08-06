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

export interface NotificationsResponse {
  generated_at: string;
  unread: number;
  notifications: NotificationItem[];
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
