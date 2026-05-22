import pytest

from oterminus.commands import COMMAND_REGISTRY, NETWORK_TOUCHING_WARNING, command as command_spec
from oterminus.models import ActionType, Proposal, ProposalMode, RiskLevel
from oterminus.policies import PolicyConfig
from oterminus.structured_commands import StructuredCommandError, parse_raw_command_as_structured
from oterminus.validator import Validator


def make_proposal(
    command: str, *, mode: ProposalMode | None = None, command_family: str | None = None
) -> Proposal:
    if mode is None:
        try:
            parsed = parse_raw_command_as_structured(command)
        except StructuredCommandError:
            parsed = None
        if parsed is not None:
            parsed_family, parsed_arguments = parsed
            mode = ProposalMode.STRUCTURED
            command_family = parsed_family
            return Proposal(
                action_type=ActionType.SHELL_COMMAND,
                mode=mode,
                command_family=command_family,
                arguments=parsed_arguments,
                command=command,
                summary="test",
                explanation="test",
                risk_level=RiskLevel.SAFE,
                needs_confirmation=True,
                notes=[],
            )
        mode = ProposalMode.EXPERIMENTAL

    return Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=mode,
        command_family=command_family or command.split()[0],
        command=command,
        summary="test",
        explanation="test",
        risk_level=RiskLevel.SAFE,
        needs_confirmation=True,
        notes=[],
    )


def test_accept_safe_command() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    result = validator.validate(make_proposal("ls -lh"))
    assert result.accepted is True
    assert result.risk_level == RiskLevel.SAFE


def test_accept_cd_command() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    result = validator.validate(make_proposal("cd src"))
    assert result.accepted is True
    assert result.risk_level == RiskLevel.SAFE


def test_reject_chained_command() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.DANGEROUS, allow_dangerous=True))
    result = validator.validate(make_proposal("ls && pwd"))
    assert result.accepted is False
    assert any("blocked command chaining" in reason for reason in result.reasons)


def test_reject_background_execution() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.DANGEROUS, allow_dangerous=True))
    result = validator.validate(make_proposal("sleep 1 &"))
    assert result.accepted is False
    assert any("blocked background execution" in reason for reason in result.reasons)


def test_policy_blocks_dangerous() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    result = validator.validate(make_proposal("rm -rf tmp"))
    assert result.accepted is False
    assert result.risk_level == RiskLevel.DANGEROUS


def test_reject_unsupported_flag_for_curated_command() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    result = validator.validate(make_proposal("cat -n README.md"))

    assert result.accepted is False
    assert any("Unsupported flag '-n' for command 'cat'." in reason for reason in result.reasons)


def test_reject_missing_required_operands() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    result = validator.validate(make_proposal("mv draft.txt"))

    assert result.accepted is False
    assert any("requires at least 2 operand" in reason for reason in result.reasons)


def test_accept_short_flag_clusters_for_curated_safe_commands() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    result = validator.validate(make_proposal("grep -Finr -m2 TODO src"))

    assert result.accepted is True
    assert result.risk_level == RiskLevel.SAFE


def test_accept_inline_value_flag_for_curated_safe_command() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    result = validator.validate(make_proposal("tail -c32 README.md"))

    assert result.accepted is True
    assert result.risk_level == RiskLevel.SAFE


def test_reject_open_url_target() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    result = validator.validate(make_proposal("open https://example.com"))

    assert result.accepted is False
    assert any("does not allow these operand targets" in reason for reason in result.reasons)


def test_validator_rejects_platform_unsupported_command(monkeypatch) -> None:
    monkeypatch.setattr("oterminus.commands.registry.sys.platform", "linux")
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    result = validator.validate(make_proposal("open ."))
    assert result.accepted is False
    assert any("unavailable on platform 'linux'" in reason for reason in result.reasons)


