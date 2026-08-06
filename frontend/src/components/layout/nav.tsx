import {
  BarChart3,
  BookOpen,
  CalendarCheck,
  CalendarDays,
  History,
  LayoutDashboard,
  ListTodo,
  Repeat2,
  Settings,
  Timer,
  type LucideIcon,
} from "lucide-react";

export interface NavItemDef {
  to: string;
  label: string;
  icon: LucideIcon;
  end?: boolean;
}

export const NAV: NavItemDef[] = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/plan", label: "Plan", icon: CalendarCheck },
  { to: "/habits", label: "Habits", icon: Repeat2 },
  { to: "/tasks", label: "Tasks", icon: ListTodo },
  { to: "/journal", label: "Journal", icon: BookOpen },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
  { to: "/timeline", label: "Timeline", icon: History },
  { to: "/calendar", label: "Calendar", icon: CalendarDays },
  { to: "/focus", label: "Focus", icon: Timer },
];

export const SETTINGS_NAV: NavItemDef = { to: "/settings", label: "Settings", icon: Settings };

export function titleForPath(path: string): string {
  if (path === "/") return "Dashboard";
  const seg = path.split("/")[1] ?? "";
  return seg ? seg.charAt(0).toUpperCase() + seg.slice(1) : "Atlas";
}
