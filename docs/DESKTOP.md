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

## Install and launch

The normal way to run Atlas is to install it — you should never need a terminal.

1. Run `frontend/src-tauri/target/release/bundle/nsis/Atlas_0.1.0_x64-setup.exe`.
   It installs **for the current user only**, so Windows does not ask for admin
   rights (`bundle.windows.nsis.installMode: "currentUser"`).
2. Atlas lands in `%LOCALAPPDATA%\Atlas`, with a **Start Menu** entry and a
   **Desktop shortcut**.

After that, launch it any of these ways:

- the **Desktop** icon
- **Start menu** → type "Atlas"
- **`Ctrl + Shift + A`** from anywhere, once Atlas is running (it lives in the
  tray, so this summons it back after you close the window)

Closing the window hides it to the tray; quit for real from the tray menu.
Nothing else needs to be started — the backend is bundled and boots with the app
(`BackendGate` holds the UI on a splash until `/health` answers).

The MSI (`bundle/msi/Atlas_0.1.0_x64_en-US.msi`) is the same app for
machine-wide or managed deployment; the NSIS setup is the one to use day to day.

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
# 1) compile the backend into the sidecar binary (~75 MB, includes the ML stack)
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

The ML stack (scikit-learn, numpy, scipy, joblib) **is bundled**. It was
originally excluded to keep the installer small, but that shipped a desktop app
where the what-if simulator, the forecast card, and model-driven
recommendations could never work — `/ml/*` was not even mounted, so the UI
offered a "Train model" button that 404'd. The ML layer is the product's
differentiator; a ~75 MB sidecar (up from ~25 MB) is the right trade.

`pandas`, `matplotlib`, `IPython`, `pytest`, and `tkinter` remain excluded —
nothing imports them.

## Logs

Release builds log to the app's log directory, not just debug builds:

    %LOCALAPPDATA%\app.atlas.desktop\logs\Atlas.log

It captures the shell's own events (tray, hotkey, autostart state, sidecar
lifecycle) and mirrors the backend's stdout. A desktop app that fails quietly
on someone else's machine is otherwise undiagnosable.

Line timestamps are **local time** (`TimezoneStrategy::UseLocal`; the plugin
defaults to UTC). The backend's mirrored JSON keeps its own `ts` in UTC, which
is explicit in the value's `+00:00` offset. Note that `timezone_strategy()`
also *replaces the line format* — that is documented plugin behaviour, not a
mistake — so lines written from this point on read `[date][LEVEL][target]`
where older ones read `[date][target][LEVEL]`.

**The trap that made this log useless for its first five weeks:** Alembic's
`env.py` calls `logging.config.fileConfig`, and Python disables *every logger
the .ini does not name* unless you pass `disable_existing_loggers=False`. Since
`ensure_schema` runs migrations in-process at startup, that call silenced every
`uvicorn.*` and `atlas.*` logger about three seconds into each launch — so the
log recorded the boot and then nothing at all: no "startup complete", no
`schema.ready`, no job runs, no errors, not even shutdown. The tell is a log
whose last line is always Alembic's `Will assume non-transactional DDL`.
`core/schema.py` now sets `cfg.attributes["configure_logger"] = False` (Alembic's
escape hatch for programmatic use) so the app keeps the logging it configured,
and `env.py` passes `disable_existing_loggers=False` so the CLI path cannot do
it either. Pinned by `tests/test_schema.py`.

## Launch at login

Handled by `tauri-plugin-autostart`, which writes `HKCU\...\CurrentVersion\Run`
on Windows. Two sharp edges worth knowing, both handled in `lib/desktop.ts` and
`DesktopCard.tsx`:

- `disable()` deletes the registry value outright and **throws when it isn't
  there**, so disabling something already disabled raises. That call is now
  idempotent.
- `is_enabled()` returns `run_key_present && task_manager_not_disabled`.
  Windows keeps a separate "Startup Apps" override next to the Run key, and its
  write is best-effort inside the crate. So `enable()` can succeed while
  `is_enabled()` still reports false — indistinguishable from a silent no-op.
  The toggle now reads the state back after writing and, on a mismatch, points
  at Task Manager → Startup apps instead of failing quietly.

## The icon

`frontend/src-tauri/app-icon.svg` is the single source of truth: a terracotta
tile (`#C2703D`) carrying the paper-white Atlas "A" — the warm-editorial accent
and display letterform, so the taskbar icon and the app agree. Regenerate every
platform size with:

    cd frontend && npx tauri icon src-tauri/app-icon.svg

That rewrites `src-tauri/icons/` (PNG set, `icon.ico`, `icon.icns`). It also
emits `android/` and `ios/` folders — delete them; Atlas is desktop-only.

The same geometry is drawn in-app by `components/ui/atlas-mark.tsx` (sidebar,
login, splash, titlebar) and served to browsers as `frontend/public/favicon.svg`.
If the glyph changes, change it in all three.

## Files

- `frontend/src-tauri/app-icon.svg` — icon source; regenerate with `tauri icon`.
- `frontend/src-tauri/tauri.conf.json` — window, identifier (`app.atlas.desktop`),
  `externalBin`, bundle config.
- `frontend/src-tauri/src/lib.rs` — tray, hotkey, window events, sidecar lifecycle.
- `frontend/src-tauri/capabilities/default.json` — Tauri v2 permissions.
- `frontend/src/lib/desktop.ts` — the browser-safe wrapper around all of it.
- `backend/run_server.py` — sidecar entry point.
- `backend/atlas-backend.spec`, `backend/scripts/build_sidecar.py` — packaging.
