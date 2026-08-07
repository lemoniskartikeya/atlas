import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  Bell,
  BellOff,
  BellRing,
  CheckCheck,
  Flame,
  HeartPulse,
  ListChecks,
  Moon,
  Sunrise,
  X,
  type LucideIcon,
} from "lucide-react";
import {
  useNotifDismiss,
  useNotifReadAll,
  useNotifRead,
  useNotifications,
} from "@/hooks/queries";
import { AnchoredOverlay } from "@/components/ui/anchored-overlay";
import { cn } from "@/lib/utils";
import type { NotificationItem } from "@/lib/types";
import { isDesktop, notify, requestNotificationPermission } from "@/lib/desktop";

const KIND_ICON: Record<string, LucideIcon> = {
  brief: Sunrise,
  risk: AlertTriangle,
  streak: Flame,
  task: ListChecks,
  wellbeing: HeartPulse,
  eod: Moon,
};

const PRIORITY_COLOR: Record<NotificationItem["priority"], string> = {
  high: "#d0605e",
  medium: "rgb(var(--accent))",
  low: "rgb(var(--ink-faint))",
};

/**
 * Optional desktop alerts for new high-priority notifications (opt-in).
 *
 * On the desktop build these are real OS notifications, so they arrive even
 * when Atlas is parked in the tray. In a browser it's the Web Notifications
 * API — `notify()` picks the right one.
 */
function useDesktopAlerts(items: NotificationItem[]) {
  const supported =
    isDesktop() || (typeof window !== "undefined" && "Notification" in window);
  const [enabled, setEnabled] = useState(
    () => supported && localStorage.getItem("atlas-desktop-alerts") === "on",
  );
  const seen = useRef<Set<string>>(new Set());

  // Seed "seen" with whatever is already on screen so enabling doesn't blast a backlog.
  useEffect(() => {
    if (enabled) items.forEach((n) => seen.current.add(n.id));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled]);

  useEffect(() => {
    if (!enabled || !supported) return;
    for (const n of items) {
      if (n.read || n.priority !== "high" || seen.current.has(n.id)) continue;
      seen.current.add(n.id);
      void notify(n.title, n.body);
    }
    items.forEach((n) => seen.current.add(n.id));
  }, [items, enabled, supported]);

  const toggle = async () => {
    if (!supported) return;
    if (enabled) {
      setEnabled(false);
      localStorage.setItem("atlas-desktop-alerts", "off");
      return;
    }
    if (await requestNotificationPermission()) {
      items.forEach((n) => seen.current.add(n.id));
      setEnabled(true);
      localStorage.setItem("atlas-desktop-alerts", "on");
    }
  };

  return { supported, enabled, toggle };
}

function NotificationRow({
  n,
  onOpen,
  onDismiss,
}: {
  n: NotificationItem;
  onOpen: (n: NotificationItem) => void;
  onDismiss: (id: string) => void;
}) {
  const Icon = KIND_ICON[n.kind] ?? Bell;
  return (
    <div
      className={cn(
        "group relative flex gap-3 rounded-xl p-2.5 transition-colors",
        n.action_route ? "cursor-pointer hover:bg-ink/5" : "",
        !n.read && "bg-accent-soft/40",
      )}
      onClick={() => onOpen(n)}
    >
      <div
        className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg"
        style={{ backgroundColor: `${PRIORITY_COLOR[n.priority]}1f`, color: PRIORITY_COLOR[n.priority] }}
      >
        <Icon size={14} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          {!n.read && (
            <span
              className="h-1.5 w-1.5 shrink-0 rounded-full"
              style={{ backgroundColor: PRIORITY_COLOR[n.priority] }}
            />
          )}
          <span className="min-w-0 flex-1 truncate text-[13px] font-medium text-ink">
            {n.title}
          </span>
        </div>
        <p className="mt-0.5 text-[12px] leading-relaxed text-ink-muted">{n.body}</p>
        <p className="mt-0.5 text-[11px] leading-relaxed text-ink-faint">{n.reason}</p>
      </div>
      <button
        onClick={(e) => {
          e.stopPropagation();
          onDismiss(n.id);
        }}
        aria-label="Dismiss"
        className="absolute right-1.5 top-1.5 grid h-5 w-5 place-items-center rounded-md text-ink-faint opacity-0 transition-opacity hover:bg-ink/10 hover:text-ink group-hover:opacity-100"
      >
        <X size={12} />
      </button>
    </div>
  );
}

