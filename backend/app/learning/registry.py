"""On-disk model registry: versioned joblib bundles + a JSON metadata index.

A bundle = {model, feature_names, metrics, importances, version, trained_at}.
The loaded bundle is cached in-process and invalidated when a newer version lands.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import joblib

from app.core.config import get_settings

_settings = get_settings()
MODELS_DIR = Path(_settings.data_dir) / "models"
REGISTRY = MODELS_DIR / "registry.json"

_cache: dict = {"version": None, "bundle": None}


def _load_index() -> list[dict]:
    if REGISTRY.exists():
        try:
            return json.loads(REGISTRY.read_text())
        except Exception:
            return []
    return []


def save(
    model,
    feature_names: list[str],
    kept_indices: list[int],
    metrics: dict,
    importances: list[dict],
) -> dict:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    version = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    trained_at = datetime.now(timezone.utc).isoformat()
    filename = f"model_{version}.joblib"
    joblib.dump(
        {
            "model": model,
            "feature_names": feature_names,
            "kept_indices": kept_indices,
            "metrics": metrics,
            "importances": importances,
            "version": version,
            "trained_at": trained_at,
        },
        MODELS_DIR / filename,
    )
    index = _load_index()
    entry = {
        "version": version,
        "trained_at": trained_at,
        "metrics": metrics,
        "path": filename,
        "model_type": type(model).__name__,
    }
    index.append(entry)
    REGISTRY.write_text(json.dumps(index, indent=2))
    _cache["version"] = None  # force reload on next access
    return entry


def latest_meta() -> Optional[dict]:
    index = _load_index()
    return index[-1] if index else None


def latest_bundle() -> Optional[dict]:
    meta = latest_meta()
    if not meta:
        return None
    if _cache["version"] == meta["version"] and _cache["bundle"] is not None:
        return _cache["bundle"]
    path = MODELS_DIR / meta["path"]
    if not path.exists():
        return None
    bundle = joblib.load(path)
    _cache["version"] = meta["version"]
    _cache["bundle"] = bundle
    return bundle
