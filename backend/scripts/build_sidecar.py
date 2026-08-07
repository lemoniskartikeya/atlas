"""Build the backend into the sidecar binary the Tauri shell bundles.

    python scripts/build_sidecar.py

Runs PyInstaller against atlas-backend.spec, then copies the result into
frontend/src-tauri/binaries/ under the ``<name>-<target-triple>`` filename
Tauri's ``bundle.externalBin`` requires (Tauri appends the triple so one bundle
config can serve every platform).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
BINARIES = BACKEND.parent / "frontend" / "src-tauri" / "binaries"
NAME = "atlas-backend"


def target_triple() -> str:
    """Ask rustc, so the name always matches what Tauri will look for."""
    for rustc in ("rustc", str(Path.home() / ".cargo" / "bin" / "rustc.exe")):
        try:
            out = subprocess.run(
                [rustc, "-vV"], capture_output=True, text=True, check=True
            ).stdout
        except (OSError, subprocess.CalledProcessError):
            continue
        for line in out.splitlines():
            if line.startswith("host:"):
                return line.split(":", 1)[1].strip()
    raise SystemExit("Could not determine the Rust target triple — is rustc on PATH?")


def main() -> int:
    triple = target_triple()
    print(f"target triple: {triple}")

    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "atlas-backend.spec",
            "--noconfirm",
            "--distpath",
            "dist-sidecar",
            "--workpath",
            "build-sidecar",
        ],
        cwd=BACKEND,
        check=True,
    )

    suffix = ".exe" if sys.platform == "win32" else ""
    built = BACKEND / "dist-sidecar" / f"{NAME}{suffix}"
    if not built.exists():
        raise SystemExit(f"Expected {built} to exist after the PyInstaller run.")

    BINARIES.mkdir(parents=True, exist_ok=True)
    dest = BINARIES / f"{NAME}-{triple}{suffix}"
    shutil.copy2(built, dest)
    print(f"sidecar -> {dest}  ({dest.stat().st_size / 1_048_576:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
