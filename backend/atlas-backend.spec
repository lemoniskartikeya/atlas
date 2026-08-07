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
    # scikit-learn resolves several internals at runtime that static analysis
    # misses, and the app itself only ever imports it lazily.
    *collect_submodules("sklearn"),
    "joblib",
    "scipy.special._cdflib",
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
    # The ML stack IS bundled. It was excluded to keep the download small, but
    # that shipped a desktop app where the what-if simulator, the forecast card
    # and model-driven recommendations could never work — /ml/* wasn't even
    # mounted, so the UI offered a "Train model" button that 404'd. The ML layer
    # is the product's differentiator; a bigger installer is the right trade.
    excludes=["pandas", "matplotlib", "tkinter", "IPython", "pytest"],
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
