import { useEffect, useState } from "react";
import { Monitor, Power } from "lucide-react";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { autostart, isDesktop } from "@/lib/desktop";
import { cn } from "@/lib/utils";

function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: () => void;
  label: string;
}) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={onChange}
      className={cn(
        "pressable relative h-6 w-11 shrink-0 rounded-full transition-colors",
        checked ? "bg-accent" : "bg-ink/15",
      )}
    >
      <span
        className={cn(
          "absolute top-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-transform duration-200 ease-out-soft",
          checked ? "translate-x-[22px]" : "translate-x-0.5",
        )}
      />
    </button>
  );
}

/** Desktop-only preferences. Hidden entirely when Atlas runs in a browser. */
export function DesktopCard() {
  const [launchOnStartup, setLaunchOnStartup] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (isDesktop()) void autostart.isEnabled().then(setLaunchOnStartup);
  }, []);

  if (!isDesktop()) return null;

  const toggleStartup = async () => {
    if (busy) return;
    setBusy(true);
    const next = !launchOnStartup;
    try {
      await autostart.set(next);
      setLaunchOnStartup(await autostart.isEnabled());
    } catch {
      setLaunchOnStartup(await autostart.isEnabled().catch(() => false));
    }
    setBusy(false);
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
            label="Launch Atlas at login"
          />
        </div>

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
              Ctrl + K
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
