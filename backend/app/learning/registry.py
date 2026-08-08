"""On-disk model registry: versioned joblib bundles + a JSON metadata index.

A bundle = {model, feature_names, metrics, importances, version, trained_at}.
The loaded bundle is cached in-process and invalidated when a newer version lands.

**One registry per account.** Bundles live under ``data/models/<user_id>/`` so a
model only ever sees the logs of the account it was fitted on — the same
boundary the database enforces. A new account simply has no registry yet and
falls back to heuristics until it has enough history to train, which is the
existing untrained-model path and needs no special handling.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import joblib

from app.core.config import get_settings

_settings = get_settings()
MODELS_ROOT = Path(_settings.data_dir) / "models"

#: ``{user_id: {"version": ..., "bundle": ...}}`` — one slot per account so a
#: multi-account session can't serve one user's model to another.
_cache: dict[str, dict] = {}


def models_dir(user_id: str) -> Path:
    """Where one account's model artifacts live."""
    return MODELS_ROOT / user_id


def registry_path(user_id: str) -> Path:
    return models_dir(user_id) / "registry.json"


def _load_index(user_id: str) -> list[dict]:
    path = registry_path(user_id)
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            return []
    return []


def save(
    user_id: str,
    model,
    feature_names: list[str],
    kept_indices: list[int],
    metrics: dict,
    importances: list[dict],
) -> dict:
    directory = models_dir(user_id)
    directory.mkdir(parents=True, exist_ok=True)
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
        directory / filename,
    )
    index = _load_index(user_id)
    entry = {
        "version": version,
        "trained_at": trained_at,
        "metrics": metrics,
        "path": filename,
        "model_type": type(model).__name__,
    }
    index.append(entry)
    registry_path(user_id).write_text(json.dumps(index, indent=2))
    _cache.pop(user_id, None)  # force reload on next access
    return entry


def latest_meta(user_id: str) -> Optional[dict]:
    index = _load_index(user_id)
    return index[-1] if index else None


def latest_bundle(user_id: str) -> Optional[dict]:
    meta = latest_meta(user_id)
    if not meta:
        return None
    slot = _cache.get(user_id)
    if slot and slot["version"] == meta["version"] and slot["bundle"] is not None:
        return slot["bundle"]
    path = models_dir(user_id) / meta["path"]
    if not path.exists():
        return None
    bundle = joblib.load(path)
    _cache[user_id] = {"version": meta["version"], "bundle": bundle}
    return bundle
