from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .scoring import BaselineModel

DEFAULT_REGISTRY_PATH = Path("docs/steps/step7/output/registry.json")


def _empty_registry() -> dict:
    return {"models": [], "active_model_id": None}


def load_registry(path: str | Path = DEFAULT_REGISTRY_PATH) -> dict:
    registry_path = Path(path)
    if not registry_path.exists():
        return _empty_registry()
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    payload.setdefault("models", [])
    payload.setdefault("active_model_id", None)
    return payload


def save_registry(registry: dict, path: str | Path = DEFAULT_REGISTRY_PATH) -> None:
    registry_path = Path(path)
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(registry, indent=2), encoding="utf-8")


def register_model(
    model_path: str | Path,
    model: BaselineModel,
    *,
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
    tags: list[str] | None = None,
    activate: bool = False,
) -> dict:
    registry = load_registry(registry_path)
    artifact_path = str(Path(model_path))
    model_id = f"{Path(model_path).stem}-{len(registry['models']) + 1:02d}"
    existing = next((item for item in registry["models"] if item["path"] == artifact_path), None)
    entry = {
        "id": existing["id"] if existing else model_id,
        "path": artifact_path,
        "model_type": model.model_type,
        "schema_version": model.schema_version,
        "threshold": model.threshold,
        "feature_count": len(model.feature_keys),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tags": sorted(set(tags or [])),
    }
    if existing is None:
        registry["models"].append(entry)
    else:
        existing.update(entry)
        entry = existing
    registry["models"].sort(key=lambda item: item["id"])
    if activate or registry.get("active_model_id") is None:
        registry["active_model_id"] = entry["id"]
    save_registry(registry, registry_path)
    return entry


def list_models(registry_path: str | Path = DEFAULT_REGISTRY_PATH) -> list[dict]:
    return load_registry(registry_path)["models"]


def activate_model(model_id: str, registry_path: str | Path = DEFAULT_REGISTRY_PATH) -> dict:
    registry = load_registry(registry_path)
    entry = next((item for item in registry["models"] if item["id"] == model_id), None)
    if entry is None:
        raise ValueError(f"unknown model_id: {model_id}")
    registry["active_model_id"] = model_id
    save_registry(registry, registry_path)
    return entry


def resolve_model_path(
    *,
    model_path: str | Path | None = None,
    model_id: str | None = None,
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
) -> str:
    if model_path is not None:
        return str(Path(model_path))

    registry = load_registry(registry_path)
    if model_id is not None:
        entry = next((item for item in registry["models"] if item["id"] == model_id), None)
        if entry is None:
            raise ValueError(f"unknown model_id: {model_id}")
        return entry["path"]

    active_model_id = registry.get("active_model_id")
    if active_model_id is None:
        raise ValueError("no model path provided and registry has no active model")
    entry = next((item for item in registry["models"] if item["id"] == active_model_id), None)
    if entry is None:
        raise ValueError(f"active model not found in registry: {active_model_id}")
    return entry["path"]