def test_validator_accepts_open_on_darwin(monkeypatch) -> None:
    monkeypatch.setattr("oterminus.commands.registry.sys.platform", "darwin")
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    result = validator.validate(make_proposal("open ."))
    assert result.accepted is True


@pytest.mark.parametrize(
    ("command", "expected_risk"),
    [
        ("whoami", RiskLevel.SAFE),
        ("clear", RiskLevel.SAFE),
        ("uname -a", RiskLevel.SAFE),
        ("which python3", RiskLevel.SAFE),
        ("env PATH", RiskLevel.SAFE),
        ("df", RiskLevel.SAFE),
        ("df -h .", RiskLevel.SAFE),
        ("cp src.txt dst.txt", RiskLevel.WRITE),
        ("mv old.txt new.txt", RiskLevel.WRITE),
        ("du .", RiskLevel.SAFE),
        ("stat README.md", RiskLevel.SAFE),
        ("head -n 20 README.md", RiskLevel.SAFE),
        ("tail -c 64 README.md", RiskLevel.SAFE),
        ("grep -r TODO src", RiskLevel.SAFE),
        ("cat README.md", RiskLevel.SAFE),
        ("file README.md", RiskLevel.SAFE),
        ("ps -Af", RiskLevel.SAFE),
        ("pgrep -fl python", RiskLevel.SAFE),
        ("lsof -anP .", RiskLevel.SAFE),
        ("wc -l README.md", RiskLevel.SAFE),
        ("sort -ru README.md", RiskLevel.SAFE),
        ("uniq -c README.md", RiskLevel.SAFE),
        ("git status --short", RiskLevel.SAFE),
        ("git branch --show-current", RiskLevel.SAFE),
        ("git log --oneline -n 5", RiskLevel.SAFE),
        ("tar -tf archive.tar", RiskLevel.SAFE),
        ("tar -xf archive.tar -C out", RiskLevel.WRITE),
        ("tar -czf backup.tar.gz src README.md", RiskLevel.WRITE),
        ("unzip -l archive.zip", RiskLevel.SAFE),
        ("unzip archive.zip -d restore", RiskLevel.WRITE),
        ("zip -r backup.zip src README.md", RiskLevel.WRITE),
    ],
)
def test_risk_classification_for_next_wave_structured_families(
    command: str, expected_risk: RiskLevel
) -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    result = validator.validate(make_proposal(command))

    assert result.accepted is True
    assert result.risk_level == expected_risk


@pytest.mark.parametrize(
    "command",
    [
        "uname --bad",
        "clear now",
        "which",
        "env",
        "env PATH HOME",
        "cp src.txt",
        "mv draft.txt",
        "du --bad .",
        "stat",
        "head -n 20",
        "tail -c 64",
        "grep -z TODO src",
        "cat -n README.md",
        "open https://example.com",
        "file",
        "ps -z",
        "pgrep -z python",
        "lsof -x",
        "wc -z README.md",
        "sort",
        "git add .",
        "git commit -m x",
        "git reset --hard",
        "git push",
        "tar -xf archive.tar",
        "tar --extract -f archive.tar",
        "tar -xf archive.tar -C /",
        "tar --strip-components 1 -xf archive.tar -C out",
        "tar --transform s/a/b/ -xf archive.tar -C out",
        "tar -czf backup.tar.gz /",
        "tar -czf backup.tar.gz '*'",
        "tar -cf backup.tar src",
        "unzip archive.zip",
        "unzip -o archive.zip",
        "zip backup.zip file.txt",
        "zip -r backup.zip /",
        "zip -r backup.zip ~",
        "zip -e backup.zip file.txt",
        "zip --password secret backup.zip file.txt",
    ],
)
def test_acceptance_rejects_invalid_next_wave_variants(command: str) -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    result = validator.validate(make_proposal(command))

    assert result.accepted is False


def test_validator_rejects_env_with_more_than_one_operand() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    result = validator.validate(make_proposal("env PATH HOME"))

    assert result.accepted is False
    assert any("allows at most 1 operand" in reason for reason in result.reasons)


