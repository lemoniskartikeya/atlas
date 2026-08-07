import { Navigate, Route, Routes } from "react-router-dom";
import { CalendarDays } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { ComingSoon } from "@/components/common/ComingSoon";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { PlanPage } from "@/features/plan/PlanPage";
import { CoachPage } from "@/features/coach/CoachPage";
import { FocusPage } from "@/features/focus/FocusPage";
import { SettingsPage } from "@/features/settings/SettingsPage";
import { HabitsPage } from "@/features/habits/HabitsPage";
import { TasksPage } from "@/features/tasks/TasksPage";
import { JournalPage } from "@/features/journal/JournalPage";
import { AnalyticsPage } from "@/features/analytics/AnalyticsPage";
import { TimelinePage } from "@/features/timeline/TimelinePage";
import { useAuth } from "@/features/auth/AuthContext";
import { LoginScreen } from "@/features/auth/LoginScreen";

/** Blocks the app behind the account gate until the stored session resolves. */
function AppGate({ children }: { children: React.ReactNode }) {
  const { user, ready } = useAuth();

  // Render nothing (not a spinner) for the sub-second token check — a flash of
  // loading chrome before a login form reads as jank.
  if (!ready) return <div className="app-aurora min-h-screen" />;
  if (!user) return <LoginScreen />;
  return <>{children}</>;
}

export default function App() {
  return (
    <AppGate>
      <AppShell>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/plan" element={<PlanPage />} />
        <Route path="/coach" element={<CoachPage />} />
        <Route path="/habits" element={<HabitsPage />} />

        <Route path="/tasks" element={<TasksPage />} />
        <Route path="/journal" element={<JournalPage />} />
        <Route path="/analytics" element={<AnalyticsPage />} />
        <Route path="/timeline" element={<TimelinePage />} />
        <Route
          path="/calendar"
          element={
            <ComingSoon
              title="Calendar"
              icon={CalendarDays}
              phase="Phase 2"
              description="Day, week, month, and agenda views with drag-and-drop scheduling."
            />
          }
        />
        <Route path="/focus" element={<FocusPage />} />
        <Route path="/settings" element={<SettingsPage />} />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      </AppShell>
    </AppGate>
  );
}
