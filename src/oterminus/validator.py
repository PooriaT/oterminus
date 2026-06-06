from __future__ import annotations

import re
import shlex
from pathlib import Path
from enum import Enum

from oterminus.commands import (
    CommandSpec,
    DirectFlagPolicy,
    MaturityLevel,
    NETWORK_TOUCHING_WARNING,
    PathOperandMode,
    command_supported_platforms,
    current_platform_id,
    get_command_spec,
    get_pack_for_command,
    is_command_supported_on_platform,
)
from oterminus.models import Proposal, ProposalMode, RiskLevel, ValidationResult
from oterminus.policies import PolicyConfig, is_risk_allowed
from oterminus.structured_commands import (
    StructuredCommandError,
    is_valid_http_head_url,
    is_valid_network_domain,
    is_valid_network_host,
    parse_raw_command_as_structured,
    render_structured_command,
)

BLOCKED_OPERATOR_TOKENS = {
    "&&": "command chaining",
    "||": "command chaining",
    ";": "command chaining",
    "|": "pipelines",
    "<": "redirection",
    ">": "redirection",
    ">>": "redirection",
    "&": "background execution",
}
BLOCKED_FRAGMENT_REASONS = {
    "$(": "command substitution",
    "`": "command substitution",
    "\n": "multiline command text",
    "\r": "multiline command text",
    "\x00": "null bytes",
}


class ProposalOrigin(str, Enum):
    DIRECT_COMMAND = "direct_command"
    LOCAL_PLANNER = "local_planner"
    OLLAMA_PLANNER = "ollama_planner"
    UNKNOWN = "unknown"


