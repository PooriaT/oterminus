from __future__ import annotations

from importlib import metadata

_DISTRIBUTION_NAME = "oterminus"
_LOCAL_VERSION = "0.0.0+local"


def get_version() -> str:
    """Return the installed OTerminus package version.

    Package metadata is authoritative for installed wheels and editable installs.
    A stable local fallback keeps source checkouts importable even when no
    distribution metadata has been generated yet.
    """
    try:
        return metadata.version(_DISTRIBUTION_NAME)
    except metadata.PackageNotFoundError:
        return _LOCAL_VERSION


def format_version() -> str:
    """Return the user-facing CLI version string."""
    return f"oterminus {get_version()}"