def test_validator_warns_about_environment_secrets_for_env_lookup() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    result = validator.validate(make_proposal("env PATH"))

    assert result.accepted is True
    assert any("Environment values may include secrets" in warning for warning in result.warnings)


def test_validator_warns_for_synthetic_network_touching_command(monkeypatch) -> None:
    spec = command_spec(
        name="netcheck",
        category="network_inspection",
        capability_id="synthetic_network",
        capability_label="Synthetic network",
        capability_description="Synthetic read-only network diagnostics.",
        risk_level=RiskLevel.SAFE,
        min_operands=1,
        max_operands=1,
        network_touching=True,
    )
    monkeypatch.setitem(COMMAND_REGISTRY, "netcheck", spec)
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))

    result = validator.validate(make_proposal("netcheck example.test"))

    assert result.accepted is True
    assert result.warnings == [
        "Experimental mode stays outside deterministic structured rendering and uses stricter confirmation.",
        NETWORK_TOUCHING_WARNING,
    ]


def test_allowed_roots_find_checks_only_search_roots() -> None:
    validator = Validator(
        PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False, allowed_roots=["/allowed"])
    )
    result = validator.validate(make_proposal("find /allowed -name '*.py'"))
    assert result.accepted is True


def test_allowed_roots_find_with_leading_option_still_checks_path_operands() -> None:
    validator = Validator(
        PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False, allowed_roots=["/allowed"])
    )
    result = validator.validate(make_proposal("find -L /etc -name '*.conf'"))
    assert result.accepted is False
    assert any("Paths outside allowed roots" in reason for reason in result.reasons)


def test_allowed_roots_find_without_explicit_path_does_not_treat_predicate_arg_as_root() -> None:
    validator = Validator(
        PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False, allowed_roots=["/allowed"])
    )
    result = validator.validate(make_proposal("find -path '/etc/*'"))
    assert result.accepted is True


def test_allowed_roots_blocks_disallowed_path_operand() -> None:
    validator = Validator(
        PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False, allowed_roots=["/allowed"])
    )
    result = validator.validate(make_proposal("cat /etc/passwd"))
    assert result.accepted is False
    assert any("Paths outside allowed roots" in reason for reason in result.reasons)


def test_allowed_roots_chmod_reference_equals_validates_target_path() -> None:
    validator = Validator(
        PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False, allowed_roots=["/allowed"])
    )
    result = validator.validate(make_proposal("chmod --reference=/allowed/ref /etc/shadow"))
    assert result.accepted is False
    assert any("Paths outside allowed roots" in reason for reason in result.reasons)


def test_allowed_roots_grep_pattern_file_is_checked() -> None:
    validator = Validator(
        PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False, allowed_roots=["/allowed"])
    )
    result = validator.validate(make_proposal("grep -f /etc/patterns /allowed/input.txt"))
    assert result.accepted is False
    assert any("Paths outside allowed roots" in reason for reason in result.reasons)


def test_allowed_roots_grep_pattern_file_stdin_sentinel_is_not_treated_as_path() -> None:
    validator = Validator(
        PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False, allowed_roots=["/allowed"])
    )
    result = validator.validate(make_proposal("grep -f - /allowed/input.txt"))
    assert result.accepted is True


def test_allowed_roots_cp_checks_both_source_and_destination() -> None:
    validator = Validator(
        PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False, allowed_roots=["/allowed"])
    )
    result = validator.validate(make_proposal("cp /allowed/in.txt /etc/out.txt"))

    assert result.accepted is False
    assert any("Paths outside allowed roots" in reason for reason in result.reasons)


def test_allowed_roots_chmod_reference_path_is_checked() -> None:
    validator = Validator(
        PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False, allowed_roots=["/allowed"])
    )
    result = validator.validate(make_proposal("chmod --reference=/etc/ref /allowed/target.txt"))
    assert result.accepted is False
    assert any("Paths outside allowed roots" in reason for reason in result.reasons)


