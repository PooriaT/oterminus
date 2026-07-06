from __future__ import annotations

from pathlib import Path


def expand_user_path(value: str) -> str:
    """Expand only current-user home shorthand that a shell would usually handle."""
    if value == "~":
        return str(Path.home())
    if value.startswith("~/"):
        return str(Path.home()) + value[1:]
    return value
