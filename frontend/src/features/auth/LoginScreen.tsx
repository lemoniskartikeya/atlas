import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { AlertTriangle, Check, Eye, EyeOff, X } from "lucide-react";
import { AtlasMark } from "@/components/ui/atlas-mark";
import { GoogleSignIn } from "./GoogleSignIn";
import { Button } from "@/components/ui/button";
import { Input, Field } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { useAuth } from "./AuthContext";

/** The password policy, mirrored client-side purely so the user sees it live.
 *  The backend re-checks all of it — this is guidance, never the gate. */
const RULES: { label: string; test: (s: string) => boolean }[] = [
  { label: "At least 8 characters", test: (s) => s.length >= 8 },
  { label: "Contains a letter", test: (s) => /[A-Za-z]/.test(s) },
  { label: "Contains a number", test: (s) => /\d/.test(s) },
  { label: "Contains a special character", test: (s) => /[^A-Za-z0-9]/.test(s) },
];

function RuleList({ password }: { password: string }) {
  return (
    <ul className="mt-2 grid gap-1">
      {RULES.map((r) => {
        const ok = r.test(password);
        return (
          <li
            key={r.label}
            className={cn(
              "flex items-center gap-1.5 text-[12px] transition-colors",
              ok ? "text-success" : password ? "text-ink-faint" : "text-ink-faint",
            )}
          >
            <span
              className={cn(
                "grid h-3.5 w-3.5 shrink-0 place-items-center rounded-full border transition-colors",
                ok ? "border-success bg-success text-white" : "border-ink/20 text-transparent",
              )}
            >
              {ok ? <Check size={9} strokeWidth={4} /> : <X size={9} strokeWidth={4} />}
            </span>
            {r.label}
          </li>
        );
      })}
    </ul>
  );
}

function StrengthBar({ password }: { password: string }) {
  const passed = RULES.filter((r) => r.test(password)).length;
  const pctDone = (passed / RULES.length) * 100;
  const tone =
    passed <= 1 ? "bg-danger" : passed === 2 ? "bg-warn" : passed === 3 ? "bg-warn" : "bg-success";
  return (
    <div className="mt-2 h-1 overflow-hidden rounded-full bg-ink/10">
      <div
        className={cn("h-full rounded-full transition-all duration-500 ease-out-soft", tone)}
        style={{ width: `${pctDone}%` }}
      />
    </div>
  );
}

/**
 * Account gate. Doubles as first-run setup: when the vault has no accounts yet
 * it opens in "create" mode, because there is nothing to sign in to.
 */
export function LoginScreen() {
  const { signIn, signUp, signInWithToken, needsSetup, policy } = useAuth();
  const [mode, setMode] = useState<"signin" | "signup">(needsSetup ? "signup" : "signin");

  const [identifier, setIdentifier] = useState("");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const passwordOk = useMemo(() => RULES.every((r) => r.test(password)), [password]);
  const canSubmit =
    mode === "signin"
      ? identifier.trim().length > 0 && password.length > 0
      : username.trim().length >= 3 && passwordOk;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit || busy) return;
    setBusy(true);
    setError(null);
    try {
      if (mode === "signin") await signIn(identifier, password);
      else await signUp({ username, password, email: email.trim() || null });
    } catch (err) {
      setError((err as Error).message.replace(/^\d{3}\s*/, ""));
    } finally {
      setBusy(false);
    }
  };

  const swap = (next: "signin" | "signup") => {
    setMode(next);
    setError(null);
    setPassword("");
  };

  return (
    <div className="app-aurora app-viewport relative grid place-items-center p-4">
      <motion.div
        initial={{ opacity: 0, y: 14, scale: 0.985 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ type: "spring", stiffness: 300, damping: 28 }}
        className="glass relative z-10 w-full max-w-sm rounded-3xl p-7"
      >
        <div className="flex flex-col items-center text-center">
          <div className="grid h-12 w-12 place-items-center rounded-2xl bg-accent text-white shadow-sm">
            <AtlasMark size={23} />
          </div>
          <h1 className="mt-3 font-display text-2xl font-semibold text-ink">
            {mode === "signup" ? (needsSetup ? "Welcome to Atlas" : "Create an account") : "Atlas"}
          </h1>
          <p className="mt-1 text-[13px] text-ink-muted">
            {mode === "signup"
              ? needsSetup
                ? "Set up the account for this vault."
                : "Add another Atlas account."
              : "Sign in to your Atlas account."}
          </p>
        </div>

        <form onSubmit={submit} className="mt-6 space-y-3.5">
          {mode === "signin" ? (
            <Field label="Username or email">
              <Input
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                autoFocus
                autoComplete="username"
                placeholder="you"
              />
            </Field>
          ) : (
            <>
              <Field label="Username" hint="Letters, numbers, - and _ only.">
                <Input
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoFocus
                  autoComplete="username"
                  placeholder="you"
                />
              </Field>
              <Field label="Email" hint="Optional — used only to sign in.">
                <Input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="email"
                  placeholder="you@example.com"
                />
              </Field>
            </>
          )}

          <Field label="Password">
            <div className="relative">
              <Input
                type={show ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete={mode === "signup" ? "new-password" : "current-password"}
                className="pr-10"
              />
              <button
                type="button"
                onClick={() => setShow((s) => !s)}
                aria-label={show ? "Hide password" : "Show password"}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-ink-faint transition-colors hover:text-ink"
              >
                {show ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
            </div>
          </Field>

          {mode === "signup" && (
            <div>
              <StrengthBar password={password} />
              <RuleList password={password} />
            </div>
          )}

          {error && (
            <div className="bg-danger-soft flex items-start gap-2 rounded-xl px-3 py-2 text-[13px] text-danger">
              <AlertTriangle size={14} className="mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <Button type="submit" size="lg" className="w-full" disabled={!canSubmit || busy}>
            {busy
              ? mode === "signup"
                ? "Creating…"
                : "Signing in…"
              : mode === "signup"
                ? "Create account"
                : "Sign in"}
          </Button>
        </form>

        <div className="mt-4">
          <GoogleSignIn onToken={(token) => void signInWithToken(token).catch((e) => setError(String(e.message ?? e)))} />
        </div>

        {!needsSetup && (
          <p className="mt-4 text-center text-[12px] text-ink-muted">
            {mode === "signin" ? "No account yet?" : "Already have one?"}{" "}
            <button
              onClick={() => swap(mode === "signin" ? "signup" : "signin")}
              className="font-medium text-accent hover:underline"
            >
              {mode === "signin" ? "Create one" : "Sign in"}
            </button>
          </p>
        )}

        <p className="mt-5 text-center text-[11px] leading-relaxed text-ink-faint">
          {policy?.description ?? "Passwords need a letter, a number, and a special character."}
          <br />
          Your account and data stay on this device.
        </p>
      </motion.div>
    </div>
  );
}