class Validator:
    def __init__(self, policy: PolicyConfig):
        self.policy = policy

    def validate(
        self, proposal: Proposal, *, origin: ProposalOrigin = ProposalOrigin.UNKNOWN
    ) -> ValidationResult:
        reasons: list[str] = []
        warnings: list[str] = []
        risk = proposal.risk_level or RiskLevel.DANGEROUS
        command: str | None = None
        args: list[str] = []

        if proposal.command_family is not None:
            spec = get_command_spec(proposal.command_family)
            if spec is None:
                reasons.append(
                    f"Command family '{proposal.command_family}' is not in the v1 allowlist."
                )
                risk = RiskLevel.DANGEROUS
            else:
                pack_id = get_pack_for_command(spec.name)
                if pack_id in self.policy.disabled_command_packs:
                    reasons.append(
                        f"Command '{spec.name}' is unavailable because command pack '{pack_id}' is disabled."
                    )
                risk = spec.risk_level
                reasons.extend(self._platform_reasons(spec))
                reasons.extend(self._maturity_reasons(spec))

        if proposal.mode == ProposalMode.STRUCTURED:
            try:
                rendered = render_structured_command(proposal.command_family, proposal.arguments)
            except StructuredCommandError as exc:
                reasons.append(str(exc))
            else:
                command = rendered.command
                args = list(rendered.argv)
                if proposal.command:
                    reasons.extend(_blocked_command_text_reasons(proposal.command))
                    warnings.append(
                        "Structured mode ignores the deprecated command field and uses deterministic rendering."
                    )
                    if proposal.command.strip() != command:
                        warnings.append(
                            "Legacy command text differs from deterministic structured rendering and was ignored."
                        )
        else:
            command = (proposal.command or "").strip()
            if command:
                args, shell_issues = self._parse_shell_command(command)
                reasons.extend(shell_issues)

                if proposal.mode == ProposalMode.EXPERIMENTAL:
                    warnings.append(
                        "Experimental mode stays outside deterministic structured rendering and "
                        "uses stricter confirmation."
                    )
                    try:
                        parsed_structured = parse_raw_command_as_structured(command)
                    except StructuredCommandError:
                        parsed_structured = None
                    if parsed_structured is not None:
                        reasons.append(
                            "Experimental mode is not allowed when deterministic structured rendering is available."
                        )

        if not command:
            reasons.append("Proposal has no executable command.")
            if not is_risk_allowed(risk, self.policy):
                reasons.append(
                    f"Risk level '{risk.value}' blocked by policy mode '{self.policy.mode.value}'"
                )
            return ValidationResult(
                accepted=False,
                risk_level=risk,
                reasons=reasons,
                warnings=warnings,
                rendered_command=command,
                argv=args,
            )

        if not args:
            reasons.append("No executable command found.")
            return ValidationResult(
                accepted=False,
                risk_level=RiskLevel.DANGEROUS,
                reasons=reasons,
                warnings=warnings,
                rendered_command=command,
                argv=args,
            )

        base = args[0]
        if not (
            proposal.mode == ProposalMode.STRUCTURED and proposal.command_family == "project_health"
        ):
            project_tool_reasons = _unsupported_project_tool_reasons(args)
            if project_tool_reasons:
                reasons.extend(project_tool_reasons)
                risk = RiskLevel.DANGEROUS

        if proposal.mode != ProposalMode.STRUCTURED and base == "project_health":
            reasons.append(
                "project_health is only valid in structured mode and must render a curated tooling command."
            )
            return ValidationResult(
                accepted=False,
                risk_level=RiskLevel.DANGEROUS,
                reasons=reasons,
                warnings=warnings,
                rendered_command=command,
                argv=args,
            )

        spec = get_command_spec(base)
        if proposal.mode == ProposalMode.STRUCTURED and proposal.command_family == "project_health":
            if not proposal.needs_confirmation:
                reasons.append("project_health proposals must require explicit confirmation.")
            expected = {
                ("poetry", "run", "pytest"),
                ("poetry", "run", "ruff", "check", "."),
                ("poetry", "run", "ruff", "format", "--check", "."),
                ("poetry", "run", "mkdocs", "build", "--strict"),
                ("poetry", "run", "oterminus-evals"),
            }
            if tuple(args) not in expected:
                reasons.append("project_health rendered an unsupported command shape.")
            warnings.append("This command runs local project tooling and may execute project code.")
            risk = RiskLevel.WRITE
            if not is_risk_allowed(risk, self.policy):
                reasons.append(
                    f"Risk level '{risk.value}' blocked by policy mode '{self.policy.mode.value}'"
                )
            return ValidationResult(
                accepted=len(reasons) == 0,
                risk_level=risk,
                reasons=reasons,
                warnings=warnings,
                rendered_command=command,
                argv=args,
            )

        if proposal.command_family is not None and proposal.command_family != base:
            reasons.append(
                f"Command base '{base}' does not match command_family '{proposal.command_family}'."
            )

        if spec is None:
            reasons.append(f"Base command '{base}' is not in the v1 allowlist.")
            risk = RiskLevel.DANGEROUS
        else:
            risk = spec.risk_level
            pack_id = get_pack_for_command(spec.name)
            if pack_id in self.policy.disabled_command_packs:
                reasons.append(
                    f"Command '{spec.name}' is unavailable because command pack '{pack_id}' is disabled."
                )
            reasons.extend(self._platform_reasons(spec))
            reasons.extend(self._maturity_reasons(spec))
            reasons.extend(self._validate_command_shape(spec, args[1:], proposal, origin))
            risk = self._risk_for_command_shape(spec, args[1:], default=risk)
            if spec.network_touching and NETWORK_TOUCHING_WARNING not in warnings:
                warnings.append(NETWORK_TOUCHING_WARNING)

        if (
            spec is not None
            and spec.dangerous_flags
            and any(flag in args for flag in spec.dangerous_flags)
        ):
            warnings.append("Recursive deletion detected.")
            risk = RiskLevel.DANGEROUS

        if (
            spec is not None
            and spec.dangerous_target_literals
            and any(arg in spec.dangerous_target_literals for arg in args[1:])
        ):
            warnings.append("Broad permission change target detected.")
            risk = RiskLevel.DANGEROUS

        if base == "env":
            warnings.append(
                "Environment values may include secrets; only query specific variables and avoid sensitive names."
            )

        if base in {"tar", "unzip"} and _is_supported_archive_extraction_shape(base, args[1:]):
            warnings.append("Archive extraction can write or overwrite files in the destination.")

        if base in {"tar", "zip"} and _is_supported_archive_creation_shape(base, args[1:]):
            warnings.append(
                "Archive creation is write-risk and may overwrite an existing archive path "
                "depending on the underlying archive tool."
            )

        if spec is not None and spec.forbidden_operand_prefixes:
            forbidden_operands = self._forbidden_operands(spec, args[1:])
            if forbidden_operands:
                reasons.append(
                    f"Command '{spec.name}' does not allow these operand targets: {', '.join(forbidden_operands)}"
                )

        if self.policy.allowed_roots and spec is not None:
            bad_paths = self._paths_outside_allowed_roots(spec, args[1:])
            if bad_paths:
                reasons.append(f"Paths outside allowed roots: {', '.join(bad_paths)}")

        if not is_risk_allowed(risk, self.policy):
            reasons.append(
                f"Risk level '{risk.value}' blocked by policy mode '{self.policy.mode.value}'"
            )

        return ValidationResult(
            accepted=len(reasons) == 0,
            risk_level=risk,
            reasons=reasons,
            warnings=warnings,
            rendered_command=command,
            argv=args,
        )

    def _maturity_reasons(self, spec: CommandSpec) -> list[str]:
        if spec.maturity_level == MaturityLevel.BLOCKED:
            return [f"Command '{spec.name}' is blocked by curated command maturity policy."]
        return []

    def _platform_reasons(self, spec: CommandSpec) -> list[str]:
        platform_id = current_platform_id()
        if is_command_supported_on_platform(spec, platform_id):
            return []
        supported = command_supported_platforms(spec)
        if not supported:
            return []
        targets = ", ".join(sorted(supported))
        return [
            f"Command '{spec.name}' is unavailable on platform '{platform_id}'. "
            f"It is only supported on: {targets}."
        ]

    def _validate_command_shape(
        self,
        spec: CommandSpec,
        arguments: list[str],
        proposal: Proposal,
        origin: ProposalOrigin,
    ) -> list[str]:
        if spec.name == "git":
            if _is_supported_git_inspection_shape(arguments):
                return []
            return [
                "Only read-only Git inspection operations are supported: status --short, "
                "branch --show-current, log --oneline -n <count>, diff --stat, diff --name-only."
            ]

        if spec.name == "tar":
            if (
                _is_supported_tar_inspection_shape(arguments)
                or _is_supported_tar_extraction_shape(arguments)
                or _is_supported_tar_creation_shape(arguments)
            ):
                return []
            return [
                "Only guarded tar archive operations are supported: tar -tf <archive>, "
                "tar -xf <archive> -C <destination>, and tar -czf <archive> "
                "<source_paths...>. Broad sources, wildcards, path transforms, extraction "
                "without -C, and arbitrary tar options are not supported."
            ]

        if spec.name == "zip":
            if _is_supported_zip_creation_shape(arguments):
                return []
            return [
                "Only guarded zip archive creation is supported: zip -r <archive> "
                "<source_paths...>. Broad sources, wildcards, encryption, passwords, split "
                "archives, delete-after-compress behavior, and arbitrary zip options are not "
                "supported."
            ]

        if spec.name == "unzip":
            if _is_supported_unzip_inspection_shape(
                arguments
            ) or _is_supported_unzip_extraction_shape(arguments):
                return []
            return [
                "Only guarded zip archive operations are supported: unzip -l <archive> and "
                "unzip <archive> -d <destination>. Extraction without -d, overwrite flags, "
                "and arbitrary unzip options are not supported."
            ]

        if spec.name == "ping":
            if _is_supported_ping_shape(arguments):
                return []
            return [
                "Only ping with a fixed count is supported: ping -c <count> <host>, "
                "where count is between 1 and 10 and host is a hostname, domain, IPv4, or IPv6 address."
            ]

        if spec.name == "curl":
            if _is_supported_curl_head_shape(arguments):
                return []
            return [
                "Only HTTP HEAD requests are supported for curl: curl -I <http-or-https-url>. "
                "POST/PUT/PATCH/DELETE, request bodies, arbitrary headers, authorization, cookies, "
                "downloads, file URLs, and arbitrary curl flags are not supported."
            ]

        if spec.name in {"dig", "nslookup"}:
            if _is_supported_dns_lookup_shape(arguments):
                return []
            return [
                f"Only basic DNS lookup is supported for {spec.name}: {spec.name} <domain>. "
                "Arbitrary flags, shell operators, and non-domain targets are not supported."
            ]

        if (
            origin == ProposalOrigin.DIRECT_COMMAND
            and spec.direct_flag_policy == DirectFlagPolicy.SAFE_INSPECTION_PASSTHROUGH
            and proposal.command_family == spec.name
        ):
            passthrough_reasons = self._validate_safe_inspection_passthrough(spec, arguments)
            if not passthrough_reasons:
                return []
            return passthrough_reasons

        reasons: list[str] = []
        operand_count = 0
        index = 0

        while index < len(arguments):
            arg = arguments[index]

            if arg == "--":
                reasons.append("Option terminator '--' is not supported in curated mode.")
                index += 1
                continue

            if not arg.startswith("-") or arg == "-":
                operand_count += 1
                index += 1
                continue

            consumed, issue = self._consume_flag(spec, arguments, index)
            if issue is not None:
                reasons.append(issue)
                index += 1
                continue
            index += consumed

        if operand_count < spec.min_operands:
            reasons.append(
                f"Command '{spec.name}' requires at least {spec.min_operands} operand(s); got {operand_count}."
            )
        if spec.max_operands is not None and operand_count > spec.max_operands:
            reasons.append(
                f"Command '{spec.name}' allows at most {spec.max_operands} operand(s); got {operand_count}."
            )

        return _dedupe_preserve_order(reasons)

    def _validate_safe_inspection_passthrough(
        self, spec: CommandSpec, arguments: list[str]
    ) -> list[str]:
        reasons: list[str] = []
        operand_count = 0

        for arg in arguments:
            if arg == "--":
                reasons.append("Option terminator '--' is not supported in curated mode.")
                continue

            if not arg.startswith("-") or arg == "-":
                operand_count += 1
                if _looks_like_url_path_operand(arg):
                    reasons.append(
                        f"Path operand '{arg}' for command '{spec.name}' must be a local filesystem target."
                    )
                continue

            if arg.startswith("--"):
                if not _is_safe_passthrough_long_option(arg):
                    reasons.append(f"Malformed direct option '{arg}' for command '{spec.name}'.")
                continue

            if not re.fullmatch(r"-[A-Za-z0-9]+", arg):
                reasons.append(f"Malformed direct option '{arg}' for command '{spec.name}'.")

        if operand_count < spec.min_operands:
            reasons.append(
                f"Command '{spec.name}' requires at least {spec.min_operands} operand(s); got {operand_count}."
            )
        if spec.max_operands is not None and operand_count > spec.max_operands:
            reasons.append(
                f"Command '{spec.name}' allows at most {spec.max_operands} operand(s); got {operand_count}."
            )

        return _dedupe_preserve_order(reasons)

    def _risk_for_command_shape(
        self, spec: CommandSpec, arguments: list[str], *, default: RiskLevel
    ) -> RiskLevel:
        if spec.name == "git" and _looks_like_git_mutation_shape(arguments):
            return RiskLevel.DANGEROUS
        if _looks_like_archive_extraction_shape(spec.name, arguments):
            return RiskLevel.WRITE
        if _looks_like_archive_creation_shape(spec.name, arguments):
            return RiskLevel.WRITE
        return default

    def _consume_flag(
        self, spec: CommandSpec, arguments: list[str], index: int
    ) -> tuple[int, str | None]:
        arg = arguments[index]
        flag_sets = (
            spec.allowed_flags,
            spec.flags_with_values,
            spec.path_valued_flags,
            spec.leading_flags,
            spec.leading_flags_with_values,
            spec.dangerous_flags,
        )

        if "=" in arg:
            flag, value = arg.split("=", maxsplit=1)
            if not value:
                return 1, f"Flag '{flag}' for '{spec.name}' requires a value."
            if (
                flag in spec.flags_with_values
                or flag in spec.path_valued_flags
                or flag in spec.leading_flags_with_values
            ):
                return 1, None
            return 1, f"Unsupported flag '{arg}' for command '{spec.name}'."

        if arg in spec.allowed_flags or arg in spec.leading_flags or arg in spec.dangerous_flags:
            return 1, None

        if (
            arg in spec.flags_with_values
            or arg in spec.path_valued_flags
            or arg in spec.leading_flags_with_values
        ):
            if index + 1 >= len(arguments):
                return 1, f"Flag '{arg}' for '{spec.name}' requires a value."
            return 2, None

        if self._is_supported_short_flag_cluster(arg, *flag_sets):
            return 1, None

        if self._has_supported_inline_flag_value(arg, spec):
            return 1, None

        return 1, f"Unsupported flag '{arg}' for command '{spec.name}'."

    def _forbidden_operands(self, spec: CommandSpec, arguments: list[str]) -> list[str]:
        blocked: list[str] = []
        for operand in self._path_operands(spec, arguments):
            lowered = operand.lower()
            if any(lowered.startswith(prefix) for prefix in spec.forbidden_operand_prefixes):
                blocked.append(operand)
        return blocked

    def _paths_outside_allowed_roots(self, spec: CommandSpec, arguments: list[str]) -> list[str]:
        disallowed: list[str] = []
        roots = [Path(root).resolve() for root in self.policy.allowed_roots]
        path_operands = self._path_operands(spec, arguments)

        for arg in path_operands:
            path = Path(arg).expanduser().resolve()
            if not any(path == root or root in path.parents for root in roots):
                disallowed.append(arg)
        return disallowed

    def _path_operands(self, spec: CommandSpec, arguments: list[str]) -> list[str]:
        if spec.path_operand_mode == PathOperandMode.CD:
            if not arguments or arguments == ["-"]:
                return ["~"] if not arguments else []
            return [arguments[0]]

        if spec.path_operand_mode == PathOperandMode.FIND:
            path_operands: list[str] = []
            index = 0
            while index < len(arguments):
                arg = arguments[index]
                if arg in spec.leading_flags:
                    index += 1
                    continue
                if arg in spec.leading_flags_with_values:
                    index += 2
                    continue
                if any(
                    arg.startswith(flag) and len(arg) > len(flag)
                    for flag in spec.leading_flags_with_inline_values
                ):
                    index += 1
                    continue
                break

            for arg in arguments[index:]:
                if arg.startswith("-") or arg in {"(", ")", "!", ","}:
                    break
                path_operands.append(arg)
            return path_operands

        path_operands: list[str] = []
        index = 0
        while index < len(arguments):
            arg = arguments[index]
            if arg.startswith("-"):
                if "=" in arg:
                    flag, value = arg.split("=", maxsplit=1)
                    if (
                        flag in spec.path_valued_flags
                        and value
                        and not self._is_non_path_flag_value(spec, flag, value)
                    ):
                        path_operands.append(value)
                    index += 1
                    continue
                if arg in spec.path_valued_flags:
                    if index + 1 < len(arguments):
                        value = arguments[index + 1]
                        if not self._is_non_path_flag_value(spec, arg, value):
                            path_operands.append(value)
                    index += 2
                    continue
                if arg in spec.flags_with_values:
                    index += 2
                    continue
                index += 1
                continue
            path_operands.append(arg)
            index += 1
        return path_operands

    def _is_non_path_flag_value(self, spec: CommandSpec, flag: str, value: str) -> bool:
        # GNU grep uses "-" with -f/--file to mean "read patterns from stdin".
        return spec.name == "grep" and flag == "-f" and value == "-"

    def _is_supported_short_flag_cluster(self, token: str, *flag_sets: frozenset[str]) -> bool:
        if not re.fullmatch(r"-[A-Za-z]{2,}", token):
            return False

        allowed_single_flags = {
            flag for flag_set in flag_sets for flag in flag_set if re.fullmatch(r"-[A-Za-z]", flag)
        }
        if not allowed_single_flags:
            return False

        return all(f"-{char}" in allowed_single_flags for char in token[1:])

    def _has_supported_inline_flag_value(self, token: str, spec: CommandSpec) -> bool:
        inline_value_flags = {
            *spec.leading_flags_with_inline_values,
            *(
                flag
                for flag in (*spec.flags_with_values, *spec.path_valued_flags)
                if re.fullmatch(r"-[A-Za-z]", flag)
            ),
        }
        return any(token.startswith(flag) and len(token) > len(flag) for flag in inline_value_flags)

    def _parse_shell_command(self, command: str) -> tuple[list[str], list[str]]:
        issues: list[str] = []
        try:
            lexer = shlex.shlex(command, posix=True, punctuation_chars="|&;<>")
            lexer.whitespace_split = True
            tokens = list(lexer)
        except ValueError:
            return [], ["Command could not be parsed safely."]

        for token, reason in BLOCKED_OPERATOR_TOKENS.items():
            if token in tokens:
                issues.append(f"Command contains blocked {reason}.")

        for fragment, reason in BLOCKED_FRAGMENT_REASONS.items():
            if fragment in command:
                issues.append(f"Command contains blocked {reason}.")

        return tokens, _dedupe_preserve_order(issues)


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _is_safe_passthrough_long_option(token: str) -> bool:
    if token == "--" or any(char.isspace() or ord(char) < 32 for char in token):
        return False
    match = re.fullmatch(r"--[A-Za-z][A-Za-z0-9-]*(?:=([A-Za-z0-9_.,:+/@%-]+))?", token)
    return match is not None and not token.endswith("=")


