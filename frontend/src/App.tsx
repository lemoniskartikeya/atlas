import { Navigate, Route, Routes } from "react-router-dom";
import { CalendarDays, Settings, Timer } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { ComingSoon } from "@/components/common/ComingSoon";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { PlanPage } from "@/features/plan/PlanPage";
import { HabitsPage } from "@/features/habits/HabitsPage";
import { TasksPage } from "@/features/tasks/TasksPage";
import { JournalPage } from "@/features/journal/JournalPage";
import { AnalyticsPage } from "@/features/analytics/AnalyticsPage";
import { TimelinePage } from "@/features/timeline/TimelinePage";

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/plan" element={<PlanPage />} />
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
        <Route
          path="/focus"
          element={
            <ComingSoon
              title="Focus Mode"
              icon={Timer}
              phase="Phase 7"
              description="A minimal Pomodoro / deep-work timer with a distraction counter and fullscreen calm."
            />
          }
        />
        <Route
          path="/settings"
          element={
            <ComingSoon
              title="Settings"
              icon={Settings}
              phase="Phase 7"
              description="Themes, keyboard shortcuts, backups, import/export, ML controls, and data retention."
            />
          }
        />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  );
}
