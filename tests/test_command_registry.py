import pytest

from oterminus.commands import (
    COMMAND_PACKS,
    command,
    command_examples_for_prompt,
    direct_supported_base_commands,
    get_commands_by_capability,
    get_command_spec,
    looks_like_direct_invocation,
    merge_command_packs,
    supported_base_commands,
    supported_capabilities,
    supported_categories,
)
from oterminus.models import RiskLevel


def test_all_command_packs_are_loaded_into_registry() -> None:
    packed_names = {spec.name for pack in COMMAND_PACKS for spec in pack}

    assert packed_names
    assert packed_names == set(supported_base_commands())


def test_duplicate_command_names_are_rejected() -> None:
    duplicate_ls = command(
        name="ls",
        category="inspection",
        capability_id="filesystem_inspection",
        capability_label="Filesystem inspection",
        capability_description="Inspect files.",
        risk_level=RiskLevel.SAFE,
    )

    with pytest.raises(ValueError, match="Duplicate command spec"):
        merge_command_packs([COMMAND_PACKS[0], (duplicate_ls,)])


def test_existing_commands_remain_available() -> None:
    assert get_command_spec("ls") is not None
    assert get_command_spec("find") is not None
    assert get_command_spec("open") is not None
    assert get_command_spec("ps") is not None


def test_supported_base_commands_includes_curated_entries() -> None:
    commands = supported_base_commands()

    assert "find" in commands
    assert "cp" in commands
    assert "open" in commands
    assert "lsof" in commands


def test_registry_contains_core_command_metadata() -> None:
    spec = get_command_spec("ls")

    assert spec is not None
    assert spec.category == "inspection"
    assert spec.capability_id == "filesystem_inspection"
    assert spec.risk_level == RiskLevel.SAFE
    assert spec.direct_supported is True


def test_registry_exposes_supported_families_and_direct_commands() -> None:
    assert "search" in supported_categories()
    assert "system_inspection" in supported_categories()
    assert "process_inspection" in supported_categories()
    assert "find" in direct_supported_base_commands()
    assert "open" in direct_supported_base_commands()
    assert "ps" in direct_supported_base_commands()
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
    assert looks_like_direct_invocation("whoami", []) is True
    assert looks_like_direct_invocation("whoami", ["extra"]) is False
    assert looks_like_direct_invocation("which", ["python3"]) is True
    assert looks_like_direct_invocation("find", ["all", ".py", "files"]) is False


def test_capability_grouping_and_lookup() -> None:
    filesystem_commands = get_commands_by_capability("filesystem_inspection")

    assert "ls" in filesystem_commands
    assert "find" in filesystem_commands
    assert "grep" not in filesystem_commands


def test_supported_capabilities_include_aliases_and_examples() -> None:
    capabilities = {cap.capability_id: cap for cap in supported_capabilities()}

    text_capability = capabilities["text_inspection"]
    assert "grep" in text_capability.commands
    assert "search text" in text_capability.aliases
    grep = get_command_spec("grep")
    assert grep is not None
    assert grep.examples


def test_all_commands_define_capability_id() -> None:
    for command_name in supported_base_commands():
        spec = get_command_spec(command_name)
        assert spec is not None
        assert spec.capability_id


def test_prompt_examples_output_remains_compact() -> None:
    output = command_examples_for_prompt(max_examples=4)

    assert len(output.splitlines()) <= 4
    assert "filesystem_inspection" in output
