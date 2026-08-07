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

export const autostart = {
  isEnabled: async (): Promise<boolean> => {
    if (!isDesktop()) return false;
    const { isEnabled } = await import("@tauri-apps/plugin-autostart");
    return isEnabled();
  },
  set: async (on: boolean): Promise<void> => {
    if (!isDesktop()) return;
    const { enable, disable } = await import("@tauri-apps/plugin-autostart");
    if (on) await enable();
    else await disable();
  },
};