def _looks_like_url_path_operand(value: str) -> bool:
    lowered = value.lower()
    return "://" in lowered or lowered.startswith("mailto:")


def _blocked_command_text_reasons(command: str) -> list[str]:
    return _dedupe_preserve_order(
        [
            f"Command contains blocked {reason}."
            for fragment, reason in BLOCKED_FRAGMENT_REASONS.items()
            if fragment in command
        ]
    )


def _unsupported_project_tool_reasons(args: list[str]) -> list[str]:
    if not args:
        return []

    base = args[0]
    reasons: list[str] = []

    if base == "poetry":
        if args[:2] == ["poetry", "run"]:
            reasons.append(
                "Direct 'poetry run ...' is unsupported. Use structured project_health with "
                "operation run_tests, lint_check, format_check, build_docs, or run_evals."
            )
            if args == ["poetry", "run", "ruff", "format", "."]:
                reasons.append(
                    "Write-formatting is unsupported; only the curated format_check operation "
                    "renders 'poetry run ruff format --check .'."
                )
            if len(args) >= 3 and args[2] in {"deploy", "publish"}:
                reasons.append("Deploy and publish commands are unsupported.")
            return _dedupe_preserve_order(reasons)

        if len(args) >= 2 and args[1] in {"add", "update", "install"}:
            reasons.append(f"'poetry {args[1]}' is unsupported in curated project health.")
            return reasons

        if len(args) >= 2 and args[1] in {"publish", "deploy"}:
            reasons.append("Deploy and publish commands are unsupported.")
            return reasons

    if base in {"pip", "npm", "brew"} and len(args) >= 2 and args[1] == "install":
        reasons.append(f"'{base} install' is unsupported in curated project health.")

    if base in {"deploy", "publish"}:
        reasons.append("Deploy and publish commands are unsupported.")

    return _dedupe_preserve_order(reasons)


