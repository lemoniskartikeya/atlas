import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Bot,
  Check,
  ExternalLink,
  Eye,
  EyeOff,
  Loader2,
  Trash2,
} from "lucide-react";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { CoachProviderOption, KeyTestResult } from "@/lib/types";

/**
 * Choose who answers the coach, and hold that provider's key.
 *
 * Keys are written to backend/.env on this machine and stored one per provider,
 * so trying a second free tier doesn't discard the first. The API only ever
 * returns a masked hint — a saved key can be recognised, never read back out.
 */
export function CoachKeyCard() {
  const qc = useQueryClient();
  const { data: status, refetch } = useQuery({
    queryKey: ["coach", "status"],
    queryFn: () => api.coachStatus(),
  });

  const [draft, setDraft] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState<null | "save" | "test" | "clear" | "switch">(null);
  const [test, setTest] = useState<KeyTestResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // A newly saved key, or a different provider, invalidates any previous verdict.
  useEffect(() => setTest(null), [status?.key_hint, status?.provider]);

  const providers = status?.providers ?? [];
  const selected = providers.find((p) => p.id === status?.provider);
  const connected = status?.ai_available ?? false;

  const refresh = async () => {
    await refetch();
    qc.invalidateQueries({ queryKey: ["coach"] });
  };

  const run = async (kind: typeof busy, fn: () => Promise<unknown>) => {
    setBusy(kind);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError((e as Error).message);
    }
    setBusy(null);
  };

  const choose = (id: string) =>
    run("switch", async () => {
      await api.setCoachProvider(id, null);
      setDraft("");
      await refresh();
    });

  const pinModel = (model: string) =>
    run("switch", async () => {
      await api.setCoachProvider(status!.provider!, model);
      await refresh();
    });

  const save = () =>
    run("save", async () => {
      await api.setCoachKey(draft.trim(), status?.provider ?? undefined);
      setDraft("");
      setShow(false);
      await refresh();
    });

  const clear = async () => {
    if (!window.confirm("Remove this provider's saved key? The coach falls back to local mode."))
      return;
    await run("clear", async () => {
      await api.clearCoachKey(status?.provider ?? undefined);
      setTest(null);
      await refresh();
    });
  };

  // The local option is the only one that never sends anything off the machine,
  // so it gets said plainly rather than left for the user to infer.
  const privacyNote = selected?.local
    ? "Runs entirely on this machine. Nothing about you leaves the device."
    : `Atlas sends your key and a compact summary of your Atlas data to ${
        selected?.label ?? "the provider"
      } only when you ask the coach something.`;

  return (
    <Card>
      <CardHeader>
        <CardTitle>AI Coach</CardTitle>
        <Bot size={15} className="text-accent" />
      </CardHeader>
      <CardBody className="space-y-4">
        <div className="flex items-center gap-2 text-[13px]">
          <span
            className={cn("h-2 w-2 shrink-0 rounded-full", connected ? "bg-success" : "bg-ink-faint")}
          />
          <span className="text-ink">
            {connected ? `Ready · ${status?.model}` : "Local mode — answers from your data only"}
          </span>
          {status?.has_key && (
            <code className="ml-auto rounded bg-ink/[0.06] px-1.5 py-0.5 text-[11px] text-ink-muted">
              {status.key_hint}
            </code>
          )}
        </div>

        <ProviderPicker
          providers={providers}
          selectedId={status?.provider ?? null}
          disabled={busy !== null}
          onSelect={choose}
        />

        {selected && !selected.needs_key ? (
          <LocalProviderPanel option={selected} model={status?.model ?? ""} onPick={pinModel} />
        ) : (
          <>
            {status && status.provider === "anthropic" && !status.sdk_installed && (
              <Notice tone="warn">
                The <code>anthropic</code> package isn't installed. Run{" "}
                <code>pip install -r requirements-ai.txt</code> in <code>backend/</code>.
              </Notice>
            )}

            <div className="flex gap-2">
              <div className="relative flex-1">
                <Input
                  type={show ? "text" : "password"}
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  placeholder={status?.has_key ? "Replace saved key…" : "Paste your API key"}
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

            {selected?.key_url && (
              <a
                href={selected.key_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-[12px] text-accent hover:underline"
              >
                Get a {selected.label} key <ExternalLink size={12} />
              </a>
            )}
          </>
        )}

        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="outline"
            onClick={() => run("test", async () => setTest(await api.testCoachKey()))}
            disabled={busy !== null || (!status?.has_key && !selected?.local)}
          >
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
          <Notice tone={test.ok ? "success" : "danger"} icon={test.ok ? "check" : "warn"}>
            {test.detail}
          </Notice>
        )}
        {error && <p className="text-sm text-danger">{error}</p>}

        <p className="text-[11px] leading-relaxed text-ink-faint">
          {privacyNote} Keys stay on this machine.
        </p>
      </CardBody>
    </Card>
  );
}