def test_structured_only_proposal_is_previewable_but_not_executable() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    proposal = Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=ProposalMode.STRUCTURED,
        command_family="grep",
        arguments={
            "pattern": "TODO",
            "paths": ["src"],
            "ignore_case": True,
            "line_number": True,
            "fixed_strings": False,
            "recursive": True,
            "files_with_matches": False,
            "max_count": 2,
        },
        summary="find todo markers",
        explanation="structured grep plan",
        risk_level=RiskLevel.SAFE,
        needs_confirmation=True,
        notes=[],
    )

    result = validator.validate(proposal)

    assert result.accepted is True
    assert result.risk_level == RiskLevel.SAFE
    assert result.rendered_command == "grep -i -n -r -m 2 TODO src"
    assert result.argv == ["grep", "-i", "-n", "-r", "-m", "2", "TODO", "src"]


def test_validator_accepts_structured_archive_inspection_proposal() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    proposal = Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=ProposalMode.STRUCTURED,
        command_family="tar",
        arguments={"operation": "list", "archive_path": "archive.tar"},
        summary="list archive",
        explanation="read-only archive inspection",
        risk_level=RiskLevel.SAFE,
        needs_confirmation=True,
        notes=[],
    )

    result = validator.validate(proposal)

    assert result.accepted is True
    assert result.risk_level == RiskLevel.SAFE
    assert result.rendered_command == "tar -tf archive.tar"
    assert result.argv == ["tar", "-tf", "archive.tar"]


def test_validator_accepts_structured_archive_extraction_proposal() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    proposal = Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=ProposalMode.STRUCTURED,
        command_family="tar",
        arguments={
            "operation": "extract_tar",
            "archive_path": "archive.tar",
            "destination_path": "out",
        },
        summary="extract archive",
        explanation="guarded archive extraction",
        risk_level=RiskLevel.WRITE,
        needs_confirmation=True,
        notes=[],
    )

    result = validator.validate(proposal)

    assert result.accepted is True
    assert result.risk_level == RiskLevel.WRITE
    assert result.rendered_command == "tar -xf archive.tar -C out"
    assert result.argv == ["tar", "-xf", "archive.tar", "-C", "out"]
    assert any("Archive extraction can write or overwrite files" in w for w in result.warnings)


def test_validator_accepts_structured_tar_gz_creation_proposal() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    proposal = Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=ProposalMode.STRUCTURED,
        command_family="tar",
        arguments={
            "operation": "create_tar_gz",
            "archive_path": "backup.tar.gz",
            "source_paths": ["src", "README.md"],
        },
        summary="create archive",
        explanation="guarded archive creation",
        risk_level=RiskLevel.WRITE,
        needs_confirmation=True,
        notes=[],
    )

    result = validator.validate(proposal)

    assert result.accepted is True
    assert result.risk_level == RiskLevel.WRITE
    assert result.rendered_command == "tar -czf backup.tar.gz src README.md"
    assert result.argv == ["tar", "-czf", "backup.tar.gz", "src", "README.md"]
    assert any("Archive creation is write-risk" in w for w in result.warnings)


def test_validator_accepts_structured_zip_creation_proposal() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    proposal = Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=ProposalMode.STRUCTURED,
        command_family="zip",
        arguments={
            "operation": "create_zip",
            "archive_path": "backup.zip",
            "source_paths": ["src", "README.md"],
        },
        summary="create zip archive",
        explanation="guarded archive creation",
        risk_level=RiskLevel.WRITE,
        needs_confirmation=True,
        notes=[],
    )

    result = validator.validate(proposal)

    assert result.accepted is True
    assert result.risk_level == RiskLevel.WRITE
    assert result.rendered_command == "zip -r backup.zip src README.md"
    assert result.argv == ["zip", "-r", "backup.zip", "src", "README.md"]
    assert any("Archive creation is write-risk" in w for w in result.warnings)


