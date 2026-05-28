from __future__ import annotations

import json
import os
from typing import Any, Dict


def ensure_dir(path: str) -> None:
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)


def load_json(path: str, default: Dict[str, Any]) -> Dict[str, Any]:
    ensure_dir(path)

    if not os.path.exists(path):
        return default

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data: Dict[str, Any]) -> None:
    ensure_dir(path)

    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    os.replace(tmp, path)