GIT_MUTATION_SUBCOMMANDS = {
    "add",
    "am",
    "apply",
    "bisect",
    "checkout",
    "cherry-pick",
    "clean",
    "commit",
    "fetch",
    "merge",
    "mv",
    "pull",
    "push",
    "rebase",
    "reset",
    "restore",
    "revert",
    "rm",
    "stash",
    "switch",
    "tag",
}

GIT_GLOBAL_FLAGS = {
    "--bare",
    "--glob-pathspecs",
    "--help",
    "--html-path",
    "--icase-pathspecs",
    "--literal-pathspecs",
    "--man-path",
    "--no-optional-locks",
    "--no-pager",
    "--no-replace-objects",
    "--noglob-pathspecs",
    "--paginate",
    "--version",
    "-p",
}

GIT_GLOBAL_FLAGS_WITH_VALUES = {
    "--config-env",
    "--exec-path",
    "--git-dir",
    "--namespace",
    "--super-prefix",
    "--work-tree",
    "-C",
    "-c",
}


def _looks_like_git_mutation_shape(arguments: list[str]) -> bool:
    subcommand = _git_subcommand_after_global_options(arguments)
    return subcommand in GIT_MUTATION_SUBCOMMANDS


def _git_subcommand_after_global_options(arguments: list[str]) -> str | None:
    index = 0
    while index < len(arguments):
        arg = arguments[index]
        if arg == "--":
            index += 1
            break
        if arg in GIT_GLOBAL_FLAGS:
            index += 1
            continue
        if arg in GIT_GLOBAL_FLAGS_WITH_VALUES:
            index += 2
            continue
        if any(
            arg.startswith(f"{flag}=")
            for flag in GIT_GLOBAL_FLAGS_WITH_VALUES
            if flag.startswith("--")
        ):
            index += 1
            continue
        if arg.startswith("-"):
            return None
        return arg

    if index < len(arguments):
        return arguments[index]
    return None


