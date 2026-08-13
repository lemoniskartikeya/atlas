import { useEffect, useState } from "react";
import { Check, Copy, ExternalLink, KeyRound, Loader2 } from "lucide-react";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { openExternal } from "@/lib/desktop";
import type { GoogleConfigStatus } from "@/lib/types";

/**
 * Sign in with Google — the credential half.
 *
 * Atlas cannot ship a Google OAuth client ID. It belongs to whoever runs the
 * app, is created in their own Google Cloud project, and a binary anyone can
 * read is not a place to keep one. So this is where theirs goes, along with
 * the redirect URI they have to register for it to work at all.
 */
export function GoogleCard() {
  const [status, setStatus] = useState<GoogleConfigStatus | null>(null);
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.googleStatus().then(setStatus).catch(() => undefined);
  }, []);

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      setStatus(await api.setGoogleConfig(clientId.trim(), clientSecret.trim() || null));
      setClientId("");
      setClientSecret("");
    } catch (e) {
      setError((e as Error).message);
    }
    setBusy(false);
  };

  const copyRedirect = async () => {
    if (!status) return;
    await navigator.clipboard.writeText(status.redirect_uri);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Sign in with Google</CardTitle>
        <KeyRound size={15} className="text-accent" />
      </CardHeader>
      <CardBody className="space-y-3">
        <div className="flex items-center gap-2 text-[13px]">
          <span
            className={`h-2 w-2 shrink-0 rounded-full ${
              status?.configured ? "bg-success" : "bg-ink-faint"
            }`}
          />
          <span className="text-ink">
            {status?.configured
              ? `Enabled · ${status.client_id_hint}`
              : "Not set up — the sign-in screen shows password login only"}
          </span>
        </div>

        <p className="text-sm text-ink-muted">
          Atlas can't ship a client ID — anything inside the app can be read out of it. Create an
          OAuth client (<strong className="text-ink">Desktop app</strong>) and paste its ID here.
        </p>

        <div className="glass-inset space-y-1.5 rounded-xl p-3">
          <div className="text-[12px] text-ink-muted">
            Register this exact redirect URI on that client:
          </div>
          <div className="flex items-center gap-2">
            <code className="min-w-0 flex-1 truncate rounded bg-ink/[0.06] px-2 py-1 font-mono text-[11px] text-ink">
              {status?.redirect_uri ?? "…"}
            </code>
            <Button variant="outline" onClick={copyRedirect} disabled={!status}>
              {copied ? <Check size={14} /> : <Copy size={14} />}
            </Button>
          </div>
        </div>

        <Input
          value={clientId}
          onChange={(e) => setClientId(e.target.value)}
          placeholder="123456789-abc.apps.googleusercontent.com"
          spellCheck={false}
          className="font-mono text-[12px]"
        />
        <Input
          type="password"
          value={clientSecret}
          onChange={(e) => setClientSecret(e.target.value)}
          placeholder="Client secret (only for Web application clients)"
          autoComplete="off"
          spellCheck={false}
          className="font-mono text-[12px]"
        />

        <div className="flex flex-wrap items-center gap-2">
          <Button onClick={save} disabled={clientId.trim().length < 8 || busy}>
            {busy ? <Loader2 size={15} className="animate-spin" /> : null}
            Save
          </Button>
          <button
            type="button"
            onClick={() => void openExternal("https://console.cloud.google.com/apis/credentials")}
            className="inline-flex items-center gap-1 text-[12px] text-accent hover:underline"
          >
            Open Google Cloud credentials <ExternalLink size={12} />
          </button>
        </div>

        {error && <p className="text-sm text-danger">{error}</p>}

        <p className="text-[11px] leading-relaxed text-ink-faint">
          Sign-in opens your real browser, so you can see who's asking. Accounts match on Google's
          account id, not your email address.
        </p>
      </CardBody>
    </Card>
  );
}
