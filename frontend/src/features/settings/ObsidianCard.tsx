import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Check, FolderOpen, Loader2, RefreshCw } from "lucide-react";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { ObsidianSyncResult, ObsidianVaultCheck } from "@/lib/types";

const KEY = "atlas-obsidian-vault";

/**
 * Obsidian sync.
 *
 * The vault path is a property of this machine rather than the account, so it
 * lives in localStorage and travels with each request — no schema change for
 * something the desktop remembers perfectly well on its own.
 */
export function ObsidianCard() {
  const qc = useQueryClient();
  const [path, setPath] = useState(() => localStorage.getItem(KEY) ?? "");
  const [check, setCheck] = useState<ObsidianVaultCheck | null>(null);
  const [result, setResult] = useState<ObsidianSyncResult | null>(null);
  const [busy, setBusy] = useState<null | "check" | "sync">(null);
  const [error, setError] = useState<string | null>(null);

  // Validate whatever was remembered, so returning to this page tells you
  // straight away whether the saved folder is still there.
  useEffect(() => {
    if (!path.trim()) return;
    let cancelled = false;
    api
      .checkObsidianVault(path)
      .then((r) => !cancelled && setCheck(r))
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
    // Only on mount: typing re-checks explicitly via the button.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const remember = (value: string) => {
    setPath(value);
    setCheck(null);
    setResult(null);
    localStorage.setItem(KEY, value);
  };

  const run = async (kind: "check" | "sync", fn: () => Promise<void>) => {
    setBusy(kind);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError((e as Error).message);
    }
    setBusy(null);
  };

  const doCheck = () => run("check", async () => setCheck(await api.checkObsidianVault(path)));

  const doSync = () =>
    run("sync", async () => {
      const res = await api.syncObsidian(path);
      setResult(res);
      // Sync can bring journal and note edits back in, so anything showing
      // them is now stale.
      await qc.invalidateQueries();
    });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Obsidian</CardTitle>
        <FolderOpen size={15} className="text-accent" />
      </CardHeader>
      <CardBody className="space-y-3">
        <p className="text-sm text-ink-muted">
          Keep your journal and notes in an Obsidian vault as plain Markdown. Atlas writes into an{" "}
          <code>Atlas</code> folder inside the vault and reads back anything you change there —
          nothing else in the vault is touched.
        </p>

        <div className="flex gap-2">
          <Input
            value={path}
            onChange={(e) => remember(e.target.value)}
            placeholder="Path to your vault, e.g. C:\Users\you\Documents\MyVault"
            spellCheck={false}
            className="flex-1 font-mono text-[12px]"
          />
          <Button variant="outline" onClick={doCheck} disabled={!path.trim() || busy !== null}>
            {busy === "check" ? <Loader2 size={15} className="animate-spin" /> : "Check"}
          </Button>
        </div>

        {check && (
          <div
            className={cn(
              "flex items-start gap-2 rounded-xl px-3 py-2 text-[12px]",
              check.exists ? "bg-success-soft text-success" : "bg-danger-soft text-danger",
            )}
          >
            {check.exists ? (
              <Check size={14} className="mt-0.5 shrink-0" />
            ) : (
              <AlertTriangle size={14} className="mt-0.5 shrink-0" />
            )}
            <span>{check.detail}</span>
          </div>
        )}

        <Button onClick={doSync} disabled={!path.trim() || busy !== null}>
          {busy === "sync" ? (
            <Loader2 size={15} className="animate-spin" />
          ) : (
            <RefreshCw size={15} />
          )}
          Sync now
        </Button>

        {result && (
          <div className="glass-inset space-y-1.5 rounded-xl p-3 text-[12px]">
            <div className="text-ink">
              {result.exported} written to the vault · {result.imported} brought in ·{" "}
              {result.updated_in_atlas} updated in Atlas
            </div>
            {result.skipped > 0 && (
              <div className="text-ink-muted">
                {result.skipped} left alone because the vault's copy was newer.
              </div>
            )}
            {result.conflicts.map((line) => (
              <div key={line} className="text-ink-muted">
                {line}
              </div>
            ))}
          </div>
        )}

        {error && <p className="text-sm text-danger">{error}</p>}

        <p className="text-[11px] leading-relaxed text-ink-faint">
          When the same entry changed in both places, the most recent edit wins and the other is
          reported above rather than discarded quietly. Sync runs when you ask it to — nothing
          watches your files in the background.
        </p>
      </CardBody>
    </Card>
  );
}
