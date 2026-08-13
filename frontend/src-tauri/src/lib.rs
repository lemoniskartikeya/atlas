//! Atlas desktop shell.
//!
//! Turns the SPA into a real desktop application: frameless window with a
//! custom titlebar, remembered window geometry, a system tray it lives in when
//! closed, a global hotkey to summon it, and OS-native notifications.

use std::sync::Mutex;

use tauri::{
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    Manager, RunEvent, WindowEvent,
};
use tauri_plugin_shell::process::CommandChild;
use tauri_plugin_shell::ShellExt;

/// Handle to the bundled backend process, so it can be shut down with the app.
#[derive(Default)]
struct Backend(Mutex<Option<CommandChild>>);

/// Start the bundled FastAPI backend.
///
/// In development the backend is normally already running (started by hand on
/// :8000), and there may be no compiled sidecar at all — so a failure to spawn
/// is logged and tolerated rather than fatal. In a packaged build this is what
/// makes Atlas a single-icon app with no terminal.
fn spawn_backend(app: &tauri::AppHandle) {
    // The sidecar watches this PID and exits with us. `kill()` alone is not
    // enough: a one-file PyInstaller build puts a bootloader between us and the
    // real server, so killing our direct child would leave the server holding
    // the port. This also covers the paths kill() never sees — a force-quit or
    // a crash of this process.
    let parent_pid = std::process::id().to_string();

    match app.shell().sidecar("atlas-backend") {
        Ok(cmd) => match cmd
            .args(["--port", "8000", "--parent-pid", &parent_pid])
            .spawn()
        {
            Ok((mut rx, child)) => {
                app.state::<Backend>().0.lock().unwrap().replace(child);
                // Drain the sidecar's output into the app log; an unread pipe
                // eventually blocks the child process.
                tauri::async_runtime::spawn(async move {
                    use tauri_plugin_shell::process::CommandEvent;
                    while let Some(event) = rx.recv().await {
                        match event {
                            CommandEvent::Stdout(line) | CommandEvent::Stderr(line) => {
                                log::info!("backend: {}", String::from_utf8_lossy(&line).trim());
                            }
                            CommandEvent::Terminated(payload) => {
                                log::warn!("backend exited: {:?}", payload.code);
                                break;
                            }
                            _ => {}
                        }
                    }
                });
                log::info!("backend sidecar started");
            }
            Err(err) => log::warn!("could not start backend sidecar: {err}"),
        },
        Err(err) => log::warn!("no backend sidecar bundled ({err}) — expecting one on :8000"),
    }
}

/// Stop the backend. Without this the process outlives the window and holds the
/// port, so the next launch silently talks to a stale build.
fn stop_backend(app: &tauri::AppHandle) {
    if let Some(child) = app.state::<Backend>().0.lock().unwrap().take() {
        let _ = child.kill();
        log::info!("backend sidecar stopped");
    }
}

/// Sink for failures raised in the webview.
///
/// Without this a rejected IPC call — a missing capability, say — dies in a
/// console nobody can open in a release build, and the feature just looks
/// broken. That is exactly how the window controls stayed dead: `close()` was
/// never granted `core:window:allow-close`, and the rejection was swallowed.
#[tauri::command]
fn log_ui_error(context: String, message: String) {
    log::error!("ui: {context}: {message}");
}

/// Notes from the webview about the environment it actually ended up in.
///
/// "The window looks wrong on my machine" is unanswerable without knowing the
/// viewport and device pixel ratio it rendered at, and neither is visible from
/// the Rust side.
#[tauri::command]
fn log_ui_info(context: String, message: String) {
    log::info!("ui: {context}: {message}");
}

/// Bring the main window to the foreground, restoring it if minimised.
fn show_main(app: &tauri::AppHandle) {
    if let Some(win) = app.get_webview_window("main") {
        let _ = win.unminimize();
        let _ = win.show();
        let _ = win.set_focus();
    }
}

/// Toggle: if Atlas already has focus, get out of the way; otherwise summon it.
/// That makes the global hotkey a true show/hide rather than a one-way "show".
fn toggle_main(app: &tauri::AppHandle) {
    if let Some(win) = app.get_webview_window("main") {
        let visible = win.is_visible().unwrap_or(false);
        let focused = win.is_focused().unwrap_or(false);
        if visible && focused {
            let _ = win.hide();
        } else {
            show_main(app);
        }
    }
}

