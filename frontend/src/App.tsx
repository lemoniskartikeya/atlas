import { Navigate, Route, Routes } from "react-router-dom";
import { BarChart3, BookOpen, CalendarDays, ListTodo, Settings, Timer } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { ComingSoon } from "@/components/common/ComingSoon";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { HabitsPage } from "@/features/habits/HabitsPage";

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/habits" element={<HabitsPage />} />

        <Route
          path="/tasks"
          element={
            <ComingSoon
              title="Tasks"
              icon={ListTodo}
              phase="Phase 2"
              description="Projects, subtasks, dependencies, and recurring tasks. The task engine and API already run — your dashboard reads from them today; this surface is next."
            />
          }
        />
        <Route
          path="/journal"
          element={
            <ComingSoon
              title="Daily Journal"
              icon={BookOpen}
              phase="Phase 2"
              description="An auto-created page each day for mood, energy, sleep, gratitude, wins, and reflection. The journal API is already live and feeding your wellbeing card."
            />
          }
        />
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
