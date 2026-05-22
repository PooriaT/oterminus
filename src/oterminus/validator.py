from __future__ import annotations

import re
import shlex
from pathlib import Path

from oterminus.commands import (
    CommandSpec,
    MaturityLevel,
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


class Validator:
    def __init__(self, policy: PolicyConfig):
        self.policy = policy

    def validate(self, proposal: Proposal) -> ValidationResult:
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
        spec = get_command_spec(base)
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
            reasons.extend(self._validate_command_shape(spec, args[1:]))
            risk = self._risk_for_command_shape(spec, args[1:], default=risk)

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

    def _validate_command_shape(self, spec: CommandSpec, arguments: list[str]) -> list[str]:
        if spec.name == "git":
            if _is_supported_git_inspection_shape(arguments):
                return []
            return [
                "Only read-only Git inspection operations are supported: status --short, "
                "branch --show-current, log --oneline -n <count>, diff --stat, diff --name-only."
            ]

        if spec.name == "tar":
            if _is_supported_tar_inspection_shape(arguments) or _is_supported_tar_extraction_shape(
                arguments
            ):
                return []
            return [
                "Only guarded tar archive operations are supported: tar -tf <archive> and "
                "tar -xf <archive> -C <destination>. Creation, compression flags, path "
                "transforms, extraction without -C, and arbitrary tar options are not supported."
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

    def _risk_for_command_shape(
        self, spec: CommandSpec, arguments: list[str], *, default: RiskLevel
    ) -> RiskLevel:
        if _looks_like_archive_extraction_shape(spec.name, arguments):
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


def _looks_like_archive_extraction_shape(base: str, arguments: list[str]) -> bool:
    if _is_supported_archive_extraction_shape(base, arguments):
        return True
    if base == "tar":
        return any(arg in {"-xf", "--extract", "-x"} for arg in arguments)
    if base == "unzip":
        return bool(arguments) and arguments[0] != "-l"
    return False


def _is_supported_tar_extraction_shape(arguments: list[str]) -> bool:
    return (
        len(arguments) == 4
        and arguments[0] == "-xf"
        and _is_safe_archive_operand(arguments[1])
        and arguments[2] == "-C"
        and _is_safe_archive_destination(arguments[3])
    )


def _is_supported_unzip_extraction_shape(arguments: list[str]) -> bool:
    return (
        len(arguments) == 3
        and _is_safe_archive_operand(arguments[0])
        and arguments[1] == "-d"
        and _is_safe_archive_destination(arguments[2])
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
    return "*" not in value and "?" not in value


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
