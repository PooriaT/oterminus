from __future__ import annotations

from pathlib import Path


def expand_user_path(value: str) -> str:
    if value == "~":
        return str(Path.home())
    if value.startswith("~/"):
        return str(Path.home()) + value[1:]
    return value
