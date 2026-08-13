import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { AlertTriangle } from "lucide-react";
import { AtlasMark } from "@/components/ui/atlas-mark";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { isDesktop, onBackendFailed } from "@/lib/desktop";

type State = "waiting" | "ready" | "unreachable";

/** How long to keep waiting before admitting the backend isn't coming. */
const TIMEOUT_MS = 25_000;
const INTERVAL_MS = 400;

const GENERIC_REASON = isDesktop()
  ? "The bundled backend didn't come up. Restarting Atlas usually clears it."
  : "No backend on http://127.0.0.1:8000 — start it with `uvicorn app.main:app` in backend/.";

/**
 * Holds the UI until the local backend answers.
 *
 * In the packaged desktop app the Rust shell spawns the backend at the same
 * moment the window appears, so for the first second or two there is nothing to
 * talk to. Without this gate every page would mount, fail, and show an error
 * that fixes itself — which reads as a broken app.
 *
 * When the backend dies instead of starting, the shell says so and says why —
 * so this stops immediately with the real reason rather than spinning out the
 * full timeout and then guessing.
 */
export function BackendGate({ children }: { children: ReactNode }) {
  const [state, setState] = useState<State>("waiting");
  const [reason, setReason] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  // Mirrors `state` for the event handler, which is registered once and
  // would otherwise close over a stale value.
  const stateRef = useRef(state);
  stateRef.current = state;

  const retry = useCallback(() => {
    setReason(null);
    setState("waiting");
    setAttempt((a) => a + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const startedAt = Date.now();

    const poll = async () => {
      while (!cancelled) {
        try {
          await api.health();
          if (!cancelled) setState("ready");
          return;
        } catch {
          if (Date.now() - startedAt > TIMEOUT_MS) {
            if (!cancelled) setState("unreachable");
            return;
          }
          await new Promise((r) => setTimeout(r, INTERVAL_MS));
        }
      }
    };

    void poll();
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  // The shell knows the backend died long before the poll loop gives up.
  useEffect(() => {
    let unlisten: (() => void) | undefined;
    let cancelled = false;

    void onBackendFailed((detail) => {
      if (cancelled) return;
      // Only while still waiting: a backend that dies after the app is running
      // is a different problem, and blanking a working UI would be worse than
      // letting the next request fail with its own error. Read the current
      // state from a ref rather than a setState updater — an updater must stay
      // free of side effects, and React invokes it twice in development.
      if (stateRef.current !== "waiting") return;
      setReason(detail);
      setState("unreachable");
    }).then((fn) => {
      if (cancelled) fn();
      else unlisten = fn;
    });

    return () => {
      cancelled = true;
      unlisten?.();
    };
  }, [attempt]);

  if (state === "ready") return <>{children}</>;

  return (
    <div className="app-aurora app-viewport grid place-items-center p-6">
      <div className="relative z-10 flex max-w-sm flex-col items-center text-center">
        {state === "waiting" ? (
          <>
            <div className="grid h-12 w-12 animate-pulse place-items-center rounded-2xl bg-accent text-white">
              <AtlasMark size={23} />
            </div>
            <p className="mt-4 font-display text-lg font-semibold text-ink">Starting Atlas…</p>
            <p className="mt-1 text-[13px] text-ink-muted">Waking the local engine.</p>
          </>
        ) : (
          <>
            <div className="grid h-12 w-12 place-items-center rounded-2xl bg-danger-soft text-danger">
              <AlertTriangle size={22} />
            </div>
            <p className="mt-4 font-display text-lg font-semibold text-ink">
              Atlas couldn't start its engine
            </p>
            <p className="mt-1 text-[13px] leading-relaxed text-ink-muted">
              {reason ?? GENERIC_REASON}
            </p>
            <Button className="mt-4" variant="outline" onClick={retry}>
              Try again
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
