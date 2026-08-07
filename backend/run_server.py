"""Entry point for the packaged backend (the Tauri sidecar).

Built into a single executable by PyInstaller and spawned by the desktop shell
on startup, so the user never sees a terminal. Also runnable directly:

    python run_server.py --port 8000
"""
from __future__ import annotations

import argparse
import os
import sys
import threading
import time


def _exit_when_parent_dies(parent_pid: int) -> None:
    """Shut down as soon as the process that launched us is gone.

    A PyInstaller one-file build runs as two processes: the bootloader (the
    desktop shell's direct child) and the real Python process underneath it.
    Killing the child from the shell therefore only reaches the bootloader, and
    the server keeps running — holding port 8000, so the *next* launch silently
    talks to a stale backend. Watching the parent from down here covers every
    exit path uniformly: graceful quit, force-kill, or a crash of the UI.
    """

    def watch() -> None:
        if sys.platform == "win32":
            import ctypes

            SYNCHRONIZE = 0x00100000
            handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, parent_pid)
            if not handle:
                return  # already gone, or not permitted — don't self-terminate
            # Blocks with no polling until the parent exits.
            ctypes.windll.kernel32.WaitForSingleObject(handle, 0xFFFFFFFF)
        else:
            while True:
                try:
                    os.kill(parent_pid, 0)
                except OSError:
                    break
                time.sleep(1.5)
        # os._exit, not sys.exit: this runs off the main thread, where a raised
        # SystemExit would be swallowed and uvicorn would carry on serving.
        os._exit(0)

    threading.Thread(target=watch, daemon=True).start()


def main() -> int:
    parser = argparse.ArgumentParser(prog="atlas-backend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--parent-pid",
        type=int,
        default=None,
        help="Exit automatically when this process exits (used by the desktop shell).",
    )
    args = parser.parse_args()

    if args.parent_pid:
        _exit_when_parent_dies(args.parent_pid)

    # Imported here so --help stays instant and import errors surface with a
    # readable message rather than a bare traceback at module load.
    import uvicorn

    from app.core.config import BASE_DIR, get_settings

    settings = get_settings()
    print(f"atlas-backend: data dir {BASE_DIR}", flush=True)
    print(f"atlas-backend: database {settings.database_url}", flush=True)

    # Bind to loopback only: this process exists to serve the local window, and
    # must never be reachable from the network.
    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        log_level="info",
        # Reload/workers spawn subprocesses, which a frozen single-file build
        # cannot do reliably.
        reload=False,
        workers=1,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
