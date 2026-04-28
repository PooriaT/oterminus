from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit

_REDACTED = "[REDACTED]"

_INLINE_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?P<prefix>\b(?:api[_-]?key|token|password|passwd|secret)\b\s*[:=]\s*)(?P<value>\S+)",
    flags=re.IGNORECASE,
)
_BEARER_RE = re.compile(r"(?P<prefix>\bbearer\s+)(?P<value>\S+)", flags=re.IGNORECASE)
_GITHUB_TOKEN_RE = re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")
_ENV_ASSIGNMENT_RE = re.compile(
    r"\b(?P<name>[A-Za-z_][A-Za-z0-9_]*(?:TOKEN|SECRET|PASSWORD|PASS|API[_-]?KEY|AUTH)[A-Za-z0-9_]*)=(?P<value>[^\s]+)",
    flags=re.IGNORECASE,
)
_FLAG_SECRET_RE = re.compile(
    r"(?P<flag>--(?:token|password|passwd|secret|api-key|api_key|access-token|access_token|auth|authorization))(?P<sep>\s+|=)(?P<value>\S+)",
    flags=re.IGNORECASE,
)
_SHORT_FLAG_SECRET_RE = re.compile(r"(?P<flag>-(?:p|k))(?P<sep>\s+)(?P<value>\S+)")


def redact_text(value: str) -> str:
    redacted = value
    redacted = _INLINE_SECRET_ASSIGNMENT_RE.sub(_replace_value, redacted)
    redacted = _BEARER_RE.sub(_replace_value, redacted)
    redacted = _FLAG_SECRET_RE.sub(_replace_value, redacted)
    redacted = _SHORT_FLAG_SECRET_RE.sub(_replace_value, redacted)
    redacted = _ENV_ASSIGNMENT_RE.sub(_replace_value, redacted)
    redacted = _GITHUB_TOKEN_RE.sub(_REDACTED, redacted)
    redacted = _redact_urls_with_credentials(redacted)
    return redacted


def redact_argv(argv: list[str]) -> list[str]:
    if not argv:
        return []

    redacted = list(argv)
    secret_flags = {
        "--token",
        "--password",
        "--passwd",
        "--secret",
        "--api-key",
        "--api_key",
        "--access-token",
        "--access_token",
        "--auth",
        "--authorization",
        "-p",
        "-k",
    }
    index = 0
    while index < len(redacted):
        token = redacted[index]
        lowered = token.lower()
        if lowered in secret_flags and index + 1 < len(redacted):
            redacted[index + 1] = _REDACTED
            index += 2
            continue
        if "=" in token:
            left, right = token.split("=", maxsplit=1)
            if left.lower() in secret_flags:
                redacted[index] = f"{left}={_REDACTED}"
                index += 1
                continue
            if _looks_sensitive_env_name(left):
                redacted[index] = f"{left}={_REDACTED}"
                index += 1
                continue
        if _looks_sensitive_env_assignment(token):
            name, _ = token.split("=", maxsplit=1)
            redacted[index] = f"{name}={_REDACTED}"
            index += 1
            continue
        redacted[index] = redact_text(token)
        index += 1
    return redacted


def _replace_value(match: re.Match[str]) -> str:
    prefix = match.group("prefix") if "prefix" in match.groupdict() else match.group("flag")
    separator = match.group("sep") if "sep" in match.groupdict() else ""
    return f"{prefix}{separator}{_REDACTED}"


def _looks_sensitive_env_name(name: str) -> bool:
    lowered = name.lower()
    return any(marker in lowered for marker in ("token", "secret", "password", "passwd", "api_key", "api-key", "auth"))


def _looks_sensitive_env_assignment(token: str) -> bool:
    if "=" not in token:
        return False
    name, _ = token.split("=", maxsplit=1)
    return _looks_sensitive_env_name(name)


def _redact_urls_with_credentials(value: str) -> str:
    parts = value.split()
    if not parts:
        return value

    transformed: list[str] = []
    for part in parts:
        transformed.append(_redact_url_token(part))
    return " ".join(transformed)


def _redact_url_token(token: str) -> str:
    try:
        parsed = urlsplit(token)
    except ValueError:
        return token
    if parsed.scheme not in {"http", "https"} or "@" not in parsed.netloc:
        return token

    host = parsed.hostname or ""
    try:
        parsed_port = parsed.port
    except ValueError:
        parsed_port = None
    port = f":{parsed_port}" if parsed_port else ""
    netloc = f"{_REDACTED}@{host}{port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))
