import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { openExternal } from "@/lib/desktop";

/** How often to ask whether the browser half of the flow has finished. */
const POLL_MS = 1200;
/** Give up after a few minutes rather than polling into the night. */
const TIMEOUT_MS = 5 * 60 * 1000;

/**
 * "Continue with Google".
 *
 * Sign-in happens in the user's real browser — Google refuses embedded
 * webviews, and rightly so. The backend receives the redirect, finishes the
 * exchange and parks a session; this polls for it.
 *
 * Renders nothing when no OAuth client is configured. Atlas cannot ship one:
 * the client ID belongs to whoever runs the app, so until they add theirs in
 * Settings there is no button to show.
 */
export function GoogleSignIn({ onToken }: { onToken: (token: string) => void }) {
  const [available, setAvailable] = useState(false);
  const [waiting, setWaiting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timers = useRef<number[]>([]);

  useEffect(() => {
    api
      .googleStatus()
      .then((s) => setAvailable(s.configured))
      .catch(() => setAvailable(false));
    return () => timers.current.forEach(clearTimeout);
  }, []);

  const start = useCallback(async () => {
    setError(null);
    setWaiting(true);
    try {
      const { authorize_url, state } = await api.googleStart();
      await openExternal(authorize_url);

      const deadline = Date.now() + TIMEOUT_MS;
      const poll = async () => {
        if (Date.now() > deadline) {
          setWaiting(false);
          setError("That took too long. Try again.");
          return;
        }
        try {
          const res = await api.googleResult(state);
          if (res.status === "ready" && res.token) {
            setWaiting(false);
            onToken(res.token);
            return;
          }
          if (res.status === "error") {
            setWaiting(false);
            setError(res.detail ?? "Sign-in failed.");
            return;
          }
        } catch {
          // A blip while the browser tab is open shouldn't end the attempt —
          // keep polling until the deadline.
        }
        timers.current.push(window.setTimeout(poll, POLL_MS));
      };
      timers.current.push(window.setTimeout(poll, POLL_MS));
    } catch (e) {
      setWaiting(false);
      setError((e as Error).message);
    }
  }, [onToken]);

  if (!available) return null;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-3">
        <span className="h-px flex-1 bg-border/10" />
        <span className="text-[11px] uppercase tracking-wide text-ink-faint">or</span>
        <span className="h-px flex-1 bg-border/10" />
      </div>

      <button
        type="button"
        onClick={start}
        disabled={waiting}
        className="pressable flex h-10 w-full items-center justify-center gap-2 rounded-xl border border-border/15 bg-surface text-[13px] font-medium text-ink transition-colors hover:bg-ink/[0.03] disabled:opacity-60"
      >
        {waiting ? <Loader2 size={15} className="animate-spin" /> : <GoogleMark />}
        {waiting ? "Waiting for your browser…" : "Continue with Google"}
      </button>

      {waiting && (
        <p className="text-center text-[11px] text-ink-faint">
          Finish signing in on the tab that opened, then come back here.
        </p>
      )}
      {error && <p className="text-center text-[12px] text-danger">{error}</p>}
    </div>
  );
}

/** Google's mark, drawn inline so the button needs no network request. */
function GoogleMark() {
  return (
    <svg width="15" height="15" viewBox="0 0 48 48" aria-hidden="true">
      <path
        fill="#4285F4"
        d="M45.1 24.5c0-1.6-.1-2.8-.4-4H24v7.3h12.1c-.2 2-1.6 5-4.5 7l6.9 5.3c4.1-3.8 6.6-9.4 6.6-15.6z"
      />
      <path
        fill="#34A853"
        d="M24 46c5.9 0 10.9-2 14.5-5.3l-6.9-5.3c-1.8 1.3-4.3 2.2-7.6 2.2-5.8 0-10.7-3.8-12.5-9.700000000000001l-7.1 5.5C7.9 40.8 15.4 46 24 46z"
      />
      <path
        fill="#FBBC05"
        d="M11.5 27.9c-.5-1.4-.7-2.9-.7-4.4s.3-3 .7-4.4l-7.1-5.5C2.9 16.5 2 20.1 2 23.5s.9 7 2.4 9.9l7.1-5.5z"
      />
      <path
        fill="#EA4335"
        d="M24 10.3c4.1 0 6.9 1.8 8.5 3.3l6.2-6C34.9 4.1 29.9 2 24 2 15.4 2 7.9 7.2 4.4 13.6l7.1 5.5C13.3 14.1 18.2 10.3 24 10.3z"
      />
    </svg>
  );
}
