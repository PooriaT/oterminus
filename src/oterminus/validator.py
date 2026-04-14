from __future__ import annotations

import shlex
from pathlib import Path

from oterminus.models import Proposal, RiskLevel, ValidationResult
from oterminus.policies import PolicyConfig, is_risk_allowed

ALLOWED_BASE_COMMANDS = {
    "ls": RiskLevel.SAFE,
    "pwd": RiskLevel.SAFE,
    "cat": RiskLevel.SAFE,
    "head": RiskLevel.SAFE,
    "tail": RiskLevel.SAFE,
    "grep": RiskLevel.SAFE,
    "find": RiskLevel.SAFE,
    "du": RiskLevel.SAFE,
    "stat": RiskLevel.SAFE,
    "mkdir": RiskLevel.WRITE,
    "cp": RiskLevel.WRITE,
    "mv": RiskLevel.WRITE,
    "chmod": RiskLevel.WRITE,
    "touch": RiskLevel.WRITE,
    "rm": RiskLevel.DANGEROUS,
    "chown": RiskLevel.DANGEROUS,
    "sudo": RiskLevel.DANGEROUS,
}

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
        risk = ALLOWED_BASE_COMMANDS.get(base)
        if risk is None:
            reasons.append(f"Base command '{base}' is not in the v1 allowlist.")
            risk = RiskLevel.DANGEROUS

        if base == "rm" and any(flag in args for flag in ["-r", "-rf", "-fr"]):
            warnings.append("Recursive deletion detected.")
            risk = RiskLevel.DANGEROUS

        if base in {"chmod", "chown"} and any(arg in {"/", "/*"} for arg in args[1:]):
            warnings.append("Broad permission change target detected.")
            risk = RiskLevel.DANGEROUS

        if self.policy.allowed_roots:
            bad_paths = self._paths_outside_allowed_roots(args[1:])
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

    def _paths_outside_allowed_roots(self, arguments: list[str]) -> list[str]:
        disallowed: list[str] = []
        roots = [Path(root).resolve() for root in self.policy.allowed_roots]

        for arg in arguments:
            if arg.startswith("-"):
                continue
            path = Path(arg).expanduser().resolve()
            if not any(path == root or root in path.parents for root in roots):
                disallowed.append(arg)
        return disallowed
