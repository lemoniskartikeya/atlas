# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Atlas backend sidecar.

Produces a single executable that the Tauri shell spawns on startup. Built via
`scripts/build_sidecar.py`, which also renames the result to the
`<name>-<target-triple>` form Tauri requires for `bundle.externalBin`.
"""

from PyInstaller.utils.hooks import collect_submodules

# Uvicorn and the app's own package are reached by string/dotted path at
# runtime ("app.main:app"), so static analysis cannot see them.
hiddenimports = [
    *collect_submodules("uvicorn"),
    *collect_submodules("app"),
    "anyio",
    # Alembic ships the migration environment; keeping it importable means the
    # packaged backend can upgrade its own schema on first launch.
    *collect_submodules("alembic"),
]

a = Analysis(
    ["run_server.py"],
    pathex=["."],
    binaries=[],
    datas=[
        # Migration scripts are data files, not modules — without these the
        # packaged app cannot create or upgrade its database.
        ("app/migrations", "app/migrations"),
        ("alembic.ini", "."),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    # Heavy optional stacks stay out: the ML layer is installed separately and
    # would multiply the bundle size for a feature most launches never touch.
    excludes=["sklearn", "scipy", "numpy", "pandas", "joblib", "matplotlib", "tkinter"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="atlas-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