def test_validator_accepts_direct_guarded_zip_extraction() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    result = validator.validate(make_proposal("unzip archive.zip -d restore"))

    assert result.accepted is True
    assert result.risk_level == RiskLevel.WRITE
    assert result.argv == ["unzip", "archive.zip", "-d", "restore"]


def test_validator_rejects_archive_extraction_in_safe_policy() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.SAFE, allow_dangerous=False))
    result = validator.validate(make_proposal("tar -xf archive.tar -C out"))

    assert result.accepted is False
    assert result.risk_level == RiskLevel.WRITE
    assert any("Risk level 'write' blocked" in reason for reason in result.reasons)


def test_validator_rejects_archive_creation_in_safe_policy() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.SAFE, allow_dangerous=False))
    result = validator.validate(make_proposal("zip -r backup.zip src"))

    assert result.accepted is False
    assert result.risk_level == RiskLevel.WRITE
    assert any("Risk level 'write' blocked" in reason for reason in result.reasons)


def test_validator_rejects_unsafe_direct_archive_path() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    result = validator.validate(
        make_proposal(
            "unzip -l https://example.com/archive.zip",
            mode=ProposalMode.EXPERIMENTAL,
            command_family="unzip",
        )
    )

    assert result.accepted is False
    assert any("Only guarded zip archive operations" in reason for reason in result.reasons)


def test_validator_rejects_unsafe_direct_archive_extraction_forms() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))

    for command in (
        "tar -xf archive.tar",
        "unzip archive.zip",
        "unzip -o archive.zip -d restore",
        "tar -xf archive.tar -C /",
        "tar --strip-components 1 -xf archive.tar -C out",
        "tar --transform s/a/b/ -xf archive.tar -C out",
    ):
        result = validator.validate(
            make_proposal(
                command, mode=ProposalMode.EXPERIMENTAL, command_family=command.split()[0]
            )
        )
        assert result.accepted is False, command


def test_validator_rejects_unsafe_direct_archive_creation_forms() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))

    for command in (
        "tar -czf backup.tar.gz /",
        "tar -czf backup.tar.gz '*'",
        "zip -r backup.zip /",
        "zip -r backup.zip ~",
        "zip -e backup.zip file.txt",
        "zip --password secret backup.zip file.txt",
    ):
        result = validator.validate(
            make_proposal(
                command, mode=ProposalMode.EXPERIMENTAL, command_family=command.split()[0]
            )
        )
        assert result.accepted is False, command


def test_validator_archive_allowed_roots_checks_archive_and_destination() -> None:
    validator = Validator(
        PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False, allowed_roots=["/allowed"])
    )

    assert validator.validate(make_proposal("tar -xf /allowed/a.tar -C /allowed/out")).accepted

    result = validator.validate(make_proposal("tar -xf /etc/a.tar -C /allowed/out"))
    assert result.accepted is False
    assert any("Paths outside allowed roots" in reason for reason in result.reasons)

    result = validator.validate(make_proposal("unzip /allowed/a.zip -d /etc/out"))
    assert result.accepted is False
    assert any("Paths outside allowed roots" in reason for reason in result.reasons)


def test_validator_archive_creation_allowed_roots_checks_archive_and_sources() -> None:
    validator = Validator(
        PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False, allowed_roots=["/allowed"])
    )

    assert validator.validate(make_proposal("zip -r /allowed/a.zip /allowed/src")).accepted

    result = validator.validate(make_proposal("zip -r /etc/a.zip /allowed/src"))
    assert result.accepted is False
    assert any("Paths outside allowed roots" in reason for reason in result.reasons)

    result = validator.validate(make_proposal("tar -czf /allowed/a.tar.gz /etc/src"))
    assert result.accepted is False
    assert any("Paths outside allowed roots" in reason for reason in result.reasons)


