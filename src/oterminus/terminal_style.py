from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Mapping, TextIO


class ColorMode(str, Enum):
    AUTO = "auto"
    ALWAYS = "always"
    NEVER = "never"


class StyleToken(str, Enum):
    HEADING = "heading"
    COMMAND = "command"
    DETAIL = "detail"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    MUTED = "muted"
    RISK_SAFE = "risk_safe"
    RISK_WRITE = "risk_write"
    RISK_DANGEROUS = "risk_dangerous"
    CONFIRMATION_STANDARD = "confirmation_standard"
    CONFIRMATION_STRONG = "confirmation_strong"
    CONFIRMATION_VERY_STRONG = "confirmation_very_strong"


_RESET = "\x1b[0m"
_ANSI_BY_TOKEN: dict[StyleToken, str] = {
    StyleToken.HEADING: "\x1b[1m",
    StyleToken.COMMAND: "\x1b[36m",
    StyleToken.DETAIL: "\x1b[37m",
    StyleToken.SUCCESS: "\x1b[32m",
    StyleToken.WARNING: "\x1b[33m",
    StyleToken.ERROR: "\x1b[31m",
    StyleToken.MUTED: "\x1b[2m",
    StyleToken.RISK_SAFE: "\x1b[32m",
    StyleToken.RISK_WRITE: "\x1b[33m",
    StyleToken.RISK_DANGEROUS: "\x1b[31;1m",
    StyleToken.CONFIRMATION_STANDARD: "\x1b[36m",
    StyleToken.CONFIRMATION_STRONG: "\x1b[33;1m",
    StyleToken.CONFIRMATION_VERY_STRONG: "\x1b[31;1m",
}


@dataclass(frozen=True)
class TerminalStyle:
    color_enabled: bool

    def apply(self, token: StyleToken, text: str) -> str:
        if not self.color_enabled or not text:
            return text
        return f"{_ANSI_BY_TOKEN[token]}{text}{_RESET}"


def resolve_color_enabled(
    *,
    color_mode: ColorMode,
    stream: TextIO,
    environ: Mapping[str, str] | None = None,
) -> bool:
    env = os.environ if environ is None else environ
    if "NO_COLOR" in env:
        return False
    if color_mode is ColorMode.NEVER:
        return False
    if color_mode is ColorMode.ALWAYS:
        return True
    return _stream_isatty(stream) and env.get("TERM", "").lower() != "dumb"


def make_terminal_style(
    *,
    color_mode: ColorMode,
    stream: TextIO,
    environ: Mapping[str, str] | None = None,
) -> TerminalStyle:
    return TerminalStyle(
        color_enabled=resolve_color_enabled(
            color_mode=color_mode,
            stream=stream,
            environ=environ,
        )
    )


def _stream_isatty(stream: TextIO) -> bool:
    isatty = getattr(stream, "isatty", None)
    if not callable(isatty):
        return False
    try:
        return bool(isatty())
    except OSError:
        return False