/** The choice itself: what each backend costs, stated up front. */
function ProviderPicker({
  providers,
  selectedId,
  disabled,
  onSelect,
}: {
  providers: CoachProviderOption[];
  selectedId: string | null;
  disabled: boolean;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="grid gap-1.5 sm:grid-cols-2">
      {providers.map((p) => {
        const active = p.id === selectedId;
        return (
          <button
            key={p.id}
            type="button"
            disabled={disabled}
            onClick={() => onSelect(p.id)}
            aria-pressed={active}
            className={cn(
              "pressable rounded-xl border px-3 py-2 text-left transition-colors disabled:opacity-60",
              active
                ? "border-accent/40 bg-accent/[0.07]"
                : "border-border/10 hover:bg-ink/[0.03]",
            )}
          >
            <div className="flex items-center gap-1.5">
              <span className="text-[13px] font-medium text-ink">{p.label}</span>
              {active && <Check size={13} className="text-accent" />}
            </div>
            <p className="mt-0.5 text-[11px] leading-snug text-ink-muted">{p.cost_note}</p>
          </button>
        );
      })}
    </div>
  );
}

/** Local models need no key — they need Ollama running and a model pulled. */
function LocalProviderPanel({
  option,
  model,
  onPick,
}: {
  option: CoachProviderOption;
  model: string;
  onPick: (model: string) => void;
}) {
  const installed = option.installed_models ?? [];

  if (installed.length === 0) {
    return (
      <Notice tone="warn">
        No local model found. Install Ollama from{" "}
        <a href={option.key_url ?? "#"} target="_blank" rel="noreferrer" className="underline">
          ollama.com
        </a>
        , then run <code>ollama pull {option.default_model}</code> and reopen this page.
      </Notice>
    );
  }

  return (
    <div className="space-y-1.5">
      <p className="text-[12px] text-ink-muted">Models installed on this machine:</p>
      <div className="flex flex-wrap gap-1.5">
        {installed.map((name) => (
          <button
            key={name}
            type="button"
            onClick={() => onPick(name)}
            className={cn(
              "pressable rounded-lg border px-2.5 py-1 font-mono text-[11px] transition-colors",
              name === model
                ? "border-accent/40 bg-accent/[0.07] text-ink"
                : "border-border/10 text-ink-muted hover:bg-ink/[0.03]",
            )}
          >
            {name}
          </button>
        ))}
      </div>
    </div>
  );
}

function Notice({
  tone,
  icon = "warn",
  children,
}: {
  tone: "warn" | "danger" | "success";
  icon?: "warn" | "check";
  children: React.ReactNode;
}) {
  const tones = {
    warn: "bg-warn/10 text-warn",
    danger: "bg-danger-soft text-danger",
    success: "bg-success-soft text-success",
  } as const;
  const Icon = icon === "check" ? Check : AlertTriangle;
  return (
    <div className={cn("flex items-start gap-2 rounded-xl px-3 py-2 text-[12px]", tones[tone])}>
      <Icon size={14} className="mt-0.5 shrink-0" />
      <span>{children}</span>
    </div>
  );
}
