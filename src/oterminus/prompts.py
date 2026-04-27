from __future__ import annotations

from oterminus.commands import command_examples_for_prompt, supported_base_commands, supported_capabilities
from oterminus.router import RouteResult
from oterminus.structured_commands import STRUCTURED_ARGUMENT_MODELS


def _format_structured_shapes() -> str:
    shapes = {
        "ls": '{"path": ".", "long": true|false, "human_readable": true|false, "all": true|false, "recursive": true|false}',
        "pwd": "{}",
        "whoami": "{}",
        "uname": '{"all": true|false, "kernel_name": true|false, "node_name": true|false, "kernel_release": true|false, "kernel_version": true|false, "machine": true|false}',
        "which": '{"commands": ["python3"], "all_matches": true|false}',
        "env": '{"variable": "PATH"|null}',
        "mkdir": '{"path": "...", "parents": true|false}',
        "chmod": '{"path": "...", "mode": "755"}',
        "find": '{"path": ".", "name": "*.py"}',
        "cp": '{"source": "...", "destination": "...", "recursive": true|false, "preserve": true|false, "no_clobber": true|false}',
        "mv": '{"source": "...", "destination": "...", "no_clobber": true|false}',
        "du": '{"path": ".", "human_readable": true|false, "summarize": true|false, "max_depth": 0|null}',
        "df": '{"path": "."|null, "human_readable": true|false}',
        "stat": '{"path": "...", "dereference": true|false, "verbose": true|false}',
        "head": '{"paths": ["..."], "lines": 10|null, "bytes": null}',
        "tail": '{"paths": ["..."], "lines": 10|null, "bytes": null}',
        "grep": '{"pattern": "...", "paths": ["..."], "ignore_case": true|false, "line_number": true|false, "fixed_strings": true|false, "recursive": true|false, "files_with_matches": true|false, "max_count": 1|null}',
        "cat": '{"paths": ["..."]}',
        "open": '{"path": "...", "reveal": true|false}',
        "file": '{"paths": ["..."], "brief": true|false}',
        "ps": '{"all_processes": true|false, "full_format": true|false, "user": "alice"|null, "pid": 1234|null}',
        "pgrep": '{"pattern": "python", "full_command": true|false, "list_names": true|false, "user": "alice"|null}',
        "lsof": '{"path": "."|null, "pid": 1234|null, "command_prefix": "python"|null, "and_selectors": true|false, "no_dns": true|false, "no_port_names": true|false}',
        "wc": '{"paths": ["README.md"], "lines": true|false, "words": true|false, "bytes": true|false}',
        "sort": '{"path": "README.md", "numeric": true|false, "reverse": true|false, "unique": true|false}',
        "uniq": '{"path": "README.md", "count": true|false, "repeated_only": true|false, "unique_only": true|false}',
    }
    return "\n".join(f"- `{family}`: `{shapes[family]}`" for family in sorted(STRUCTURED_ARGUMENT_MODELS))


def build_system_prompt() -> str:
    structured_families = ", ".join(f"`{family}`" for family in sorted(STRUCTURED_ARGUMENT_MODELS))
    allowlisted_families = ", ".join(f"`{family}`" for family in sorted(supported_base_commands()))
    capability_summaries = "; ".join(
        f"{cap.capability_id} ({', '.join(cap.commands)})" for cap in supported_capabilities()
    )
    capability_examples = command_examples_for_prompt()

    return f"""
You are `oterminus-planner`, a local terminal planning model.

Your role:
- Convert one user request into exactly one proposed terminal action.
- Stay tightly focused on local terminal and filesystem tasks.
- Do not behave like a general chatbot and do not continue the conversation.

Output contract:
- Return JSON only. No markdown. No prose before or after the JSON object.
- Use this schema:
  {{
    "action_type": "shell_command",
    "mode": "structured|experimental",
    "command_family": "... optional command family ...",
    "arguments": {{ "...": "..." }},
    "command": "... optional raw command string ...",
    "summary": "...",
    "explanation": "...",
    "risk_level": "safe|write|dangerous",
    "needs_confirmation": true,
    "notes": ["..."]
  }}

Planning rules:
- Propose exactly one action only.
- Do not produce multi-step plans, alternatives, follow-up questions, or command sequences unless the user explicitly asks for that later.
- Stay within the curated local command families: {allowlisted_families}.
- Treat command families as members of curated capabilities: {capability_summaries}.
- Never include shell chaining, pipelines, redirection, subshells, or command substitution.
- Avoid unrelated conversation, tutorials, or policy commentary.

Structured-first policy:
- Prefer `"mode": "structured"` whenever the request cleanly fits one of the supported structured families: {structured_families}.
- Use `"mode": "experimental"` for single-command shell proposals that stay within the curated allowlist but do not fit the supported structured subset.
- If you return `"mode": "structured"`, always include `"command_family"` and `"arguments"`.
- If you return `"mode": "structured"`, `"command_family"` and `"arguments"` are mandatory and authoritative.
- If you return `"mode": "experimental"`, always include `"command"` and set `notes` to mention that the proposal is experimental.
- For structured proposals, do not include `"command"` unless absolutely required for backward compatibility. Python ignores it and renders the final command deterministically from `"command_family"` + `"arguments"`.
- If structured support is unavailable for the intended action but the action still fits a single allowed shell command, prefer `"mode": "experimental"` and provide `"command"`.

Supported structured families and argument shapes:
{_format_structured_shapes()}

Curated capability examples (compact):
{capability_examples}

Behavior guidance:
- Prefer the most direct single command that satisfies the request.
- Prefer safe read-only inspection commands when the request is ambiguous.
- Use the provided capability route (category + suggested families) to bias family selection before detailed argument planning.
- If route category is `unsupported`, you may still choose experimental mode when a conservative single local command exists, and you must state the limitation in `notes`.
- If the request falls outside local terminal/filesystem work, do not chat about it; choose the closest conservative single local command and explain the limitation in `notes`.
""".strip()


SYSTEM_PROMPT = build_system_prompt()


def build_user_prompt(request: str, route: RouteResult | None = None) -> str:
    if route is None:
        route_block = "none"
    else:
        suggested = ", ".join(route.suggested_families) if route.suggested_families else "none"
        capabilities = ", ".join(route.suggested_capabilities) if route.suggested_capabilities else "none"
        route_block = (
            f"category={route.category}; confidence={route.confidence:.2f}; "
            f"reason={route.reason}; suggested_families={suggested}; suggested_capabilities={capabilities}"
        )

    return (
        f"User request: {request}\n"
        f"Capability route: {route_block}\n"
        "Use the capability route as guidance only; choose the best valid proposal.\n"
        "If route category is unsupported, keep notes explicit about limitations and why experimental mode may be needed.\n"
        "Return only JSON."
    )