def _is_supported_git_inspection_shape(arguments: list[str]) -> bool:
    if arguments == ["status", "--short"]:
        return True
    if arguments == ["branch", "--show-current"]:
        return True
    if arguments == ["diff", "--stat"]:
        return True
    if arguments == ["diff", "--name-only"]:
        return True
    if len(arguments) == 4 and arguments[:3] == ["log", "--oneline", "-n"]:
        try:
            count = int(arguments[3])
        except ValueError:
            return False
        return 1 <= count <= 100
    return False


def _is_supported_ping_shape(arguments: list[str]) -> bool:
    if len(arguments) != 3 or arguments[0] != "-c":
        return False
    try:
        count = int(arguments[1])
    except ValueError:
        return False
    return 1 <= count <= 10 and is_valid_network_host(arguments[2])


def _is_supported_curl_head_shape(arguments: list[str]) -> bool:
    return len(arguments) == 2 and arguments[0] == "-I" and is_valid_http_head_url(arguments[1])


def _is_supported_dns_lookup_shape(arguments: list[str]) -> bool:
    return len(arguments) == 1 and is_valid_network_domain(arguments[0])


def _is_supported_tar_inspection_shape(arguments: list[str]) -> bool:
    return len(arguments) == 2 and arguments[0] == "-tf" and _is_safe_archive_operand(arguments[1])


