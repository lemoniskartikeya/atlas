import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Bot, Check, Eye, EyeOff, Loader2, Trash2 } from "lucide-react";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { KeyTestResult } from "@/lib/types";

/**
 * Anthropic API key management.
 *
 * The key is written to backend/.env on this machine — Atlas never transmits it
 * anywhere except to api.anthropic.com when you actually ask the coach
 * something. The API only ever returns a masked hint, so a saved key can be
 * recognised but never read back out of the UI.
 */
export function CoachKeyCard() {
  const qc = useQueryClient();
  const { data: status, refetch } = useQuery({
    queryKey: ["coach", "status"],
    queryFn: () => api.coachStatus(),
  });

  const [draft, setDraft] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState<null | "save" | "test" | "clear">(null);
  const [test, setTest] = useState<KeyTestResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // A newly saved key invalidates any previous verdict.
  useEffect(() => setTest(null), [status?.key_hint]);

  const refresh = async () => {
    await refetch();
    qc.invalidateQueries({ queryKey: ["coach"] });
  };

  const save = async () => {
    if (!draft.trim()) return;
    setBusy("save");
    setError(null);
    try {
      await api.setCoachKey(draft.trim());
      setDraft("");
      setShow(false);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    }
    setBusy(null);
  };

  const runTest = async () => {
    setBusy("test");
    setError(null);
    try {
      setTest(await api.testCoachKey());
    } catch (e) {
      setError((e as Error).message);
    }
    setBusy(null);
  };

  const clear = async () => {
    if (!window.confirm("Remove the saved API key? The coach falls back to local mode.")) return;
    setBusy("clear");
    try {
      await api.clearCoachKey();
      setTest(null);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    }
    setBusy(null);
  };

  const connected = status?.ai_available ?? false;

  return (
    <Card>
      <CardHeader>
        <CardTitle>AI Coach</CardTitle>
        <Bot size={15} className="text-accent" />
      </CardHeader>
      <CardBody className="space-y-3">
        <div className="flex items-center gap-2 text-[13px]">
          <span
            className={cn(
              "h-2 w-2 shrink-0 rounded-full",
              connected ? "bg-success" : "bg-ink-faint",
            )}
          />
          <span className="text-ink">
            {connected ? `Connected · ${status?.model}` : "Local mode"}
          </span>
          {status?.has_key && (
            <code className="ml-auto rounded bg-ink/[0.06] px-1.5 py-0.5 text-[11px] text-ink-muted">
              {status.key_hint}
            </code>
          )}
        </div>

        <p className="text-sm text-ink-muted">
          {connected
            ? "The coach answers general questions and grounds anything about you in your real Atlas data."
            : "Without a key the coach stays fully offline and can only answer questions about your own Atlas data. Add a key to let it answer anything."}
        </p>

        {status && !status.sdk_installed && (
          <div className="flex items-start gap-2 rounded-xl bg-warn/10 px-3 py-2 text-[12px] text-warn">
            <AlertTriangle size={14} className="mt-0.5 shrink-0" />
            <span>
              The <code>anthropic</code> package isn't installed. Run{" "}
              <code>pip install -r requirements-ai.txt</code> in <code>backend/</code>.
            </span>
          </div>
        )}

        <div className="flex gap-2">
          <div className="relative flex-1">
            <Input
              type={show ? "text" : "password"}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder={status?.has_key ? "Replace saved key…" : "sk-ant-…"}
              autoComplete="off"
              spellCheck={false}
              className="pr-10 font-mono text-[12px]"
            />
            <button
              type="button"
              onClick={() => setShow((s) => !s)}
              aria-label={show ? "Hide key" : "Show key"}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-ink-faint transition-colors hover:text-ink"
            >
              {show ? <EyeOff size={15} /> : <Eye size={15} />}
            </button>
          </div>
          <Button onClick={save} disabled={!draft.trim() || busy !== null}>
            {busy === "save" ? <Loader2 size={15} className="animate-spin" /> : "Save"}
          </Button>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" onClick={runTest} disabled={!status?.has_key || busy !== null}>
            {busy === "test" ? <Loader2 size={15} className="animate-spin" /> : null}
            Test connection
          </Button>
          {status?.has_key && (
            <Button variant="danger" onClick={clear} disabled={busy !== null}>
              <Trash2 size={15} /> Remove key
            </Button>
          )}
        </div>

        {test && (
          <div
            className={cn(
              "flex items-start gap-2 rounded-xl px-3 py-2 text-[13px]",
              test.ok ? "bg-success-soft text-success" : "bg-danger-soft text-danger",
            )}
          >
            {test.ok ? (
              <Check size={14} className="mt-0.5 shrink-0" />
            ) : (
              <AlertTriangle size={14} className="mt-0.5 shrink-0" />
            )}
            <span>{test.detail}</span>
          </div>
        )}

        {error && <p className="text-sm text-danger">{error}</p>}

        <p className="text-[11px] leading-relaxed text-ink-faint">
          Stored in <code>backend/.env</code> on this machine and never committed. Atlas sends your
          key and a compact summary of your Atlas data to api.anthropic.com only when you ask the
          coach something. Get a key at console.anthropic.com.
        </p>
      </CardBody>
    </Card>
  );
}
