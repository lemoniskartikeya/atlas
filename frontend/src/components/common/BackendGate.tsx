import { useCallback, useEffect, useState, type ReactNode } from "react";
import { AlertTriangle, Orbit } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { isDesktop } from "@/lib/desktop";

type State = "waiting" | "ready" | "unreachable";

/** How long to keep waiting before admitting the backend isn't coming. */
const TIMEOUT_MS = 25_000;
const INTERVAL_MS = 400;

/**
 * Holds the UI until the local backend answers.
 *
 * In the packaged desktop app the Rust shell spawns the backend at the same
 * moment the window appears, so for the first second or two there is nothing to
 * talk to. Without this gate every page would mount, fail, and show an error
 * that fixes itself — which reads as a broken app.
 */
export function BackendGate({ children }: { children: ReactNode }) {
  const [state, setState] = useState<State>("waiting");
  const [attempt, setAttempt] = useState(0);

  const retry = useCallback(() => {
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

  if (state === "ready") return <>{children}</>;

  return (
    <div className="app-aurora grid min-h-screen place-items-center p-6">
      <div className="relative z-10 flex max-w-sm flex-col items-center text-center">
        {state === "waiting" ? (
          <>
            <div className="grid h-12 w-12 animate-pulse place-items-center rounded-2xl bg-accent text-white">
              <Orbit size={24} />
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
            <p className="mt-1 text-[13px] text-ink-muted">
              {isDesktop()
                ? "The bundled backend didn't come up. Restarting Atlas usually clears it."
                : "No backend on http://127.0.0.1:8000 — start it with `uvicorn app.main:app` in backend/."}
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
