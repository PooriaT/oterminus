import pytest

from oterminus.commands import (
    COMMAND_PACKS,
    COMMAND_REGISTRY,
    NETWORK_TOUCHING_WARNING,
    MaturityLevel,
    capability_summary_for_prompt,
    command,
    command_examples_for_prompt,
    direct_supported_base_commands,
    get_commands_by_capability,
    get_command_spec,
    looks_like_direct_invocation,
    merge_command_packs,
    normalize_platform_id,
    supported_base_commands,
    supported_capabilities,
    supported_categories,
)
from oterminus.models import RiskLevel


def test_all_command_packs_are_loaded_into_registry() -> None:
    packed_names = {spec.name for pack in COMMAND_PACKS for spec in pack.commands}

    assert packed_names
    assert set(supported_base_commands(platform_id="darwin")).issubset(packed_names)
    assert set(supported_base_commands(platform_id="linux")).issubset(packed_names)


def test_duplicate_command_names_are_rejected() -> None:
    filesystem_pack = next(pack for pack in COMMAND_PACKS if pack.pack_id == "filesystem")
    duplicate_ls = command(
        name="ls",
        category="inspection",
        capability_id="filesystem_inspection",
        capability_label="Filesystem inspection",
        capability_description="Inspect files.",
        risk_level=RiskLevel.SAFE,
    )

    with pytest.raises(ValueError, match="Duplicate command spec"):
        merge_command_packs([filesystem_pack, (duplicate_ls,)])


def test_existing_commands_remain_available() -> None:
    assert get_command_spec("ls") is not None
    assert get_command_spec("clear") is not None
    assert get_command_spec("find") is not None
    assert get_command_spec("open") is not None
    assert get_command_spec("ps") is not None
    assert get_command_spec("git") is not None
    assert get_command_spec("tar") is not None
    assert get_command_spec("unzip") is not None
    assert get_command_spec("ping") is not None
    assert get_command_spec("curl") is not None
    assert get_command_spec("dig") is not None
    assert get_command_spec("nslookup") is not None


def test_supported_base_commands_includes_curated_entries() -> None:
    commands = supported_base_commands()

    assert "find" in commands
    assert "clear" in commands
    assert "cp" in commands
    assert "open" not in supported_base_commands(platform_id="linux")
    assert "open" in supported_base_commands(platform_id="darwin")
    assert "lsof" in commands
    assert "git" in commands
    assert "tar" in commands
    assert "unzip" in commands
    assert "ping" in commands
    assert "curl" in commands
    assert "dig" in commands
    assert "nslookup" in commands


def test_registry_contains_core_command_metadata() -> None:
    spec = get_command_spec("ls")

    assert spec is not None
    assert spec.category == "inspection"
    assert spec.capability_id == "filesystem_inspection"
    assert spec.risk_level == RiskLevel.SAFE
    assert spec.direct_supported is True
    assert spec.network_touching is False


def test_command_spec_network_touching_defaults_false() -> None:
    spec = command(
        name="localcheck",
        category="inspection",
        capability_id="synthetic_local",
        capability_label="Synthetic local",
        capability_description="Synthetic local command.",
        risk_level=RiskLevel.SAFE,
    )

    assert spec.network_touching is False


def test_command_spec_can_mark_network_touching() -> None:
    spec = command(
        name="netcheck",
        category="network_inspection",
        capability_id="synthetic_network",
        capability_label="Synthetic network",
        capability_description="Synthetic network command.",
        risk_level=RiskLevel.SAFE,
        maturity_level=MaturityLevel.DIRECT_ONLY,
        network_touching=True,
    )

    assert spec.network_touching is True


