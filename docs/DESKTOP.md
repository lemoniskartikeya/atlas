# Atlas desktop (Tauri) — Phase 7

Atlas ships as a web app (Vite SPA + FastAPI backend). Tauri wraps that same SPA
in a native desktop window — no rewrite, purely additive.

## Prerequisites (one-time)

The Node side is already scaffolded (`frontend/src-tauri/`). To compile the
native shell you need the Rust toolchain and the Windows C++ build tools:

1. **Rust** — install [rustup](https://rustup.rs). In this session you can run:
   ```
   ! winget install --id Rustlang.Rustup -e
   ```
   then open a new terminal so `cargo` is on `PATH` (or run `rustup default stable`).
2. **MSVC C++ build tools** — the Visual Studio Build Tools with the
   *"Desktop development with C++"* workload (provides `link.exe`):
   ```
   ! winget install --id Microsoft.VisualStudio.2022.BuildTools -e
   ```
   then in the Visual Studio Installer add the *Desktop development with C++*
   workload.
3. **WebView2 runtime** — already present on this machine (Windows 11 ships it).

Verify: `cargo --version` and `where link` should resolve to the MSVC `link.exe`.

## Run the desktop app (dev)

Two processes, same as the web app:

```
# 1) backend
cd backend && ./.venv/Scripts/python -m uvicorn app.main:app --reload

# 2) desktop shell (starts Vite via beforeDevCommand, opens a native window)
cd frontend && npm run tauri dev
```

The Tauri window loads the Vite dev server (`http://localhost:5173`), and Vite
proxies `/api` to the backend on `:8000` — so the desktop app is fully wired
with no code changes. First run compiles the Rust crates (a few minutes);
subsequent runs are fast.

## Build a bundle

```
cd frontend && npm run tauri build
```

**Production caveat (next step).** The bundled build serves the SPA from
Tauri's local protocol, so the app's relative `/api` calls don't reach the
Python backend on their own. Two supported paths:

- **Run the backend separately** and build the SPA with an absolute API base:
  `VITE_API_BASE=http://127.0.0.1:8000 npm run build` before `tauri build`
  (the backend already allows the Tauri origins via CORS).
- **Bundle the backend as a Tauri sidecar** — package the FastAPI app with
  PyInstaller into a single executable, declare it under
  `bundle.externalBin`, and have the Rust shell spawn it on startup. This is
  the fully self-contained option and the recommended follow-up.

## Files

- `frontend/src-tauri/tauri.conf.json` — window, identifier (`app.atlas.desktop`),
  dev URL, bundle config.
- `frontend/src-tauri/src/{main,lib}.rs` — the native entry point.
- `frontend/src-tauri/Cargo.toml` — Rust dependencies.
- `frontend/src-tauri/{target,gen}/` — build output (git-ignored).
