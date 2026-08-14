/**
 * Carrying a save out to the Obsidian vault.
 *
 * The backend cannot do this on its own. The vault path is a property of this
 * machine rather than of the account, so it lives in localStorage and reaches
 * the server only as a request field — which is why saving a journal entry
 * writes to the database and stops there. This module is the piece that hands
 * the path over after a save, so "synced folder" means what a person expects it
 * to mean.
 *
 * Two properties matter:
 *
 * - **Coalesced.** The journal autosaves a second after you stop typing. A full
 *   two-way sync per pause would hammer the disk and spend most of its time
 *   rewriting a file that has not changed, so bursts collapse into one run once
 *   the typing settles, and a sync already in flight queues at most one more.
 * - **Best-effort.** The entry is already safe in SQLite before any of this
 *   runs. A vault that is unplugged, renamed, or on a disconnected drive must
 *   never turn a successful save into a visible failure — Settings → Obsidian
 *   is where sync problems get reported, with the detail to act on them.
 */
import { api } from "@/lib/api";

/** Shared with the Settings card so the two cannot drift apart. */
export const VAULT_KEY = "atlas-obsidian-vault";

/** The configured vault path, or "" when there is none. */
export function getVaultPath(): string {
  try {
    return localStorage.getItem(VAULT_KEY)?.trim() ?? "";
  } catch {
    return ""; // storage can be unavailable (private mode, hardened settings)
  }
}

/** How long the typing has to settle before a sync is worth doing. */
const QUIET_MS = 2500;

let timer: ReturnType<typeof setTimeout> | null = null;
let inFlight = false;
let queued = false;

/**
 * Sync after a save, once a burst of autosaves has settled.
 *
 * `onImported` fires only when the vault sent something back, so the caller can
 * refresh without repainting on the common case of a pure one-way write.
 */
export function syncVaultSoon(onImported?: () => void): void {
  if (!getVaultPath()) return; // nothing configured, nothing to do
  if (timer) clearTimeout(timer);
  timer = setTimeout(() => void run(onImported), QUIET_MS);
}

async function run(onImported?: () => void): Promise<void> {
  timer = null;
  const path = getVaultPath();
  if (!path) return;

  // Never overlap: two syncs against one vault would race over the same files.
  if (inFlight) {
    queued = true;
    return;
  }

  inFlight = true;
  try {
    const result = await api.syncObsidian(path);
    const incoming = (result.imported ?? 0) + (result.updated_in_atlas ?? 0);
    if (incoming > 0) onImported?.();
  } catch {
    // Deliberately silent — see the module docstring.
  } finally {
    inFlight = false;
    if (queued) {
      queued = false;
      void run(onImported);
    }
  }
}
