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
  useNotifAct,
  useNotifDismiss,
  useNotifReadAll,
  useNotifRead,
  useNotifSnooze,
  useNotifResume,
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

const ACTION_LABEL: Record<string, string> = {
  complete: "Mark done",
  defer: "Tomorrow",
};

function NotificationRow({
  n,
  onOpen,
  onDismiss,
  onAct,
  onSnooze,
  busy,
}: {
  n: NotificationItem;
  onOpen: (n: NotificationItem) => void;
  onDismiss: (id: string) => void;
  onAct: (id: string, action: string) => void;
  onSnooze: (id: string) => void;
  busy: boolean;
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

        {/* Deal with it here. A nudge that can only be read or dismissed makes
            you go and find the thing it is already telling you about. */}
        {(n.actions?.length ?? 0) > 0 && (
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {n.actions!.map((action) => (
              <button
                key={action}
                disabled={busy}
                onClick={(e) => {
                  e.stopPropagation();
                  onAct(n.id, action);
                }}
                className="rounded-full bg-ink/[0.06] px-2 py-0.5 text-[11px] font-medium text-ink transition-colors hover:bg-accent-soft hover:text-accent disabled:opacity-50"
              >
                {ACTION_LABEL[action] ?? action}
              </button>
            ))}
            <button
              disabled={busy}
              onClick={(e) => {
                e.stopPropagation();
                onSnooze(n.id);
              }}
              title="Hide until tomorrow — not held against this nudge"
              className="rounded-full px-2 py-0.5 text-[11px] text-ink-faint transition-colors hover:bg-ink/[0.06] hover:text-ink disabled:opacity-50"
            >
              Not now
            </button>
          </div>
        )}
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
  const act = useNotifAct();
  const snooze = useNotifSnooze();
  const readAll = useNotifReadAll();
  const [open, setOpen] = useState(false);
  const btnRef = useRef<HTMLButtonElement>(null);

  const items = data?.notifications ?? [];
  const snoozed = data?.snoozed ?? [];
  const unread = data?.unread ?? 0;
  const alerts = useDesktopAlerts(items);
  const resume = useNotifResume();

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
                  onAct={(id, action) => act.mutate({ id, action })}
                  onSnooze={(id) => snooze.mutate(id)}
                  busy={act.isPending || snooze.isPending}
                />
              ))
            )}

            {/* Backed-off nudges are shown rather than silently withheld — the
                user should be able to see what Atlas stopped sending, and why. */}
            {snoozed.length > 0 && (
              <div className="mt-2 border-t border-border/10 pt-2">
                <div className="px-1.5 pb-1 text-[10px] font-medium uppercase tracking-wide text-ink-faint">
                  Paused — you kept dismissing these
                </div>
                {snoozed.map((s) => (
                  <div
                    key={`${s.kind}:${s.target ?? ""}`}
                    className="flex items-start gap-2 rounded-xl px-1.5 py-1.5"
                  >
                    <BellOff size={13} className="mt-0.5 shrink-0 text-ink-faint" />
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-[13px] text-ink-muted">{s.label}</div>
                      <div className="text-[11px] text-ink-faint">{s.reason}</div>
                    </div>
                    <button
                      onClick={() => resume.mutate({ kind: s.kind, target: s.target })}
                      className="pressable shrink-0 rounded-lg px-2 py-1 text-[11px] font-medium text-accent hover:bg-accent-soft"
                    >
                      Resume
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      </AnchoredOverlay>
    </div>
  );
}