def test_reject_unknown_command_family() -> None:
    proposal = Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=ProposalMode.EXPERIMENTAL,
        command_family="python",
        command="python script.py",
        summary="unknown family",
        explanation="not allowlisted",
        risk_level=RiskLevel.SAFE,
        needs_confirmation=True,
        notes=[],
    )

    validator = Validator(PolicyConfig(mode=RiskLevel.DANGEROUS, allow_dangerous=True))
    result = validator.validate(proposal)

    assert result.accepted is False
    assert any(
        "Command family 'python' is not in the v1 allowlist." in reason for reason in result.reasons
    )


def test_structured_command_with_disallowed_root_is_rejected() -> None:
    validator = Validator(
        PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False, allowed_roots=["/allowed"])
    )
    proposal = Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=ProposalMode.STRUCTURED,
        command_family="open",
        arguments={"path": "/etc/hosts", "reveal": False},
        summary="open hosts file",
        explanation="structured open",
        risk_level=RiskLevel.SAFE,
        needs_confirmation=True,
        notes=[],
    )

    result = validator.validate(proposal)

    assert result.accepted is False
    assert any("Paths outside allowed roots" in reason for reason in result.reasons)


def test_accept_experimental_command_with_warning() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    result = validator.validate(
        make_proposal("stat -f %z README.md", mode=ProposalMode.EXPERIMENTAL)
    )

    assert result.accepted is True
    assert result.risk_level == RiskLevel.SAFE
    assert any(
        "Experimental mode stays outside deterministic structured rendering" in warning
        for warning in result.warnings
    )


def test_structured_command_ignores_legacy_command_text() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    proposal = Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=ProposalMode.STRUCTURED,
        command_family="find",
        arguments={"path": ".", "name": "*.py"},
        command="find src -name '*.py'",
        summary="find python files",
        explanation="structured find stays authoritative",
        risk_level=RiskLevel.SAFE,
        needs_confirmation=True,
        notes=[],
    )

    result = validator.validate(proposal)

    assert result.accepted is True
    assert result.rendered_command == "find . -name '*.py'"
    assert any(
        "Structured mode ignores the deprecated command field" in warning
        for warning in result.warnings
    )
    assert any(
        "Legacy command text differs from deterministic structured rendering and was ignored."
        in warning
        for warning in result.warnings
    )


def test_reject_experimental_when_structured_rendering_is_available() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    result = validator.validate(
        make_proposal("find . -name '*.py'", mode=ProposalMode.EXPERIMENTAL)
    )

    assert result.accepted is False
    assert any(
        "Experimental mode is not allowed when deterministic structured rendering is available."
        in reason
        for reason in result.reasons
    )


def test_blocked_maturity_command_is_rejected_even_in_dangerous_mode() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.DANGEROUS, allow_dangerous=True))
    result = validator.validate(make_proposal("sudo ls /var/root", mode=ProposalMode.EXPERIMENTAL))

    assert result.accepted is False
    assert any("blocked by curated command maturity policy" in reason for reason in result.reasons)


def test_validator_rejects_command_from_disabled_pack() -> None:
    validator = Validator(PolicyConfig(disabled_command_packs=frozenset({"process"})))
    result = validator.validate(make_proposal("ps -Af"))

    assert result.accepted is False
    assert any("command pack 'process' is disabled" in reason for reason in result.reasons)


def test_validator_accepts_command_when_pack_enabled() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    result = validator.validate(make_proposal("ps -Af"))

    assert result.accepted is True


def test_validator_rejects_archive_command_from_disabled_pack() -> None:
    validator = Validator(PolicyConfig(disabled_command_packs=frozenset({"archive"})))
    result = validator.validate(make_proposal("tar -tf archive.tar"))

    assert result.accepted is False
    assert any("command pack 'archive' is disabled" in reason for reason in result.reasons)
