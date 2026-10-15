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
    "admin_audit.json": ("events", list),
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
                if mid is not None and not isinstance(mid, (str, int)):
                    problems.append(f"matches.json: entry {index} has invalid ID type.")
                    continue
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
                elif group.get("active") and not isinstance(group["active"], dict):
                    problems.append(f"tournaments.json: guild {str(gid)[:24]} active event is malformed.")
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
            if mid is not None and not isinstance(mid, (str, int)):
                raise MaintenanceError("matches.json has a non-scalar match ID.")
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
        verify_backup(name, allow_empty=True)
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


def verify_backup(name: str, *, allow_empty: bool = False) -> dict[str, bytes]:
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
        if not filenames and not allow_empty:
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
    try:
        rollback = create_backup()
    except MaintenanceError:
        # A corrupt current JSON file is the primary reason to need restore.
        # Preserve its raw bytes for forensic recovery, never rewrite it as valid.
        name = "quarantine-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
        directory = BACKUP_DIR / name
        directory.mkdir(parents=True, exist_ok=False)
        for filename in SCHEMAS:
            source = DATA_DIR / filename
            if source.is_file():
                shutil.copy2(source, directory / filename)
        rollback = name
    for filename, raw in contents.items():
        payload = json.loads(raw.decode("utf-8"))
        save_json(str(DATA_DIR / filename), payload)
    LOG.warning("Restored snapshot %s; pre-restore backup %s", name, rollback)
    return rollback


# Admin resets are deliberately scoped to the current Discord server.
# Shared knight/horse records and historical match journals remain untouched.
RESET_SCOPES = {
    "settings": "Clear selected title, active equipment and cosmetic standard. Preserve purchased gear.",
    "inventory": "Also retire owned unlockable equipment WITHOUT refunding previous purchases.",
}


def reset_user_plan(guild_id: int, user_id: int, scope: str = "settings") -> dict:
    if scope not in RESET_SCOPES or guild_id <= 0 or user_id <= 0:
        raise MaintenanceError("Invalid reset scope, guild or player.")
    # Fail closed on malformed JSON: admins should repair/restore first.
    progression = _read("progression.json") or {"guilds": {}}
    titles = _read("titles.json") or {"guilds": {}}
    pgroup = progression.get("guilds", {}).get(str(guild_id), {})
    tgroup = titles.get("guilds", {}).get(str(guild_id), {})
    if not isinstance(pgroup, dict) or not isinstance(tgroup, dict):
        raise MaintenanceError("Server data is malformed; reset blocked.")
    pdata = pgroup.get(str(user_id), {})
    current = tgroup.get(str(user_id))
    if not isinstance(pdata, dict):
        raise MaintenanceError("Target player's progression record is malformed.")
    if current is not None and not isinstance(current, str):
        raise MaintenanceError("Target player's title record is malformed.")
    owned = pdata.get("purchases", {})
    if not isinstance(owned, dict):
        raise MaintenanceError("Target player's purchased inventory is malformed.")
    try:
        costs = [int(p["cost"]) for p in owned.values()]
        if any(cost < 0 for cost in costs):
            raise ValueError("negative purchase value")
        spent = sum(costs)
        if int(pdata.get("retired_spend", 0)) < 0:
            raise ValueError("negative retired spend")
    except (TypeError, ValueError, AttributeError) as exc:
        raise MaintenanceError("Cannot account for historical purchases; reset blocked.") from exc
    changes = []
    if current:
        changes.append("Unequip selected title")
    for key in ("loadout", "horse_barding"):
        if pdata.get(key):
            changes.append("Clear " + key.replace("_", " "))
    if pdata.get("standard") not in (None, "none"):
        changes.append("Unequip cosmetic standard")
    if scope == "inventory" and owned:
        changes.append(f"Retire {len(owned)} unlocked items without refund ({spent} gold already spent)")
    return {
        "scope": scope, "guild_id": guild_id, "user_id": user_id,
        "changes": changes, "retired_purchase_cost": spent if scope == "inventory" else 0,
        "preserved": ["Match history", "Knights and horses", "Treatments/injuries",
                      "Earned gold history", "Tournament entries", "Other servers"],
    }


def reset_user(guild_id: int, user_id: int, scope: str, actor_id: int) -> dict:
    """Apply a confirmed, backup-protected server-only user reset.

    Prevents a reset from laundering previously spent gold back into the wallet.
    Returns the backup ID; the caller must check authorisation and active matches.
    """
    if actor_id <= 0:
        raise MaintenanceError("Invalid reset operator.")
    plan = reset_user_plan(guild_id, user_id, scope)
    progression = _read("progression.json") or {"guilds": {}}
    titles = _read("titles.json") or {"guilds": {}}
    audit = _read("admin_audit.json") or {"events": []}
    if not isinstance(audit.get("events", []), list):
        raise MaintenanceError("Admin audit log is malformed.")
    for root in (progression, titles):
        group = root.get("guilds", {}).get(str(guild_id), {})
        if not isinstance(group, dict):
            raise MaintenanceError("Server data is malformed.")
    backup = create_backup()
    gid, uid = str(guild_id), str(user_id)
    record = progression.setdefault("guilds", {}).setdefault(gid, {}).setdefault(uid, {})
    record.pop("loadout", None)
    record.pop("horse_barding", None)
    record["standard"] = "none"
    if scope == "inventory":
        retired = int(record.get("retired_spend", 0))
        if retired < 0:
            raise MaintenanceError("Negative retired spending encountered.")
        record["retired_spend"] = retired + plan["retired_purchase_cost"]
        record["purchases"] = {}
    titles.setdefault("guilds", {}).setdefault(gid, {}).pop(uid, None)
    audit.setdefault("events", []).append({
        "at": _now(), "action": "reset_user", "guild_id": guild_id,
        "target_user_id": user_id, "admin_user_id": actor_id,
        "scope": scope, "backup": backup,
        "changes": plan["changes"],
    })
    # Each file is atomic, but multi-file operations are not a transaction.
    # Admin backup permits manual restore if the process stops mid-operation.
    save_json(str(DATA_DIR / "progression.json"), progression)
    save_json(str(DATA_DIR / "titles.json"), titles)
    save_json(str(DATA_DIR / "admin_audit.json"), audit)
    LOG.warning("Admin reset guild=%s player=%s admin=%s scope=%s backup=%s",
                guild_id, user_id, actor_id, scope, backup)
    return {**plan, "backup": backup}
