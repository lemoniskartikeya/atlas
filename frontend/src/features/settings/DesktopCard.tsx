import { useEffect, useState } from "react";
import { AlertTriangle, Loader2, Monitor, Power } from "lucide-react";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { autostart, isDesktop } from "@/lib/desktop";
import { cn } from "@/lib/utils";

function Toggle({
  checked,
  onChange,
  label,
  busy,
  disabled,
}: {
  checked: boolean;
  onChange: () => void;
  label: string;
  busy?: boolean;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={onChange}
      disabled={disabled}
      className={cn(
        "pressable relative h-6 w-11 shrink-0 rounded-full transition-colors",
        checked ? "bg-accent" : "bg-ink/15",
        disabled && "cursor-not-allowed opacity-50",
      )}
    >
      <span
        className={cn(
          "absolute top-0.5 grid h-5 w-5 place-items-center rounded-full bg-white shadow-sm transition-transform duration-200 ease-out-soft",
          checked ? "translate-x-[22px]" : "translate-x-0.5",
        )}
      >
        {busy && <Loader2 size={11} className="animate-spin text-accent" />}
      </span>
    </button>
  );
}

/** Desktop-only preferences. Hidden entirely when Atlas runs in a browser. */
export function DesktopCard() {
  const [launchOnStartup, setLaunchOnStartup] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Read the real OS state on mount. A rejection here used to leave the switch
  // stuck at "off" with nothing to explain why.
  useEffect(() => {
    if (!isDesktop()) return;
    autostart
      .isEnabled()
      .then(setLaunchOnStartup)
      .catch((e) => setError(`Couldn't read the startup setting: ${String(e)}`));
  }, []);

  if (!isDesktop()) return null;

  const toggleStartup = async () => {
    if (busy) return;
    setBusy(true);
    setError(null);

    const next = !launchOnStartup;
    // Optimistic, so the switch responds to the click immediately.
    setLaunchOnStartup(next);

    try {
      await autostart.set(next);
      // Trust the OS, not our intent: read back what actually got registered,
      // so a silent no-op can't masquerade as success.
      const actual = await autostart.isEnabled();
      setLaunchOnStartup(actual);
      if (actual !== next) {
        // Windows keeps a separate "Startup Apps" override next to the Run key.
        // If Atlas has been switched off there, the entry is written and then
        // reported back as disabled — which is exactly what a silent no-op
        // looks like. Name the actual place to fix it.
        setError(
          next
            ? "Windows registered Atlas but is still reporting it as off. Open Task Manager → Startup apps and make sure Atlas is enabled there."
            : "The startup entry couldn't be removed. Try disabling Atlas in Task Manager → Startup apps.",
        );
      }
    } catch (e) {
      setLaunchOnStartup(!next); // roll the optimistic update back
      setError(String((e as Error)?.message ?? e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Desktop</CardTitle>
        <Monitor size={15} className="text-accent" />
      </CardHeader>
      <CardBody className="space-y-3">
        <div className="flex items-center justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-1.5 text-sm text-ink">
              <Power size={13} className="text-ink-faint" /> Launch at login
            </div>
            <div className="text-[12px] text-ink-muted">
              Start Atlas in the tray when you sign in to this computer.
            </div>
          </div>
          <Toggle
            checked={launchOnStartup}
            onChange={toggleStartup}
            busy={busy}
            label="Launch Atlas at login"
          />
        </div>

        {error && (
          <div className="bg-danger-soft flex items-start gap-2 rounded-xl px-3 py-2 text-[12px] text-danger">
            <AlertTriangle size={14} className="mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div className="glass-inset space-y-1.5 rounded-xl p-3 text-[12px] text-ink-muted">
          <div className="flex items-center justify-between gap-3">
            <span>Summon Atlas from anywhere</span>
            <kbd className="rounded bg-ink/10 px-1.5 py-0.5 text-[11px] font-medium text-ink">
              Ctrl + Shift + A
            </kbd>
          </div>
          <div className="flex items-center justify-between gap-3">
            <span>Command palette</span>
            <kbd className="rounded bg-ink/10 px-1.5 py-0.5 text-[11px] font-medium text-ink">
              K
            </kbd>
          </div>
          <p className="pt-1 text-[11px] text-ink-faint">
            Closing the window keeps Atlas running in the system tray so nudges still reach you.
            Quit for real from the tray icon.
          </p>
        </div>
      </CardBody>
    </Card>
  );
}
