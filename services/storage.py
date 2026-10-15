"""JSON file persistence with uniquely staged, durable atomic replacements.

This protects individual JSON writes from partial files. It is not a distributed
transaction or a substitute for a single running bot instance/persistent disk.
"""
from __future__ import annotations

import json
import os
import tempfile
from typing import Any, Dict


def ensure_dir(path: str) -> None:
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)


def load_json(path: str, default: Dict[str, Any]) -> Dict[str, Any]:
    ensure_dir(path)
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def save_json(path: str, data: Dict[str, Any]) -> None:
    """Flush JSON to a unique temporary file then atomically replace target."""
    ensure_dir(path)
    directory = os.path.dirname(os.path.abspath(path))
    fd, temporary = tempfile.mkstemp(prefix=".joust-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