fn build_tray(app: &tauri::AppHandle) -> tauri::Result<()> {
    let open = MenuItem::with_id(app, "open", "Open Atlas", true, None::<&str>)?;
    let focus = MenuItem::with_id(app, "focus", "Start a focus session", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "Quit Atlas", true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&open, &focus, &quit])?;

    TrayIconBuilder::with_id("atlas-tray")
        .icon(app.default_window_icon().unwrap().clone())
        .tooltip("Atlas")
        .menu(&menu)
        // Left-click belongs to the OS menu on macOS; elsewhere it opens the app.
        .show_menu_on_left_click(false)
        .on_menu_event(|app, event| match event.id.as_ref() {
            "open" => show_main(app),
            "focus" => {
                show_main(app);
                if let Some(win) = app.get_webview_window("main") {
                    // The window owns routing; ask the SPA to navigate.
                    let _ = win.eval("window.location.hash = ''; window.__atlasNavigate?.('/focus')");
                }
            }
            "quit" => app.exit(0),
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = event
            {
                toggle_main(tray.app_handle());
            }
        })
        .build(app)?;
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let mut builder = tauri::Builder::default().manage(Backend::default());

    // Must be registered before anything else, so a second launch is turned away
    // before it starts a tray icon or a sidecar. Atlas closes to the tray, so
    // re-opening it from the desktop icon while it is already running is the
    // normal case — without this the second instance takes over the window the
    // user sees, then loses its sidecar to the already-bound port 8000 and
    // cannot register the global hotkey either.
    #[cfg(desktop)]
    {
        builder = builder.plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            log::info!("second launch — focusing the running instance");
            show_main(app);
        }));
    }

    builder = builder
        // Remembers size/position/maximised state between launches.
        .plugin(tauri_plugin_window_state::Builder::default().build())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_shell::init());

    #[cfg(desktop)]
    {
        use tauri_plugin_autostart::MacosLauncher;
        use tauri_plugin_global_shortcut::{Code, Modifiers, Shortcut, ShortcutState};

        // Ctrl/Cmd + Shift + A summons Atlas from anywhere.
        let toggle_shortcut = Shortcut::new(Some(Modifiers::CONTROL | Modifiers::SHIFT), Code::KeyA);

        builder = builder
            .plugin(tauri_plugin_autostart::init(
                MacosLauncher::LaunchAgent,
                None,
            ))
            .plugin(
                tauri_plugin_global_shortcut::Builder::new()
                    .with_handler(move |app, shortcut, event| {
                        // Fire on press only; the release event would toggle twice.
                        if shortcut == &toggle_shortcut && event.state() == ShortcutState::Pressed {
                            toggle_main(app);
                        }
                    })
                    .build(),
            );
    }

    builder
        .setup(|app| {
            // Logging is on in release too, to a file in the app's log dir.
            // A desktop app that fails quietly on someone else's machine is
            // undiagnosable otherwise — which is exactly how the launch-at-login
            // toggle managed to do nothing without ever saying why.
            app.handle().plugin(
                tauri_plugin_log::Builder::default()
                    .level(log::LevelFilter::Info)
                    // Stamp lines in the user's own clock, not UTC (the default).
                    // One person reads this log, on this machine, comparing it
                    // against when they remember something going wrong — an
                    // offset they have to add in their head is a bug in a
                    // diagnostic tool. Falls back to UTC if the zone is unknown.
                    // (The mirrored backend JSON keeps its own `ts` in UTC; it
                    // carries an explicit +00:00 offset, so it stays unambiguous.)
                    .timezone_strategy(tauri_plugin_log::TimezoneStrategy::UseLocal)
                    .targets([
                        tauri_plugin_log::Target::new(tauri_plugin_log::TargetKind::Stdout),
                        tauri_plugin_log::Target::new(tauri_plugin_log::TargetKind::LogDir {
                            file_name: Some("atlas".into()),
                        }),
                    ])
                    .build(),
            )?;

            #[cfg(desktop)]
            {
                use tauri_plugin_autostart::ManagerExt;
                match app.autolaunch().is_enabled() {
                    Ok(on) => log::info!("autostart: registered = {on}"),
                    Err(err) => log::warn!("autostart: unavailable ({err})"),
                }
            }

            spawn_backend(app.handle());
            build_tray(app.handle())?;

            #[cfg(desktop)]
            {
                use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut};
                let shortcut =
                    Shortcut::new(Some(Modifiers::CONTROL | Modifiers::SHIFT), Code::KeyA);
                // Non-fatal: another app may already own this combination, and
                // that must not stop Atlas from starting.
                if let Err(err) = app.global_shortcut().register(shortcut) {
                    log::warn!("global shortcut unavailable: {err}");
                }
            }

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![log_ui_error, log_ui_info])
        .on_window_event(|window, event| {
            // Closing the window parks Atlas in the tray instead of quitting —
            // background nudges and the global hotkey keep working. Quit is an
            // explicit choice from the tray menu.
            if let WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                let _ = window.hide();
            }
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app, event| {
            // Covers every way the app can end — tray Quit, OS shutdown, a
            // crash in the window — so the backend never outlives the UI.
            if let RunEvent::Exit = event {
                stop_backend(app);
            }
        });
}
