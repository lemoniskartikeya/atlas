import { useCallback, useEffect, useRef, useState } from "react";
import { Copy, Minus, Square, X } from "lucide-react";
import { AtlasMark } from "@/components/ui/atlas-mark";
import {
  isDesktop,
  reportDesktopError,
  reportDesktopInfo,
  windowControls,
} from "@/lib/desktop";

function ControlButton({
  onClick,
  label,
  accent,
  children,
}: {
  onClick: () => void;
  label: string;
  accent?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      className={
        // no-drag keeps the button clickable inside the drag strip; the
        // mousedown guard below is what actually protects it in WebView2.
        "no-drag grid h-8 w-11 place-items-center text-ink-muted transition-colors " +
        (accent ? "hover:bg-accent hover:text-white" : "hover:bg-ink/10 hover:text-ink")
      }
      onMouseDown={(e) => e.stopPropagation()}
    >
      {children}
    </button>
  );
}

/**
 * Custom window chrome for the desktop build.
 *
 * The native frame is switched off (`decorations: false`), so this bar is the
 * *only* way to minimise, maximise or close — which is why it is mounted above
 * the auth gate rather than inside the signed-in shell. Before that it did not
 * exist on the splash or login screen at all, leaving those with no window
 * controls whatsoever. Renders nothing in a browser, where tab chrome exists.
 */
export function Titlebar() {
  const [maximized, setMaximized] = useState(false);
  const barRef = useRef<HTMLDivElement | null>(null);

  // Record where the chrome actually landed. A control that renders off-screen
  // is indistinguishable from one that ignores clicks, and neither is visible
  // from the Rust side — so the window logs its own geometry once on mount.
  useEffect(() => {
    if (!isDesktop() || !barRef.current) return;
    const bar = barRef.current.getBoundingClientRect();
    const buttons = Array.from(barRef.current.querySelectorAll("button")).map(
      (b) => {
        const r = b.getBoundingClientRect();
        return `${b.getAttribute("aria-label")}@${Math.round(r.left)},${Math.round(
          r.top,
        )} ${Math.round(r.width)}x${Math.round(r.height)}`;
      },
    );
    const nav = navigator as Navigator & { deviceMemory?: number };
    void reportDesktopInfo(
      "chrome",
      `effects=${document.documentElement.dataset.effects} ` +
        `cores=${nav.hardwareConcurrency ?? "?"} memGB=${nav.deviceMemory ?? "?"} ` +
        `dpr=${window.devicePixelRatio} viewport=${window.innerWidth}x${window.innerHeight} ` +
        `doc=${document.documentElement.scrollWidth}x${document.documentElement.scrollHeight} ` +
        `bar=${Math.round(bar.left)},${Math.round(bar.top)} ${Math.round(bar.width)}x${Math.round(bar.height)} ` +
        `buttons=[${buttons.join(" | ")}]`,
    );
  }, []);

  useEffect(() => {
    if (!isDesktop()) return;
    let unlisten: (() => void) | undefined;
    let cancelled = false;
    const sync = () =>
      windowControls
        .isMaximized()
        .then((v) => {
          if (!cancelled) setMaximized(v);
        })
        .catch((err) => void reportDesktopError("titlebar.isMaximized", err));
    void sync();
    windowControls
      .onResized(sync)
      .then((fn) => {
        if (cancelled) fn();
        else unlisten = fn;
      })
      .catch((err) => void reportDesktopError("titlebar.onResized", err));
    return () => {
      cancelled = true;
      unlisten?.();
    };
  }, []);

  // Every control reports rather than swallowing: a rejected IPC call (a
  // missing capability, most likely) now lands in the desktop log instead of
  // looking like a dead button.
  const run = useCallback(
    (context: string, action: () => Promise<void>) => () =>
      void action().catch((err) => reportDesktopError(context, err)),
    [],
  );

  // Dragging the bar moves the window. Ignored when the press started on a
  // control, and on double-click, which toggles maximise like a native frame.
  const onDragMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button !== 0) return;
    if ((e.target as HTMLElement).closest("button")) return;
    if (e.detail === 2) {
      void windowControls
        .toggleMaximize()
        .catch((err) => reportDesktopError("titlebar.doubleClickMaximize", err));
      return;
    }
    void windowControls.startDragging().catch((err) => reportDesktopError("titlebar.drag", err));
  }, []);

  if (!isDesktop()) return null;

  return (
    <div
      ref={barRef}
      className="drag-region sticky top-0 z-40 flex h-8 shrink-0 items-center justify-between border-b border-border/10 bg-canvas/60 backdrop-blur-md"
      onMouseDown={onDragMouseDown}
    >
      <span className="flex select-none items-center gap-1.5 pl-3 text-[11px] font-medium tracking-wide text-ink-faint">
        <AtlasMark size={11} className="text-accent" />
        Atlas
      </span>
      <div className="flex items-center">
        <ControlButton onClick={run("window.minimize", windowControls.minimize)} label="Minimize">
          <Minus size={13} />
        </ControlButton>
        <ControlButton
          onClick={run("window.toggleMaximize", windowControls.toggleMaximize)}
          label={maximized ? "Restore" : "Maximize"}
        >
          {maximized ? <Copy size={11} /> : <Square size={11} />}
        </ControlButton>
        {/* Warm accent, not alarm red: closing parks Atlas in the tray, it does
            not destroy anything, and red reads as danger it hasn't earned. */}
        <ControlButton onClick={run("window.close", windowControls.close)} label="Close to tray" accent>
          <X size={14} />
        </ControlButton>
      </div>
    </div>
  );
}
