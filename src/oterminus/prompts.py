from __future__ import annotations

from oterminus.commands import (
    NETWORK_TOUCHING_WARNING,
    capability_summary_for_prompt,
    command_examples_for_prompt,
    supported_base_commands,
)
from oterminus.router import RouteResult
from oterminus.structured_commands import STRUCTURED_ARGUMENT_MODELS


def _format_structured_shapes(structured_families: tuple[str, ...]) -> str:
    shapes = {
        "ls": (
            '{"path": ".", "long": true|false, "human_readable": true|false, '
            '"all": true|false, "recursive": true|false}'
        ),
        "pwd": "{}",
        "clear": "{}",
        "whoami": "{}",
        "uname": (
            '{"all": true|false, "kernel_name": true|false, "node_name": true|false, '
            '"kernel_release": true|false, "kernel_version": true|false, "machine": true|false}'
        ),
        "which": '{"commands": ["python3"], "all_matches": true|false}',
        "env": '{"variable": "PATH"}',
        "mkdir": '{"path": "...", "parents": true|false}',
        "chmod": '{"path": "...", "mode": "755"}',
        "find": '{"path": ".", "name": "*.py"}',
        "cp": (
            '{"source": "...", "destination": "...", "recursive": true|false, '
            '"preserve": true|false, "no_clobber": true|false}'
        ),
        "mv": '{"source": "...", "destination": "...", "no_clobber": true|false}',
        "du": (
            '{"path": ".", "human_readable": true|false, "summarize": true|false, '
            '"max_depth": 0|null}'
        ),
        "df": '{"path": "."|null, "human_readable": true|false}',
        "stat": '{"path": "...", "dereference": true|false, "verbose": true|false}',
        "head": '{"paths": ["..."], "lines": 10|null, "bytes": null}',
        "tail": '{"paths": ["..."], "lines": 10|null, "bytes": null}',
        "grep": (
            '{"pattern": "...", "paths": ["..."], "ignore_case": true|false, '
            '"line_number": true|false, "fixed_strings": true|false, '
            '"recursive": true|false, "files_with_matches": true|false, '
            '"max_count": 1|null}'
        ),
        "cat": '{"paths": ["..."]}',
        "open": '{"path": "...", "reveal": true|false}',
        "file": '{"paths": ["..."], "brief": true|false}',
        "ps": (
            '{"all_processes": true|false, "full_format": true|false, '
            '"user": "alice"|null, "pid": 1234|null}'
        ),
        "pgrep": (
            '{"pattern": "python", "full_command": true|false, '
            '"list_names": true|false, "user": "alice"|null}'
        ),
        "lsof": (
            '{"path": "."|null, "pid": 1234|null, "command_prefix": "python"|null, '
            '"and_selectors": true|false, "no_dns": true|false, '
            '"no_port_names": true|false}'
        ),
        "wc": (
            '{"paths": ["README.md"], "lines": true|false, '
            '"words": true|false, "bytes": true|false}'
        ),
        "sort": (
            '{"path": "README.md", "numeric": true|false, '
            '"reverse": true|false, "unique": true|false}'
        ),
        "uniq": (
            '{"path": "README.md", "count": true|false, '
            '"repeated_only": true|false, "unique_only": true|false}'
        ),
        "git": (
            '{"operation": "status_short|branch_current|log_oneline|diff_stat|diff_name_only", '
            '"count": 10}'
        ),
        "ping": '{"host": "example.com", "count": 4}',
        "curl": '{"operation": "http_head", "url": "https://example.com"}',
        "dig": '{"domain": "example.com"}',
        "nslookup": '{"domain": "example.com"}',
        "tar": (
            '{"operation": "list|extract_tar|create_tar_gz", "archive_path": "archive.tar", '
            '"destination_path": "out" only for extract_tar, '
            '"source_paths": ["src"] only for create_tar_gz}'
        ),
        "unzip": (
            '{"operation": "list|extract_zip", "archive_path": "archive.zip", '
            '"destination_path": "out" only for extract_zip}'
        ),
        "zip": (
            '{"operation": "create_zip", "archive_path": "archive.zip", "source_paths": ["src"]}'
        ),
        "project_health": (
            '{"operation": "run_tests|lint_check|format_check|build_docs|run_evals"}'
        ),
    }
    return "\n".join(f"- `{family}`: `{shapes[family]}`" for family in structured_families)


