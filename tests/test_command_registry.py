from oterminus.command_registry import (
    direct_supported_base_commands,
    get_command_spec,
    looks_like_direct_invocation,
    supported_categories,
)
from oterminus.models import RiskLevel


def test_registry_contains_core_command_metadata() -> None:
    spec = get_command_spec("ls")

    assert spec is not None
    assert spec.category == "inspection"
    assert spec.risk_level == RiskLevel.SAFE
    assert spec.direct_supported is True


def test_registry_exposes_supported_families_and_direct_commands() -> None:
    assert "search" in supported_categories()
    assert "find" in direct_supported_base_commands()
    assert "open" in direct_supported_base_commands()
    assert "macos_integration" in supported_categories()


def test_registry_tracks_new_family_constraints() -> None:
    cp = get_command_spec("cp")
    open_command = get_command_spec("open")

    assert cp is not None
    assert cp.risk_level == RiskLevel.WRITE
    assert "-R" in cp.allowed_flags
    assert cp.min_operands == 2

    assert open_command is not None
    assert open_command.risk_level == RiskLevel.SAFE
    assert "https://" in open_command.forbidden_operand_prefixes


def test_registry_direct_detection_heuristics_match_current_behavior() -> None:
    assert looks_like_direct_invocation("pwd", []) is True
    assert looks_like_direct_invocation("pwd", ["extra"]) is False
    assert looks_like_direct_invocation("find", ["all", ".py", "files"]) is False