def _is_supported_unzip_inspection_shape(arguments: list[str]) -> bool:
    return len(arguments) == 2 and arguments[0] == "-l" and _is_safe_archive_operand(arguments[1])


def _is_supported_archive_extraction_shape(base: str, arguments: list[str]) -> bool:
    if base == "tar":
        return _is_supported_tar_extraction_shape(arguments)
    if base == "unzip":
        return _is_supported_unzip_extraction_shape(arguments)
    return False


def _is_supported_archive_creation_shape(base: str, arguments: list[str]) -> bool:
    if base == "tar":
        return _is_supported_tar_creation_shape(arguments)
    if base == "zip":
        return _is_supported_zip_creation_shape(arguments)
    return False


def _looks_like_archive_extraction_shape(base: str, arguments: list[str]) -> bool:
    if _is_supported_archive_extraction_shape(base, arguments):
        return True
    if base == "tar":
        return any(arg in {"-xf", "--extract", "-x"} for arg in arguments)
    if base == "unzip":
        return bool(arguments) and arguments[0] != "-l"
    return False


def _looks_like_archive_creation_shape(base: str, arguments: list[str]) -> bool:
    if _is_supported_archive_creation_shape(base, arguments):
        return True
    if base == "tar":
        return any(arg in {"-czf", "-cf", "-c", "--create"} for arg in arguments)
    if base == "zip":
        return bool(arguments)
    return False


