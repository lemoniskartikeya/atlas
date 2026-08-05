import { Navigate, Route, Routes } from "react-router-dom";
import { BarChart3, CalendarDays, Settings, Timer } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { ComingSoon } from "@/components/common/ComingSoon";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { HabitsPage } from "@/features/habits/HabitsPage";
import { TasksPage } from "@/features/tasks/TasksPage";
import { JournalPage } from "@/features/journal/JournalPage";

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/habits" element={<HabitsPage />} />

        <Route path="/tasks" element={<TasksPage />} />
        <Route path="/journal" element={<JournalPage />} />
        <Route
          path="/analytics"
          element={
            <ComingSoon
              title="Analytics"
              icon={BarChart3}
              phase="Phase 3"
              description="Correlations (sleep vs. focus, mood vs. productivity), monthly reports, and personal bests — built on the same history that powers your consistency heatmap."
            />
          }
        />
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
