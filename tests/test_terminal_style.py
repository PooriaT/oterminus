from __future__ import annotations

from oterminus.terminal_style import (
    ColorMode,
    StyleToken,
    TerminalStyle,
    resolve_color_enabled,
)


class FakeStream:
    def __init__(self, isatty: bool) -> None:
        self._isatty = isatty

    def isatty(self) -> bool:
        return self._isatty


def test_terminal_style_preserves_exact_text_when_disabled() -> None:
    style = TerminalStyle(color_enabled=False)

    assert style.apply(StyleToken.ERROR, "FAIL example") == "FAIL example"


def test_terminal_style_wraps_text_when_enabled() -> None:
    style = TerminalStyle(color_enabled=True)

    styled = style.apply(StyleToken.SUCCESS, "PASS example")

    assert styled.startswith("\x1b[")
    assert styled.endswith("\x1b[0m")
    assert "PASS example" in styled


def test_auto_color_requires_tty_and_non_dumb_term() -> None:
    assert (
        resolve_color_enabled(
            color_mode=ColorMode.AUTO,
            stream=FakeStream(True),
            environ={"TERM": "xterm-256color"},
        )
        is True
    )
    assert (
        resolve_color_enabled(
            color_mode=ColorMode.AUTO,
            stream=FakeStream(False),
            environ={"TERM": "xterm-256color"},
        )
        is False
    )
    assert (
        resolve_color_enabled(
            color_mode=ColorMode.AUTO,
            stream=FakeStream(True),
            environ={"TERM": "dumb"},
        )
        is False
    )


def test_always_enables_redirected_output_unless_no_color_is_set() -> None:
    assert (
        resolve_color_enabled(
            color_mode=ColorMode.ALWAYS,
            stream=FakeStream(False),
            environ={"TERM": "dumb"},
        )
        is True
    )
    assert (
        resolve_color_enabled(
            color_mode=ColorMode.ALWAYS,
            stream=FakeStream(True),
            environ={"NO_COLOR": ""},
        )
        is False
    )


def test_never_disables_color() -> None:
    assert (
        resolve_color_enabled(
            color_mode=ColorMode.NEVER,
            stream=FakeStream(True),
            environ={"TERM": "xterm-256color"},
        )
        is False
    )