def test_registry_exposes_supported_families_and_direct_commands() -> None:
    assert "search" in supported_categories()
    assert "system_inspection" in supported_categories()
    assert "process_inspection" in supported_categories()
    assert "archive_inspection" in supported_categories()
    assert "network_inspection" in supported_categories()
    assert "find" in direct_supported_base_commands()
    assert "open" in direct_supported_base_commands(platform_id="darwin")
    assert "open" not in direct_supported_base_commands(platform_id="linux")
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
    assert looks_like_direct_invocation("clear", []) is True
    assert looks_like_direct_invocation("clear", ["extra"]) is False
    assert looks_like_direct_invocation("whoami", []) is True
    assert looks_like_direct_invocation("whoami", ["extra"]) is False
    assert looks_like_direct_invocation("which", ["python3"]) is True
    assert looks_like_direct_invocation("find", ["all", ".py", "files"]) is False
    assert looks_like_direct_invocation("git", ["status", "--short"]) is True
    assert looks_like_direct_invocation("git", ["add", "."]) is False
    assert looks_like_direct_invocation("tar", ["-tf", "archive.tar"]) is True
    assert looks_like_direct_invocation("tar", ["-xf", "archive.tar", "-C", "out"]) is True
    assert looks_like_direct_invocation("tar", ["-xf", "archive.tar"]) is False
    assert looks_like_direct_invocation("unzip", ["-l", "archive.zip"]) is True
    assert looks_like_direct_invocation("unzip", ["archive.zip", "-d", "restore"]) is True
    assert looks_like_direct_invocation("unzip", ["archive.zip"]) is False
    assert looks_like_direct_invocation("ping", ["-c", "4", "example.com"]) is True
    assert looks_like_direct_invocation("ping", ["example.com"]) is False
    assert looks_like_direct_invocation("ping", ["-f", "example.com"]) is False
    assert looks_like_direct_invocation("curl", ["-I", "https://example.com"]) is True
    assert looks_like_direct_invocation("curl", ["-X", "POST", "https://example.com"]) is False
    assert looks_like_direct_invocation("dig", ["example.com"]) is True
    assert looks_like_direct_invocation("dig", ["+short", "example.com"]) is False


def test_capability_grouping_and_lookup() -> None:
    filesystem_commands = get_commands_by_capability("filesystem_inspection")

    assert "ls" in filesystem_commands
    assert "find" in filesystem_commands
    assert "grep" not in filesystem_commands


def test_supported_capabilities_include_aliases_and_examples() -> None:
    capabilities = {cap.capability_id: cap for cap in supported_capabilities()}

    text_capability = capabilities["text_inspection"]
    archive_capability = capabilities["archive_inspection"]
    assert "git_inspection" in capabilities
    network_capability = capabilities["network_diagnostics"]
    assert network_capability.network_touching is True
    assert network_capability.commands == ("curl", "dig", "nslookup", "ping")
    assert "tar" in archive_capability.commands
    assert "unzip" in archive_capability.commands
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


def test_only_network_pack_commands_are_network_touching() -> None:
    network_commands = {name for name, spec in COMMAND_REGISTRY.items() if spec.network_touching}

    assert network_commands == {"curl", "dig", "nslookup", "ping"}


def test_network_pack_can_be_disabled() -> None:
    commands = supported_base_commands(disabled_pack_ids=frozenset({"network"}))
    capabilities = {cap.capability_id for cap in supported_capabilities(frozenset({"network"}))}

    assert "ping" not in commands
    assert "curl" not in commands
    assert "network_diagnostics" not in capabilities


def test_prompt_examples_output_remains_compact() -> None:
    output = command_examples_for_prompt(max_examples=4)

    assert len(output.splitlines()) <= 4
    assert "filesystem_inspection" in output


def test_capability_summary_for_prompt_remains_compact() -> None:
    summary = capability_summary_for_prompt(max_capabilities=3, max_commands_per_capability=2)

    assert len(summary.splitlines()) == 3
    assert len(summary) < 600


def test_capability_summary_for_prompt_can_mark_network_touching(monkeypatch) -> None:
    spec = command(
        name="netcheck",
        category="network_inspection",
        capability_id="synthetic_network",
        capability_label="Synthetic network",
        capability_description="Synthetic read-only network diagnostics.",
        risk_level=RiskLevel.SAFE,
        network_touching=True,
        natural_language_aliases=("network diagnostic",),
    )
    monkeypatch.setitem(COMMAND_REGISTRY, "netcheck", spec)

    summary = capability_summary_for_prompt(max_capabilities=20)

    assert "synthetic_network" in summary
    assert "network-touching" in summary
    assert NETWORK_TOUCHING_WARNING not in summary


def test_platform_normalization() -> None:
    assert normalize_platform_id("darwin") == "darwin"
    assert normalize_platform_id("linux") == "linux"
    assert normalize_platform_id("linux2") == "linux"
    assert normalize_platform_id("win32") == "windows"
