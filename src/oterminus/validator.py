from __future__ import annotations

import shlex
from pathlib import Path

from oterminus.command_registry import CommandSpec, PathOperandMode, get_command_spec
from oterminus.models import Proposal, RiskLevel, ValidationResult
from oterminus.policies import PolicyConfig, is_risk_allowed

BLOCKED_TOKENS = {"&&", "||", ";", "|", "`", "$(", ">", ">>", "<"}


class Validator:
    def __init__(self, policy: PolicyConfig):
        self.policy = policy

    def validate(self, proposal: Proposal) -> ValidationResult:
        command = proposal.command.strip()
        reasons: list[str] = []
        warnings: list[str] = []

        if not command:
            return ValidationResult(accepted=False, risk_level=RiskLevel.DANGEROUS, reasons=["Empty command."])

        if any(token in command for token in BLOCKED_TOKENS):
            reasons.append("Command contains blocked shell operators or redirection.")

        try:
            args = shlex.split(command)
        except ValueError:
            reasons.append("Command could not be parsed safely.")
            args = []

        if not args:
            reasons.append("No executable command found.")
            return ValidationResult(accepted=False, risk_level=RiskLevel.DANGEROUS, reasons=reasons)

        base = args[0]
        spec = get_command_spec(base)
        if spec is None:
            reasons.append(f"Base command '{base}' is not in the v1 allowlist.")
            risk = RiskLevel.DANGEROUS
        else:
            risk = spec.risk_level

        if spec is not None and spec.dangerous_flags and any(flag in args for flag in spec.dangerous_flags):
            warnings.append("Recursive deletion detected.")
            risk = RiskLevel.DANGEROUS

        if spec is not None and spec.dangerous_target_literals and any(
            arg in spec.dangerous_target_literals for arg in args[1:]
        ):
            warnings.append("Broad permission change target detected.")
            risk = RiskLevel.DANGEROUS

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
        )

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
        skip_next = False
        for arg in arguments:
            if skip_next:
                skip_next = False
                continue
            if arg.startswith("-"):
                if arg in spec.flags_with_values:
                    skip_next = True
                continue
            path_operands.append(arg)
        return path_operands
