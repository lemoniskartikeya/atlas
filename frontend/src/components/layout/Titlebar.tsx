import { useEffect, useState } from "react";
import { Copy, Minus, Square, X } from "lucide-react";
import { isDesktop, windowControls } from "@/lib/desktop";

function ControlButton({
  onClick,
  label,
  danger,
  children,
}: {
  onClick: () => void;
  label: string;
  danger?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      aria-label={label}
      title={label}
      className={
        "no-drag grid h-8 w-11 place-items-center text-ink-muted transition-colors " +
        (danger ? "hover:bg-danger hover:text-white" : "hover:bg-ink/10 hover:text-ink")
      }
    >
      {children}
    </button>
  );
}

/**
 * Custom window chrome for the desktop build.
 *
 * The native frame is switched off (`decorations: false`) so the titlebar can
 * carry the app's own material instead of an OS bar bolted above it. Renders
 * nothing in a browser, where the tab chrome already exists.
 */
export function Titlebar() {
  const [maximized, setMaximized] = useState(false);

  useEffect(() => {
    if (!isDesktop()) return;
    let unlisten: (() => void) | undefined;
    const sync = () => void windowControls.isMaximized().then(setMaximized);
    sync();
    void windowControls.onResized(sync).then((fn) => (unlisten = fn));
    return () => unlisten?.();
  }, []);

  if (!isDesktop()) return null;

  return (
    <div className="drag-region sticky top-0 z-30 flex h-8 shrink-0 items-center justify-between border-b border-border/10 bg-canvas/60 backdrop-blur-md">
      <span className="select-none pl-3 text-[11px] font-medium tracking-wide text-ink-faint">
        Atlas
      </span>
      <div className="flex items-center">
        <ControlButton onClick={() => void windowControls.minimize()} label="Minimize">
          <Minus size={13} />
        </ControlButton>
        <ControlButton
          onClick={() => void windowControls.toggleMaximize()}
          label={maximized ? "Restore" : "Maximize"}
        >
          {maximized ? <Copy size={11} /> : <Square size={11} />}
        </ControlButton>
        <ControlButton onClick={() => void windowControls.close()} label="Close to tray" danger>
          <X size={14} />
        </ControlButton>
      </div>
    </div>
  );
}
