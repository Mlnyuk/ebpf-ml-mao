from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .scoring import BaselineModel

DEFAULT_REGISTRY_PATH = Path("docs/steps/step7/output/registry.json")


def _empty_registry() -> dict:
    return {"models": [], "active_model_id": None}


def _normalize_registry(registry: dict) -> dict:
    registry.setdefault("models", [])
    registry.setdefault("active_model_id", None)
    registry["models"].sort(key=lambda item: item["id"])
    active_model_id = registry.get("active_model_id")
    if active_model_id is not None and not any(item["id"] == active_model_id for item in registry["models"]):
        registry["active_model_id"] = registry["models"][0]["id"] if registry["models"] else None
    return registry


def load_registry(path: str | Path = DEFAULT_REGISTRY_PATH) -> dict:
    registry_path = Path(path)
    if not registry_path.exists():
        return _empty_registry()
    try:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"registry file is not valid JSON: {registry_path}") from exc
    return _normalize_registry(payload)


def save_registry(registry: dict, path: str | Path = DEFAULT_REGISTRY_PATH) -> None:
    registry_path = Path(path)
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(_normalize_registry(registry), indent=2), encoding="utf-8")


def backup_registry(
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
    backup_path: str | Path | None = None,
) -> str:
    source = Path(registry_path)
    if not source.exists():
        raise ValueError(f"registry file does not exist: {source}")
    if backup_path is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = source.with_name(f"{source.stem}-{timestamp}.bak.json")
    else:
        backup = Path(backup_path)
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, backup)
    return str(backup)


def _next_model_id(registry: dict, model_path: str | Path) -> str:
    return f"{Path(model_path).stem}-{len(registry['models']) + 1:02d}"


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
    existing = next((item for item in registry["models"] if item["path"] == artifact_path), None)
    entry = {
        "id": existing["id"] if existing else _next_model_id(registry, model_path),
        "path": artifact_path,
        "model_type": model.model_type,
        "schema_version": model.schema_version,
        "threshold": model.threshold,
        "feature_count": len(model.feature_keys),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tags": sorted(set((existing or {}).get("tags", []) + list(tags or []))),
    }
    if existing is None:
        registry["models"].append(entry)
    else:
        existing.update(entry)
        entry = existing
    if activate or registry.get("active_model_id") is None:
        registry["active_model_id"] = entry["id"]
    save_registry(registry, registry_path)
    return entry


def list_models(registry_path: str | Path = DEFAULT_REGISTRY_PATH) -> list[dict]:
    return load_registry(registry_path)["models"]


def _find_entry(registry: dict, model_id: str) -> dict:
    entry = next((item for item in registry["models"] if item["id"] == model_id), None)
    if entry is None:
        raise ValueError(f"unknown model_id: {model_id}")
    return entry


def activate_model(model_id: str, registry_path: str | Path = DEFAULT_REGISTRY_PATH) -> dict:
    registry = load_registry(registry_path)
    entry = _find_entry(registry, model_id)
    registry["active_model_id"] = model_id
    save_registry(registry, registry_path)
    return entry


def tag_model(
    model_id: str,
    tags: list[str],
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
) -> dict:
    if not tags:
        raise ValueError("at least one tag is required")
    registry = load_registry(registry_path)
    entry = _find_entry(registry, model_id)
    entry["tags"] = sorted(set(entry.get("tags", []) + tags))
    save_registry(registry, registry_path)
    return entry


def prune_registry(
    *,
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
    model_id: str | None = None,
    missing_only: bool = False,
    delete_artifact: bool = False,
    create_backup: bool = True,
) -> dict:
    registry = load_registry(registry_path)
    if create_backup and Path(registry_path).exists():
        backup_path = backup_registry(registry_path)
    else:
        backup_path = None

    removed: list[dict] = []
    kept: list[dict] = []
    for entry in registry["models"]:
        artifact_exists = Path(entry["path"]).exists()
        should_remove = False
        if model_id is not None:
            should_remove = entry["id"] == model_id
        elif missing_only:
            should_remove = not artifact_exists
        if should_remove:
            removed.append(entry)
            if delete_artifact and artifact_exists:
                Path(entry["path"]).unlink()
            continue
        kept.append(entry)

    if model_id is not None and not removed:
        raise ValueError(f"unknown model_id: {model_id}")

    registry["models"] = kept
    registry = _normalize_registry(registry)
    save_registry(registry, registry_path)
    return {
        "removed_count": len(removed),
        "removed": removed,
        "active_model_id": registry.get("active_model_id"),
        "backup_path": backup_path,
    }


def registry_status(registry_path: str | Path = DEFAULT_REGISTRY_PATH) -> dict:
    registry = load_registry(registry_path)
    models = registry["models"]
    return {
        "model_count": len(models),
        "active_model_id": registry.get("active_model_id"),
        "missing_artifact_count": sum(1 for item in models if not Path(item["path"]).exists()),
        "tagged_model_count": sum(1 for item in models if item.get("tags")),
        "model_types": sorted({item["model_type"] for item in models}),
    }


def resolve_model_path(
    *,
    model_path: str | Path | None = None,
    model_id: str | None = None,
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
) -> str:
    if model_path is not None and model_id is not None:
        raise ValueError("provide either model_path or model_id, not both")
    if model_path is not None:
        return str(Path(model_path))

    registry = load_registry(registry_path)
    if model_id is not None:
        entry = _find_entry(registry, model_id)
        return entry["path"]

    active_model_id = registry.get("active_model_id")
    if active_model_id is None:
        raise ValueError("no model path provided and registry has no active model")
    entry = _find_entry(registry, active_model_id)
    return entry["path"]
