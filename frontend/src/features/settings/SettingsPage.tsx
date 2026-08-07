import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Check, Download, Lock, Upload } from "lucide-react";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { api } from "@/lib/api";
import { decryptBackup, downloadText, encryptBackup, isEncryptedBackup } from "@/lib/backup";
import { todayISO } from "@/lib/utils";
import type { BackupDoc, BackupResult } from "@/lib/types";
import { CoachKeyCard } from "./CoachKeyCard";
import { DesktopCard } from "./DesktopCard";

export function SettingsPage() {
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);

  const [encrypt, setEncrypt] = useState(false);
  const [exportPass, setExportPass] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const [envelope, setEnvelope] = useState<Parameters<typeof decryptBackup>[0] | null>(null);
  const [importPass, setImportPass] = useState("");
  const [staged, setStaged] = useState<BackupDoc | null>(null);
  const [result, setResult] = useState<BackupResult | null>(null);

  const reset = () => {
    setMsg(null);
    setErr(null);
  };

  const doExport = async () => {
    reset();
    if (encrypt && exportPass.length < 6) {
      setErr("Use a passphrase of at least 6 characters.");
      return;
    }
    setBusy(true);
    try {
      const doc = await api.exportBackup();
      if (encrypt) {
        downloadText(`atlas-backup-${todayISO()}.atlas`, await encryptBackup(doc, exportPass));
        setMsg("Encrypted backup downloaded. Keep your passphrase safe — it can't be recovered.");
      } else {
        downloadText(`atlas-backup-${todayISO()}.json`, JSON.stringify(doc, null, 2));
        setMsg("Backup downloaded.");
      }
    } catch {
      setErr("Export failed.");
    }
    setBusy(false);
  };

  const onFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    reset();
    setResult(null);
    setStaged(null);
    setEnvelope(null);
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const parsed = JSON.parse(String(reader.result));
        if (isEncryptedBackup(parsed)) setEnvelope(parsed);
        else if (parsed?.atlas_backup) setStaged(parsed as BackupDoc);
        else setErr("That file isn't an Atlas backup.");
      } catch {
        setErr("Couldn't read that file.");
      }
    };
    reader.readAsText(file);
  };

  const decryptStage = async () => {
    if (!envelope) return;
    reset();
    try {
      const doc = (await decryptBackup(envelope, importPass)) as BackupDoc;
      if (!doc?.atlas_backup) {
        setErr("Decrypted, but that isn't a valid backup.");
        return;
      }
      setStaged(doc);
      setEnvelope(null);
      setImportPass("");
    } catch {
      setErr("Wrong passphrase, or the file is corrupted.");
    }
  };

  const confirmImport = async () => {
    if (!staged) return;
    reset();
    setBusy(true);
    try {
      const res = await api.importBackup(staged);
      setResult(res);
      setStaged(null);
      await qc.invalidateQueries();
    } catch {
      setErr("Import failed — your current data is unchanged.");
    }
    setBusy(false);
  };

  const stagedCount = staged
    ? Object.values(staged.data).reduce((n, arr) => n + (Array.isArray(arr) ? arr.length : 0), 0)
    : 0;

  return (
    <div className="animate-fade-in mx-auto max-w-2xl space-y-4">
      <div>
        <h2 className="text-xl font-display font-semibold text-ink">Settings</h2>
        <p className="text-sm text-ink-muted">Appearance and your data.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Appearance</CardTitle>
        </CardHeader>
        <CardBody className="flex items-center justify-between">
          <div>
            <div className="text-sm text-ink">Theme</div>
            <div className="text-[12px] text-ink-muted">Light, dark, or match your system.</div>
          </div>
          <ThemeToggle />
        </CardBody>
      </Card>

      <DesktopCard />

      <CoachKeyCard />

      <Card>
        <CardHeader>
          <CardTitle>Backup</CardTitle>
          <Download size={15} className="text-accent" />
        </CardHeader>
        <CardBody className="space-y-3">
          <p className="text-sm text-ink-muted">
            Export everything — habits, logs, tasks, journal, notes, and focus sessions — to a file
            you own.
          </p>
          <label className="flex items-center gap-2 text-sm text-ink">
            <input
              type="checkbox"
              checked={encrypt}
              onChange={(e) => setEncrypt(e.target.checked)}
              className="h-4 w-4"
              style={{ accentColor: "rgb(var(--accent))" }}
            />
            <Lock size={13} className="text-ink-faint" /> Encrypt with a passphrase
          </label>
          {encrypt && (
            <input
              type="password"
              value={exportPass}
              onChange={(e) => setExportPass(e.target.value)}
              placeholder="Passphrase (kept on this device)"
              className="h-9 w-full rounded-lg bg-ink/[0.05] px-2.5 text-sm text-ink outline-none placeholder:text-ink-faint"
            />
          )}
          <Button onClick={doExport} disabled={busy}>
            <Download size={15} /> Export data
          </Button>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Restore</CardTitle>
          <Upload size={15} className="text-accent" />
        </CardHeader>
        <CardBody className="space-y-3">
          <p className="text-sm text-ink-muted">
            Import an Atlas backup. This <strong className="text-ink">replaces all current data</strong>.
          </p>
          <input
            ref={fileRef}
            type="file"
            accept=".json,.atlas,application/json"
            className="hidden"
            onChange={onFile}
          />
          <Button variant="outline" onClick={() => fileRef.current?.click()}>
            <Upload size={15} /> Choose backup file
          </Button>

          {envelope && (
            <div className="glass-inset space-y-2 rounded-xl p-3">
              <div className="flex items-center gap-1.5 text-[13px] text-ink">
                <Lock size={13} className="text-accent" /> Encrypted backup — enter its passphrase.
              </div>
              <div className="flex gap-2">
                <input
                  type="password"
                  value={importPass}
                  onChange={(e) => setImportPass(e.target.value)}
                  placeholder="Passphrase"
                  className="h-9 flex-1 rounded-lg bg-ink/[0.05] px-2.5 text-sm text-ink outline-none placeholder:text-ink-faint"
                />
                <Button onClick={decryptStage} disabled={!importPass}>
                  Decrypt
                </Button>
              </div>
            </div>
          )}

          {staged && (
            <div className="bg-danger-soft space-y-2 rounded-xl p-3">
              <div className="flex items-center gap-1.5 text-[13px] font-medium text-danger">
                <AlertTriangle size={14} /> Replace all data with this backup?
              </div>
              <p className="text-[12px] text-ink-muted">
                {stagedCount} items{staged.exported_at ? ` · from ${staged.exported_at.slice(0, 10)}` : ""}. This
                can't be undone.
              </p>
              <div className="flex gap-2">
                <button
                  onClick={confirmImport}
                  disabled={busy}
                  className="pressable rounded-lg bg-danger px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
                >
                  {busy ? "Restoring…" : "Replace everything"}
                </button>
                <Button variant="ghost" onClick={() => setStaged(null)}>
                  Cancel
                </Button>
              </div>
            </div>
          )}

          {result && (
            <p className="flex items-center gap-1.5 text-sm text-success">
              <Check size={15} /> Restored {result.total} items from your backup.
            </p>
          )}
        </CardBody>
      </Card>

      {msg && <p className="px-1 text-sm text-success">{msg}</p>}
      {err && <p className="px-1 text-sm text-danger">{err}</p>}

      <p className="px-1 text-[11px] leading-relaxed text-ink-faint">
        Backups are handled on your device. When you encrypt, the passphrase never leaves your
        browser — Atlas can't recover it, so store it somewhere safe.
      </p>
    </div>
  );
}
