import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowLeft, Loader2, Mail } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input, Field } from "@/components/ui/input";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { OtpPurpose } from "@/lib/types";

const CODE_LENGTH = 6;

type Step = "email" | "code";

/**
 * Sign in with a code sent to your email.
 *
 * Renders nothing until the backend says a mail provider is configured —
 * offering a button that can only ever produce "email isn't set up" would be
 * worse than not offering it. The code is checked server-side; nothing here
 * knows or decides whether it is right.
 */
export function EmailOtpSignIn({
  mode,
  onToken,
}: {
  mode: "signin" | "signup";
  onToken: (token: string) => void;
}) {
  const purpose: OtpPurpose = mode === "signup" ? "signup" : "login";

  const [available, setAvailable] = useState(false);
  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState<null | "send" | "verify">(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [resendIn, setResendIn] = useState(0);

  const codeRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api
      .emailStatus()
      .then((s) => setAvailable(s.email_configured))
      .catch(() => setAvailable(false));
  }, []);

  // Countdown until another code may be requested. The backend enforces this
  // regardless; the timer exists so the button isn't a coin flip.
  useEffect(() => {
    if (resendIn <= 0) return;
    const id = window.setTimeout(() => setResendIn((n) => n - 1), 1000);
    return () => clearTimeout(id);
  }, [resendIn]);

  // Going back to the email step must not leave a stale code behind.
  useEffect(() => {
    if (step === "code") codeRef.current?.focus();
    else setCode("");
  }, [step]);

  const fail = (e: unknown) => {
    const raw = (e as Error).message ?? String(e);
    // Strip the leading status code the http helper prefixes on.
    setError(raw.replace(/^\d{3}\s*/, ""));
  };

  const send = useCallback(
    async (isResend = false) => {
      if (!email.trim()) return;
      setBusy("send");
      setError(null);
      setNotice(null);
      try {
        const res = await api.sendOtp(email, purpose);
        setStep("code");
        setResendIn(res.resend_in_seconds);
        setNotice(isResend ? "New code sent." : res.detail);
        // Development convenience only: the backend returns this exclusively
        // when it is running in development with the echo explicitly enabled.
        if (res.dev_code) setCode(res.dev_code);
      } catch (e) {
        fail(e);
      }
      setBusy(null);
    },
    [email, purpose],
  );

  const verify = useCallback(async () => {
    if (code.length !== CODE_LENGTH) return;
    setBusy("verify");
    setError(null);
    try {
      const res = await api.verifyOtp(email, code, purpose);
      onToken(res.token);
    } catch (e) {
      fail(e);
      setCode("");
      codeRef.current?.focus();
    }
    setBusy(null);
  }, [code, email, purpose, onToken]);

  if (!available) return null;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <span className="h-px flex-1 bg-border/10" />
        <span className="text-[11px] uppercase tracking-wide text-ink-faint">or</span>
        <span className="h-px flex-1 bg-border/10" />
      </div>

      {step === "email" ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void send();
          }}
          className="space-y-2"
        >
          <Field label="Email address">
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              autoComplete="email"
              spellCheck={false}
            />
          </Field>
          <Button
            type="submit"
            variant="outline"
            className="w-full"
            disabled={!email.trim() || busy !== null}
          >
            {busy === "send" ? (
              <Loader2 size={15} className="animate-spin" />
            ) : (
              <Mail size={15} />
            )}
            Email me a code
          </Button>
        </form>
      ) : (
        <div className="space-y-2">
          <p className="text-center text-[13px] text-ink">
            Enter the 6-digit code sent to{" "}
            <span className="font-medium">{email.trim().toLowerCase()}</span>.
          </p>

          <CodeInput
            inputRef={codeRef}
            value={code}
            onChange={(next) => {
              setCode(next);
              setError(null);
            }}
            onComplete={() => void verify()}
            disabled={busy !== null}
          />

          <Button
            onClick={() => void verify()}
            size="lg"
            className="w-full"
            disabled={code.length !== CODE_LENGTH || busy !== null}
          >
            {busy === "verify" ? <Loader2 size={15} className="animate-spin" /> : null}
            {busy === "verify" ? "Verifying…" : "Verify"}
          </Button>

          <div className="flex items-center justify-between pt-0.5">
            <button
              type="button"
              onClick={() => {
                setStep("email");
                setError(null);
                setNotice(null);
              }}
              className="inline-flex items-center gap-1 text-[12px] text-ink-muted hover:text-ink"
            >
              <ArrowLeft size={12} /> Use a different email
            </button>
            <button
              type="button"
              onClick={() => void send(true)}
              disabled={resendIn > 0 || busy !== null}
              className={cn(
                "text-[12px]",
                resendIn > 0 || busy !== null
                  ? "cursor-not-allowed text-ink-faint"
                  : "text-accent hover:underline",
              )}
            >
              {resendIn > 0 ? `Resend in ${resendIn}s` : "Resend code"}
            </button>
          </div>
        </div>
      )}

      {notice && !error && (
        <p className="text-center text-[12px] leading-relaxed text-ink-muted">{notice}</p>
      )}
      {error && (
        <p className="text-center text-[12px] leading-relaxed text-danger">{error}</p>
      )}
    </div>
  );
}

/**
 * Six boxes that behave like one field.
 *
 * A single real input sits invisibly on top, so paste, autofill, mobile
 * keyboards and the browser's own SMS/email code suggestion all work — the
 * boxes are only a rendering of its value. Six separate inputs look the same
 * and break every one of those.
 */
const CodeInput = ({
  inputRef,
  value,
  onChange,
  onComplete,
  disabled,
}: {
  inputRef: React.RefObject<HTMLInputElement>;
  value: string;
  onChange: (next: string) => void;
  onComplete: () => void;
  disabled?: boolean;
}) => {
  const cells = Array.from({ length: CODE_LENGTH });

  return (
    <div className="relative">
      <input
        ref={inputRef}
        value={value}
        onChange={(e) => {
          const digits = e.target.value.replace(/\D/g, "").slice(0, CODE_LENGTH);
          onChange(digits);
          if (digits.length === CODE_LENGTH) onComplete();
        }}
        inputMode="numeric"
        // Lets the OS offer the code straight from the notification.
        autoComplete="one-time-code"
        maxLength={CODE_LENGTH}
        disabled={disabled}
        aria-label="6-digit verification code"
        className="absolute inset-0 z-10 h-full w-full cursor-text opacity-0"
      />
      <div className="flex justify-between gap-1.5" aria-hidden="true">
        {cells.map((_, i) => (
          <div
            key={i}
            className={cn(
              "grid h-11 flex-1 place-items-center rounded-xl border font-mono text-[17px] text-ink transition-colors",
              i === value.length && !disabled
                ? "border-accent/50 bg-accent/[0.06]"
                : "border-border/15 bg-ink/[0.03]",
            )}
          >
            {value[i] ?? ""}
          </div>
        ))}
      </div>
    </div>
  );
};
