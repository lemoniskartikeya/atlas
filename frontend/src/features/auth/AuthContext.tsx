import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, onSessionExpired, session } from "@/lib/api";
import type { AtlasUser, PasswordPolicy, RegisterBody } from "@/lib/types";

interface AuthState {
  user: AtlasUser | null;
  policy: PasswordPolicy | null;
  /** False until the stored token has been checked against the backend. */
  ready: boolean;
  /** True when no account exists yet — the UI offers "create" rather than "sign in". */
  needsSetup: boolean;
  signIn: (identifier: string, password: string) => Promise<void>;
  signUp: (body: RegisterBody) => Promise<void>;
  signOut: () => Promise<void>;
}

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [user, setUser] = useState<AtlasUser | null>(null);
  const [policy, setPolicy] = useState<PasswordPolicy | null>(null);
  const [needsSetup, setNeedsSetup] = useState(false);
  const [ready, setReady] = useState(false);

  // Resolve the stored token once on boot. A token that no longer resolves is
  // dropped rather than left to 401 every subsequent request.
  useEffect(() => {
    let cancelled = false;
    api
      .authStatus()
      .then((s) => {
        if (cancelled) return;
        setPolicy(s.policy);
        setNeedsSetup(!s.has_accounts);
        if (s.authenticated && s.user) setUser(s.user);
        else session.clear();
      })
      .catch(() => {
        /* backend unreachable — AppGate surfaces that separately */
      })
      .finally(() => !cancelled && setReady(true));
    return () => {
      cancelled = true;
    };
  }, []);

  // Sessions expire, and now that every data endpoint requires one, a dead
  // token would leave every page erroring with no way back. Drop it and let
  // the sign-in screen take over instead.
  useEffect(() => {
    onSessionExpired(() => {
      session.clear();
      setUser(null);
      qc.clear();
    });
    return () => onSessionExpired(null);
  }, [qc]);

  const adopt = useCallback(
    (token: string, u: AtlasUser) => {
      session.set(token);
      setUser(u);
      setNeedsSetup(false);
      // Data was fetched (or refused) as a different identity — start clean.
      qc.clear();
    },
    [qc],
  );

  const signIn = useCallback(
    async (identifier: string, password: string) => {
      const res = await api.login(identifier, password);
      adopt(res.token, res.user);
    },
    [adopt],
  );

  const signUp = useCallback(
    async (body: RegisterBody) => {
      const res = await api.register(body);
      adopt(res.token, res.user);
    },
    [adopt],
  );

  const signOut = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      /* revoking server-side is best-effort; the local token goes regardless */
    }
    session.clear();
    setUser(null);
    qc.clear();
  }, [qc]);

  const value = useMemo(
    () => ({ user, policy, ready, needsSetup, signIn, signUp, signOut }),
    [user, policy, ready, needsSetup, signIn, signUp, signOut],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