def _is_supported_tar_extraction_shape(arguments: list[str]) -> bool:
    return (
        len(arguments) == 4
        and arguments[0] == "-xf"
        and _is_safe_archive_operand(arguments[1])
        and arguments[2] == "-C"
        and _is_safe_archive_destination(arguments[3])
    )


def _is_supported_tar_creation_shape(arguments: list[str]) -> bool:
    return (
        len(arguments) >= 3
        and arguments[0] == "-czf"
        and _is_safe_archive_operand(arguments[1])
        and all(_is_safe_archive_source(operand) for operand in arguments[2:])
    )


def _is_supported_unzip_extraction_shape(arguments: list[str]) -> bool:
    return (
        len(arguments) == 3
        and _is_safe_archive_operand(arguments[0])
        and arguments[1] == "-d"
        and _is_safe_archive_destination(arguments[2])
    )


def _is_supported_zip_creation_shape(arguments: list[str]) -> bool:
    return (
        len(arguments) >= 3
        and arguments[0] == "-r"
        and _is_safe_archive_operand(arguments[1])
        and all(_is_safe_archive_source(operand) for operand in arguments[2:])
    )


def _is_safe_archive_operand(value: str) -> bool:
    if not value or value.startswith("-"):
        return False
    lowered = value.lower()
    if "://" in lowered or lowered.startswith("mailto:"):
        return False
    blocked_fragments = ("$(", "`", "\n", "\r", "\x00")
    if any(fragment in value for fragment in blocked_fragments):
        return False
    blocked_operator_fragments = ("&&", "||", ";", "|", "<", ">", "&")
    if any(fragment in value for fragment in blocked_operator_fragments):
        return False
    return not any(fragment in value for fragment in ("*", "?", "[", "]", "{", "}"))


def _is_safe_archive_destination(value: str) -> bool:
    if not _is_safe_archive_operand(value):
        return False
    return value not in {
        "/",
        "/bin",
        "/dev",
        "/etc",
        "/lib",
        "/private",
        "/sbin",
        "/usr",
        "/var",
    }


def _is_safe_archive_source(value: str) -> bool:
    if not _is_safe_archive_operand(value):
        return False
    if value in {
        ".",
        "..",
        "/",
        "~",
        "$HOME",
        "${HOME}",
        "/bin",
        "/dev",
        "/etc",
        "/home",
        "/lib",
        "/private",
        "/root",
        "/sbin",
        "/Users",
        "/usr",
        "/var",
    }:
        return False
    if value.rstrip("/") == str(Path.home()).rstrip("/"):
        return False
    return not (
        value.startswith("~/") or value.startswith("$HOME/") or value.startswith("${HOME}/")
    )
