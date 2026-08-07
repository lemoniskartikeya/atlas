import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

export function pct(n: number, digits = 0): string {
  return `${(n * 100).toFixed(digits)}%`;
}

export function clamp(n: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, n));
}

const WEEKDAY = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTH = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** Parse a YYYY-MM-DD string as a *local* date (no timezone shift). */
export function parseDate(iso: string): Date {
  const [y, m, d] = iso.split("T")[0].split("-").map(Number);
  return new Date(y, (m ?? 1) - 1, d ?? 1);
}

export function formatLongDate(iso: string): string {
  const d = parseDate(iso);
  return `${WEEKDAY[d.getDay()]}, ${MONTH[d.getMonth()]} ${d.getDate()}`;
}

export function relativeDay(iso: string): string {
  const d = parseDate(iso);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diff = Math.round((d.getTime() - today.getTime()) / 86_400_000);
  if (diff === 0) return "Today";
  if (diff === 1) return "Tomorrow";
  if (diff === -1) return "Yesterday";
  if (diff < 0) return `${-diff}d overdue`;
  return `in ${diff}d`;
}

export function todayISO(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
    d.getDate(),
  ).padStart(2, "0")}`;
}

/** Short axis label, e.g. "12 Aug". */
export function shortDate(d: Date): string {
  return `${d.getDate()} ${MONTH[d.getMonth()]}`;
}

/** Weekday + short date, e.g. "Wed 12 Aug". */
export function weekdayShortDate(d: Date): string {
  return `${WEEKDAY[d.getDay()]} ${d.getDate()} ${MONTH[d.getMonth()]}`;
}

/**
 * Label a trailing daily series that ends today, oldest first.
 * Backend trend arrays carry values only, so the dates are reconstructed here.
 */
export function trailingDayLabels(count: number, format = weekdayShortDate): string[] {
  const out: string[] = [];
  const base = new Date();
  base.setHours(0, 0, 0, 0);
  for (let i = count - 1; i >= 0; i--) {
    const d = new Date(base);
    d.setDate(base.getDate() - i);
    out.push(format(d));
  }
  return out;
}

export function initials(text: string): string {
  return text
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}
