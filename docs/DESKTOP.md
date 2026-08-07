# Atlas desktop (Tauri)

Atlas is a desktop application. The same Vite SPA and FastAPI backend that run
in a browser during development are packaged into a single installable app: one
icon, no terminal, no `localhost` in sight.

## What "desktop" means here

- **Self-contained.** The FastAPI backend is compiled to a single executable by
  PyInstaller and bundled as a Tauri *sidecar*. The shell starts it on launch
  and shuts it down on exit.
- **Native chrome.** The OS title bar is off (`decorations: false`); the app
  draws its own (`components/layout/Titlebar.tsx`). Window size, position, and
  maximised state persist between launches.
- **Lives in the tray.** Closing the window hides it rather than quitting, so
  nudges keep working. Quit for real from the tray menu.
- **Global hotkey.** `Ctrl/Cmd + Shift + A` summons or hides Atlas from anywhere.
- **Native notifications.** Real OS toasts, not Web Notifications — they arrive
  even when the window is hidden.
- **Launch at login**, toggleable in Settings → Desktop.

Everything degrades gracefully in a browser: `lib/desktop.ts` feature-detects
the Tauri runtime and each capability becomes a no-op or its web equivalent.

## Prerequisites (one-time)

1. **Rust** — install [rustup](https://rustup.rs):
   `winget install --id Rustlang.Rustup -e`
   (winget does not refresh `PATH`; open a new terminal, or call
   `~/.cargo/bin/cargo.exe` directly.)
2. **MSVC C++ build tools** — provides `link.exe`:
   `winget install --id Microsoft.VisualStudio.2022.BuildTools -e --override "--add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"`
3. **WebView2 runtime** — already present on Windows 11.

Verify with `cargo --version`.

## Develop

```
# 1) backend (the dev app talks to this directly)
cd backend && ./.venv/Scripts/python -m uvicorn app.main:app --reload

# 2) desktop shell — starts Vite via beforeDevCommand, opens a native window
cd frontend && npm run tauri dev
```

In dev the Tauri window loads the Vite dev server and Vite proxies `/api` to
`:8000`. The shell still *tries* to spawn a sidecar; if none is built, it logs a
warning and carries on against the backend you started by hand.

## Build the installers

```
# 1) compile the backend into the sidecar binary (~25 MB)
cd backend && ./.venv/Scripts/python scripts/build_sidecar.py

# 2) build the app + installers
cd frontend && npm run tauri build
```

Output:

- `frontend/src-tauri/target/release/app.exe` — the app itself
- `…/target/release/bundle/msi/Atlas_0.1.0_x64_en-US.msi`
- `…/target/release/bundle/nsis/Atlas_0.1.0_x64-setup.exe`

`build_sidecar.py` asks `rustc` for the host target triple and names the binary
`atlas-backend-<triple>.exe`, which is the form `bundle.externalBin` requires.

The packaged SPA is built with `--mode tauri`, which loads `frontend/.env.tauri`
(`VITE_API_BASE=http://127.0.0.1:8000`). Relative `/api` calls cannot work from
the `tauri://` origin, so the absolute base is required; the backend's CORS
config already allows the Tauri origins.

## Where the packaged app keeps data

A frozen build writes to a per-user directory rather than next to the
executable, because PyInstaller unpacks a one-file build into a temp folder that
is deleted on exit:

| Platform | Location |
| --- | --- |
| Windows | `%APPDATA%\Atlas` |
| macOS | `~/Library/Application Support/Atlas` |
| Linux | `$XDG_DATA_HOME/Atlas` (or `~/.local/share/Atlas`) |

That directory holds `atlas.db`, `.env` (including the AI-coach API key), and
trained models. See `FROZEN` / `BASE_DIR` in `backend/app/core/config.py`.

## Process lifetime

A one-file PyInstaller build runs as *two* processes: a bootloader and the real
Python process beneath it. The shell's direct child is the bootloader, so
killing it would leave the server running and holding port 8000 — the next
launch would then silently talk to a stale backend.

The sidecar is therefore started with `--parent-pid <shell pid>` and watches
that process (`WaitForSingleObject` on Windows, a `kill(pid, 0)` poll
elsewhere), exiting the moment its parent does. This covers graceful quit,
force-kill, and a crash of the UI alike — verified by force-killing `app.exe`
and confirming port 8000 is released.

## The ML layer in packaged builds

`atlas-backend.spec` excludes scikit-learn, numpy, scipy, and friends to keep
the bundle small. The packaged backend logs `ml.router_unavailable` and every
ML-backed surface falls back to its heuristic path — by design. Remove those
entries from `excludes` if you want a bundle with the ML layer baked in.

## Files

- `frontend/src-tauri/tauri.conf.json` — window, identifier (`app.atlas.desktop`),
  `externalBin`, bundle config.
- `frontend/src-tauri/src/lib.rs` — tray, hotkey, window events, sidecar lifecycle.
- `frontend/src-tauri/capabilities/default.json` — Tauri v2 permissions.
- `frontend/src/lib/desktop.ts` — the browser-safe wrapper around all of it.
- `backend/run_server.py` — sidecar entry point.
- `backend/atlas-backend.spec`, `backend/scripts/build_sidecar.py` — packaging.
