"""JoustingBot v0.9 — cautious local backups, validation, repairs and restore.

Only known application JSON files are managed. Repairs are deliberately limited to
missing files/containers and byte-identical duplicated match entries. A damaged
JSON file or conflicting ID is never silently overwritten.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from services.storage import save_json

LOG = logging.getLogger(__name__)
DATA_DIR = Path("storage")
BACKUP_DIR = Path("backups")
SCHEMAS = {
    "knights.json": ("knights", dict),
    "horses.json": ("horses", dict),
    "matches.json": ("matches", list),
    "titles.json": ("guilds", dict),
    "progression.json": ("guilds", dict),
    "tournaments.json": ("guilds", dict),
}
BACKUP_RE = re.compile(r"^bkp-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}$")


class MaintenanceError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read(name: str) -> dict | None:
    path = DATA_DIR / name
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as file:
            value = json.load(file)
    except (ValueError, OSError) as exc:
        raise MaintenanceError(f"{name}: cannot read JSON ({type(exc).__name__}).") from exc
    if not isinstance(value, dict):
        raise MaintenanceError(f"{name}: root must be a JSON object.")
    field, kind = SCHEMAS[name]
    if field in value and not isinstance(value[field], kind):
        raise MaintenanceError(f"{name}: {field} must be {kind.__name__}.")
    return value


def inspect() -> dict:
    files, problems, warnings = [], [], []
    for name, (key, _kind) in SCHEMAS.items():
        path = DATA_DIR / name
        try:
            obj = _read(name)
        except MaintenanceError as exc:
            files.append((name, "ERROR"))
            problems.append(str(exc))
            continue
        if obj is None:
            files.append((name, "MISSING"))
            warnings.append(f"{name}: file is missing (can initialize).")
            continue
        files.append((name, "OK"))
        if key not in obj:
            warnings.append(f"{name}: missing {key} container (can initialize).")
        if name == "matches.json":
            ids = {}
            for index, match in enumerate(obj.get("matches", [])):
                if not isinstance(match, dict):
                    problems.append(f"matches.json: entry {index} is not an object.")
                    continue
                mid = match.get("id")
                if not mid:
                    warnings.append(f"matches.json: entry {index} has no ID; left untouched.")
                    continue
                if mid in ids:
                    if ids[mid] != match:
                        problems.append(f"matches.json: conflicting duplicate ID {str(mid)[:40]}.")
                    else:
                        warnings.append(f"matches.json: identical repeated ID {str(mid)[:40]} (can deduplicate).")
                else:
                    ids[mid] = match
        if name == "tournaments.json":
            for gid, group in obj.get("guilds", {}).items():
                if not isinstance(group, dict):
                    problems.append(f"tournaments.json: guild {str(gid)[:24]} is not an object.")
                elif group.get("active") and group["active"].get("status") not in ("registration", "running"):
                    warnings.append(f"tournaments.json: guild {str(gid)[:24]} has an unusual active status; review manually.")
    return {"files": files, "errors": problems, "warnings": warnings, "healthy": not problems}


def _safe_state() -> tuple[dict[str, dict | None], list[str]]:
    contents, changes = {}, []
    for name, (field, kind) in SCHEMAS.items():
        current = _read(name)
        contents[name] = current
        if current is None:
            changes.append(f"Create missing {name}.")
        elif field not in current:
            changes.append(f"Initialize {field} in {name}.")
    matches = contents["matches.json"]
    if matches is not None and isinstance(matches.get("matches"), list):
        seen, duplicates = {}, 0
        for item in matches["matches"]:
            if not isinstance(item, dict):
                raise MaintenanceError("matches.json includes a non-object entry; manual review required.")
            mid = item.get("id")
            if not mid:
                continue
            if mid in seen:
                if seen[mid] != item:
                    raise MaintenanceError("matches.json includes conflicting IDs; cannot safely repair.")
                duplicates += 1
            else:
                seen[mid] = item
        if duplicates:
            changes.append(f"Remove {duplicates} byte-equivalent duplicate match record(s).")
    return contents, changes


def repair(*, apply: bool = False) -> dict:
    check = inspect()
    if check["errors"]:
        raise MaintenanceError("Unsafe repair blocked: " + "; ".join(check["errors"][:3]))
    contents, planned = _safe_state()
    if not apply or not planned:
        return {"changes": planned, "applied": False, "backup": None}
    backup = create_backup()
    for name, (field, kind) in SCHEMAS.items():
        data = contents[name]
        if data is None:
            save_json(str(DATA_DIR / name), {field: kind()})
            continue
        changed = False
        if field not in data:
            data[field] = kind()
            changed = True
        if name == "matches.json":
            unique, ids = [], set()
            for item in data["matches"]:
                mid = item.get("id")
                if mid and mid in ids:
                    changed = True
                    continue
                unique.append(item)
                if mid:
                    ids.add(mid)
            if changed:
                data["matches"] = unique
        if changed:
            save_json(str(DATA_DIR / name), data)
    LOG.warning("Applied safe JSON repairs: %s; backup %s", planned, backup)
    return {"changes": planned, "applied": True, "backup": backup}


def create_backup() -> str:
    """Verify all present files, write immutable snapshots and SHA256 manifest."""
    state = inspect()
    if state["errors"]:
        raise MaintenanceError("Backup rejected due to invalid files: " + "; ".join(state["errors"][:2]))
    name = "bkp-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    target = BACKUP_DIR / name
    target.mkdir(parents=True, exist_ok=False)
    copied = {}
    try:
        for filename in SCHEMAS:
            src = DATA_DIR / filename
            if not src.is_file():
                continue
            contents = src.read_bytes()
            (target / filename).write_bytes(contents)
            copied[filename] = _hash(contents)
        manifest = {"schema": 1, "created_at": _now(), "files": copied}
        (target / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        verify_backup(name)
    except Exception:
        shutil.rmtree(target, ignore_errors=True)
        raise
    LOG.info("Backup created: %s (%s files)", name, len(copied))
    return name


def backup_names(limit: int = 20) -> list[str]:
    if not BACKUP_DIR.exists():
        return []
    names = [p.name for p in BACKUP_DIR.iterdir() if p.is_dir() and BACKUP_RE.fullmatch(p.name)]
    return sorted(names, reverse=True)[:limit]


def verify_backup(name: str) -> dict[str, bytes]:
    if not BACKUP_RE.fullmatch(name):
        raise MaintenanceError("Invalid backup identifier.")
    folder = BACKUP_DIR / name
    if not folder.is_dir() or folder.is_symlink():
        raise MaintenanceError("Backup not found.")
    try:
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        filenames = manifest["files"]
        if manifest.get("schema") != 1 or not isinstance(filenames, dict):
            raise ValueError("invalid manifest")
        if not filenames:
            raise ValueError("empty backup")
        contents = {}
        for filename, digest in filenames.items():
            if filename not in SCHEMAS:
                raise ValueError("unrecognized filename")
            path = folder / filename
            if path.is_symlink():
                raise ValueError("symlink is not a backup")
            raw = path.read_bytes()
            if _hash(raw) != digest:
                raise ValueError("checksum mismatch")
            value = json.loads(raw.decode("utf-8"))
            field, kind = SCHEMAS[filename]
            if not isinstance(value, dict) or (field in value and not isinstance(value[field], kind)):
                raise ValueError("backup JSON has unexpected structure")
            contents[filename] = raw
        return contents
    except (OSError, ValueError, KeyError, TypeError, UnicodeError) as exc:
        raise MaintenanceError(f"Backup verification failed: {type(exc).__name__}.") from exc


def restore_backup(name: str) -> str:
    """Preflight full snapshot; make an emergency backup first, then restore.

    Restore is best-effort across files (each file replacement is atomic). Only
    perform while no matches/other writes are active on this bot instance.
    """
    contents = verify_backup(name)
    rollback = create_backup()
    for filename, raw in contents.items():
        payload = json.loads(raw.decode("utf-8"))
        save_json(str(DATA_DIR / filename), payload)
    LOG.warning("Restored snapshot %s; pre-restore backup %s", name, rollback)
    return rollback
