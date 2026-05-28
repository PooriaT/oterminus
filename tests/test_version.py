from __future__ import annotations

from importlib import metadata
from unittest.mock import Mock

import pytest

from oterminus.version import get_version


def test_get_version_uses_package_metadata(monkeypatch) -> None:
    version_lookup = Mock(return_value="1.2.3")
    monkeypatch.setattr("oterminus.version.metadata.version", version_lookup)

    assert get_version() == "1.2.3"
    version_lookup.assert_called_once_with("oterminus")


def test_get_version_falls_back_when_package_metadata_missing(monkeypatch) -> None:
    def missing(_name: str) -> str:
        raise metadata.PackageNotFoundError(_name)

    monkeypatch.setattr("oterminus.version.metadata.version", missing)

    assert get_version() == "0.0.0+local"