def build_system_prompt(
    *, disabled_pack_ids: frozenset[str] | None = None, platform_id: str | None = None
) -> str:
    enabled_families = set(supported_base_commands(disabled_pack_ids, platform_id))
    structured_family_list = tuple(
        family for family in sorted(STRUCTURED_ARGUMENT_MODELS) if family in enabled_families
    )
    structured_families = ", ".join(f"`{family}`" for family in structured_family_list)
    allowlisted_families = ", ".join(
        f"`{family}`" for family in sorted(supported_base_commands(disabled_pack_ids, platform_id))
    )
    capability_summaries = capability_summary_for_prompt(
        disabled_pack_ids=disabled_pack_ids, platform_id=platform_id
    )
    capability_examples = command_examples_for_prompt(
        disabled_pack_ids=disabled_pack_ids, platform_id=platform_id
    )
    archive_guidance = (
        "- For archive extraction, use structured `tar`/`unzip` only when the request includes an "
        "explicit destination. Do not guess the destination and do not use overwrite or arbitrary "
        "archive flags.\n"
        "- For archive creation, use structured `tar` with operation `create_tar_gz` or structured "
        "`zip` with operation `create_zip` only when the request includes both an explicit output "
        "archive path and explicit source paths. Do not infer sources, use wildcards, add flags, "
        "or support encryption/passwords/split archives.\n"
        if {"tar", "unzip", "zip"}.issubset(enabled_families)
        else ""
    )
    network_guidance = (
        "- Network diagnostics contact external hosts and may reveal network metadata. Use only "
        "structured `ping`, `curl` HTTP HEAD, `dig`, or `nslookup` for read-only diagnostics. "
        "Do not propose POST/PUT/PATCH/DELETE, request bodies, arbitrary headers, authorization, "
        "cookies, downloads, redirects that write files, scanning, SSH, or arbitrary network shell "
        "commands.\n"
        if {"ping", "curl", "dig", "nslookup"}.issubset(enabled_families)
        else ""
    )
    project_health_guidance = (
        "- `project_health` is a curated developer-workflow capability only. Supported operations are "
        "`run_tests`, `lint_check`, `format_check`, `build_docs`, and `run_evals`.\n"
        "- `project_health` operations may execute local project code and tooling; keep "
        "`risk_level` as `write` and keep confirmation required.\n"
        "- Do not propose arbitrary `poetry run ...`, install/update/package-management commands "
        "(`poetry add`, `poetry update`, `poetry install`, `pip install`, `npm install`, `brew install`), "
        "deploy/publish commands, or write-formatting (for example `ruff format .`).\n"
        if "project_health" in enabled_families
        else ""
    )

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
    "command": "... optional command string for experimental proposals ...",
    "summary": "...",
    "explanation": "...",
    "risk_level": "safe|write|dangerous",
    "needs_confirmation": true,
    "notes": ["..."]
  }}

Planning rules:
- Propose exactly one action only.
- Do not produce multi-step plans, alternatives, follow-up questions, or command sequences unless the user \
explicitly asks for that later.
- Stay within the curated local command families: {allowlisted_families}.
- Treat command families as members of curated capabilities:
{capability_summaries}
- If a capability summary is marked network-touching, treat it as leaving the local-machine-only \
boundary and include this warning in `notes`: {NETWORK_TOUCHING_WARNING}
- Never include shell chaining, pipelines, redirection, subshells, or command substitution.
- Avoid unrelated conversation, tutorials, or policy commentary.

Structured-first policy:
- Prefer `"mode": "structured"` whenever the request cleanly fits one of the supported structured \
families: {structured_families}.
- Use `"mode": "experimental"` only for single-command shell proposals that stay within the curated \
allowlist but do not fit the supported structured subset.
- If you return `"mode": "structured"`, always include `"command_family"` and `"arguments"`.
- Only `"structured"` and `"experimental"` are valid modes; never emit any other mode value.
- If you return `"mode": "structured"`, `"command_family"` and `"arguments"` are mandatory and authoritative.
- If you return `"mode": "experimental"`, always include `"command"` and set `notes` to mention \
that the proposal is experimental.
- For structured proposals, do not include `"command"`; Python renders the final command \
deterministically from `"command_family"` + `"arguments"`.
- If structured support is unavailable for the intended action but the action still fits a single \
allowed shell command, prefer `"mode": "experimental"` and provide `"command"`.

Supported structured families and argument shapes:
{_format_structured_shapes(structured_family_list)}

Curated capability examples (compact):
{capability_examples}

Behavior guidance:
- Prefer the most direct single command that satisfies the request.
- Prefer safe read-only inspection commands when the request is ambiguous.
{archive_guidance}\
{network_guidance}\
{project_health_guidance}\
- Use the provided capability route (category + suggested families) to bias family selection before \
detailed argument planning.
- If route category is `unsupported`, you may still choose experimental mode when a conservative \
single local command exists, and you must state the limitation in `notes`.
- If the request falls outside local terminal/filesystem work, do not chat about it; choose the \
closest conservative single local command and explain the limitation in `notes`.
""".strip()


def build_user_prompt(request: str, route: RouteResult | None = None) -> str:
    if route is None:
        route_block = "none"
    else:
        suggested = ", ".join(route.suggested_families) if route.suggested_families else "none"
        capabilities = (
            ", ".join(route.suggested_capabilities) if route.suggested_capabilities else "none"
        )
        route_block = (
            f"category={route.category}; confidence={route.confidence:.2f}; "
            f"reason={route.reason}; suggested_families={suggested}; suggested_capabilities={capabilities}"
        )

    return (
        f"User request: {request}\n"
        f"Capability route: {route_block}\n"
        "Use the capability route as guidance only; choose the best valid proposal.\n"
        "If route category is unsupported, keep notes explicit about limitations and why "
        "experimental mode may be needed.\n"
        "Return only JSON."
    )
