/**
 * Desktop integration.
 *
 * Every export here is safe to call in a plain browser: Atlas still runs as a
 * web app during development, so each capability degrades to a no-op or to the
 * web equivalent rather than throwing. Tauri modules are imported lazily so the
 * browser bundle never evaluates them.
 */

/** True when running inside the Tauri shell rather than a browser tab. */
export const isDesktop = (): boolean =>
  typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;

/* ------------------------------------------------------------ window controls */

async function appWindow() {
  const { getCurrentWindow } = await import("@tauri-apps/api/window");
  return getCurrentWindow();
}

/**
 * Report a webview-side failure into the desktop log.
 *
 * A release build has no console anyone can open, so an IPC rejection that is
 * only `console.error`d is invisible — the feature just looks broken with no
 * trail. Never throws: a logger that can fail is worse than no logger.
 */
export async function reportDesktopError(context: string, err: unknown): Promise<void> {
  const message =
    err instanceof Error ? `${err.name}: ${err.message}` : String(err ?? "unknown error");
  console.error(`[atlas] ${context}: ${message}`);
  if (!isDesktop()) return;
  try {
    const { invoke } = await import("@tauri-apps/api/core");
    await invoke("log_ui_error", { context, message });
  } catch {
    /* the log sink itself is unavailable — nothing more we can do */
  }
}

/** Note something into the desktop log. Never throws. */
export async function reportDesktopInfo(context: string, message: string): Promise<void> {
  if (!isDesktop()) return;
  try {
    const { invoke } = await import("@tauri-apps/api/core");
    await invoke("log_ui_info", { context, message });
  } catch {
    /* logging is best effort */
  }
}

/**
 * Open a URL in the user's real browser rather than this webview.
 *
 * Google refuses to serve its sign-in page inside an embedded webview — the
 * user can't see the address bar there, so they can't tell who is asking for
 * their password. In a browser build a new tab is already the real browser.
 */
export async function openExternal(url: string): Promise<void> {
  if (!isDesktop()) {
    window.open(url, "_blank", "noopener,noreferrer");
    return;
  }
  const { invoke } = await import("@tauri-apps/api/core");
  await invoke("open_external", { url });
}

/**
 * Subscribe to the shell giving up on the backend.
 *
 * The splash used to spin for its full 25-second timeout and then guess at the
 * cause, while the shell had known the real reason within two seconds — it can
 * read the backend's dying words. Returns an unsubscribe function; resolves to
 * a no-op in a browser, where there is no shell to hear from.
 */
export async function onBackendFailed(
  handler: (reason: string) => void,
): Promise<() => void> {
  if (!isDesktop()) return () => {};
  try {
    const { listen } = await import("@tauri-apps/api/event");
    return await listen<string>("backend-failed", (event) => handler(event.payload));
  } catch {
    return () => {};
  }
}

/**
 * Ask the OS for a folder.
 *
 * Returns null when the user cancels, and also in a browser — there is no way
 * to get a real filesystem path from a web page, so the caller keeps its text
 * field as the way in rather than pretending the button is missing.
 */
export async function pickFolder(title: string): Promise<string | null> {
  if (!isDesktop()) return null;
  const { open } = await import("@tauri-apps/plugin-dialog");
  const picked = await open({ directory: true, multiple: false, title });
  return typeof picked === "string" ? picked : null;
}

export const windowControls = {
  minimize: async () => {
    if (isDesktop()) await (await appWindow()).minimize();
  },
  toggleMaximize: async () => {
    if (isDesktop()) await (await appWindow()).toggleMaximize();
  },
  /** Closing parks Atlas in the tray — the Rust side intercepts the request. */
  close: async () => {
    if (isDesktop()) await (await appWindow()).close();
  },
  isMaximized: async (): Promise<boolean> => {
    if (!isDesktop()) return false;
    return (await appWindow()).isMaximized();
  },
  /** Subscribe to resize so the maximise/restore glyph stays truthful. */
  onResized: async (fn: () => void): Promise<() => void> => {
    if (!isDesktop()) return () => {};
    return (await appWindow()).onResized(fn);
  },
  /**
   * Drag the window from the custom titlebar.
   *
   * `-webkit-app-region: drag` is a Chromium feature that WebView2 does not
   * reliably honour, so the CSS alone leaves the titlebar unable to move the
   * window. Tauri's own `startDragging` is the supported path.
   */
  startDragging: async () => {
    if (isDesktop()) await (await appWindow()).startDragging();
  },
};

/* -------------------------------------------------------------- notifications */

/**
 * Send a notification through the OS.
 *
 * On desktop this is a real native toast (it shows even when Atlas is parked in
 * the tray). In a browser it falls back to the Web Notifications API, which is
 * what the notification centre used before.
 */
export async function notify(title: string, body: string): Promise<void> {
  if (isDesktop()) {
    const { isPermissionGranted, requestPermission, sendNotification } = await import(
      "@tauri-apps/plugin-notification"
    );
    let granted = await isPermissionGranted();
    if (!granted) granted = (await requestPermission()) === "granted";
    if (granted) sendNotification({ title, body });
    return;
  }

  if (typeof Notification !== "undefined" && Notification.permission === "granted") {
    new Notification(title, { body });
  }
}

export async function requestNotificationPermission(): Promise<boolean> {
  if (isDesktop()) {
    const { isPermissionGranted, requestPermission } = await import(
      "@tauri-apps/plugin-notification"
    );
    return (await isPermissionGranted()) || (await requestPermission()) === "granted";
  }
  if (typeof Notification === "undefined") return false;
  if (Notification.permission === "granted") return true;
  return (await Notification.requestPermission()) === "granted";
}

/* ------------------------------------------------------------------ autostart */

/** Windows reports a missing registry value as "cannot find the file". */
function isMissingEntryError(err: unknown): boolean {
  return /cannot find the file|not found|NotFound|os error 2\b/i.test(String(err));
}

export const autostart = {
  isEnabled: async (): Promise<boolean> => {
    if (!isDesktop()) return false;
    const { isEnabled } = await import("@tauri-apps/plugin-autostart");
    return isEnabled();
  },

  /**
   * Register or unregister launch-at-login.
   *
   * Turning it *off* is made idempotent on purpose: the underlying crate
   * deletes a registry value outright, which throws when the value isn't there.
   * Since the UI can be out of sync with the registry (Windows lets the user
   * disable a startup entry from Task Manager behind the app's back), a
   * "disable something already disabled" call is a normal thing to happen and
   * shouldn't surface as an error.
   */
  set: async (on: boolean): Promise<void> => {
    if (!isDesktop()) return;
    const { enable, disable } = await import("@tauri-apps/plugin-autostart");
    if (on) {
      await enable();
      return;
    }
    try {
      await disable();
    } catch (err) {
      if (!isMissingEntryError(err)) throw err;
    }
  },
};