export function NotificationCenter() {
  const navigate = useNavigate();
  const { data } = useNotifications();
  const read = useNotifRead();
  const dismiss = useNotifDismiss();
  const readAll = useNotifReadAll();
  const [open, setOpen] = useState(false);
  const btnRef = useRef<HTMLButtonElement>(null);

  const items = data?.notifications ?? [];
  const unread = data?.unread ?? 0;
  const alerts = useDesktopAlerts(items);

  // Dismissal (outside click, Escape) is handled by AnchoredOverlay's scrim.

  const openItem = (n: NotificationItem) => {
    if (!n.read) read.mutate(n.id);
    if (n.action_route) {
      navigate(n.action_route);
      setOpen(false);
    }
  };

  return (
    <div className="relative">
      <button
        ref={btnRef}
        onClick={() => setOpen((v) => !v)}
        aria-label="Notifications"
        aria-expanded={open}
        className="glass pressable relative grid h-9 w-9 place-items-center rounded-xl text-ink-muted hover:text-ink"
      >
        <Bell size={16} />
        {unread > 0 && (
          <span className="absolute -right-1 -top-1 grid h-4 min-w-4 place-items-center rounded-full bg-accent px-1 text-[10px] font-semibold text-white">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>

      <AnchoredOverlay open={open} onClose={() => setOpen(false)} anchorRef={btnRef} width={360}>
        <>
          <div className="flex shrink-0 items-center justify-between border-b border-border/10 px-3 py-2.5">
              <div className="flex items-center gap-2 text-sm font-semibold text-ink">
                Notifications
                {unread > 0 && (
                  <span className="rounded-full bg-accent-soft px-1.5 py-0.5 text-[10px] font-semibold text-accent">
                    {unread} new
                  </span>
                )}
              </div>
              <div className="flex items-center gap-1">
                {alerts.supported && (
                  <button
                    onClick={alerts.toggle}
                    title={alerts.enabled ? "Desktop alerts on" : "Enable desktop alerts"}
                    aria-label="Toggle desktop alerts"
                    className={cn(
                      "grid h-7 w-7 place-items-center rounded-lg transition-colors hover:bg-ink/5",
                      alerts.enabled ? "text-accent" : "text-ink-faint",
                    )}
                  >
                    {alerts.enabled ? <BellRing size={14} /> : <BellOff size={14} />}
                  </button>
                )}
                {unread > 0 && (
                  <button
                    onClick={() => readAll.mutate()}
                    title="Mark all read"
                    aria-label="Mark all read"
                    className="grid h-7 w-7 place-items-center rounded-lg text-ink-faint transition-colors hover:bg-ink/5 hover:text-ink"
                  >
                    <CheckCheck size={15} />
                  </button>
                )}
              </div>
            </div>

          <div className="min-h-0 flex-1 space-y-1 overflow-y-auto p-2">
            {items.length === 0 ? (
              <div className="flex flex-col items-center gap-2 px-3 py-10 text-center">
                <BellOff size={20} className="text-ink-faint" />
                <p className="text-[13px] text-ink-muted">You're all caught up.</p>
              </div>
            ) : (
              items.map((n) => (
                <NotificationRow
                  key={n.id}
                  n={n}
                  onOpen={openItem}
                  onDismiss={(id) => dismiss.mutate(id)}
                />
              ))
            )}
          </div>
        </>
      </AnchoredOverlay>
    </div>
  );
}
