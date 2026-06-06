import oterminus.direct_commands as direct_commands
from oterminus.direct_commands import detect_direct_command
from oterminus.models import ProposalMode
from oterminus.structured_commands import StructuredCommandError


def test_detect_direct_command_for_cd() -> None:
    proposal = detect_direct_command("cd src")

    assert proposal is not None
    assert proposal.mode == ProposalMode.EXPERIMENTAL
    assert proposal.command_family == "cd"
    assert proposal.command == "cd src"


def test_detect_direct_command_rejects_natural_language_find() -> None:
    proposal = detect_direct_command("find all .py files")

    assert proposal is None


def test_detect_direct_command_for_new_curated_family() -> None:
    proposal = detect_direct_command("open .", platform_id="darwin")

    assert proposal is not None
    assert proposal.mode == ProposalMode.STRUCTURED
    assert proposal.command_family == "open"
    assert proposal.command is None


def test_detect_direct_command_for_process_family() -> None:
    proposal = detect_direct_command("ps -Af")

    assert proposal is not None
    assert proposal.mode == ProposalMode.STRUCTURED
    assert proposal.command_family == "ps"


def test_detect_direct_command_for_system_family() -> None:
    proposal = detect_direct_command("whoami")

    assert proposal is not None
    assert proposal.mode == ProposalMode.STRUCTURED
    assert proposal.command_family == "whoami"


def test_detect_direct_command_for_clear() -> None:
    proposal = detect_direct_command("clear")

    assert proposal is not None
    assert proposal.mode == ProposalMode.STRUCTURED
    assert proposal.command_family == "clear"


def test_detect_direct_command_preserves_registry_notes() -> None:
    proposal = detect_direct_command("cd src")

    assert proposal is not None
    assert any("working directory" in note for note in proposal.notes)


def test_detect_direct_command_falls_back_when_structured_parse_errors(monkeypatch) -> None:
    def _raise(_: str) -> None:
        raise StructuredCommandError("boom")

    monkeypatch.setattr(direct_commands, "parse_raw_command_as_structured", _raise)

    proposal = detect_direct_command("open .", platform_id="darwin")

    assert proposal is not None
    assert proposal.mode == ProposalMode.EXPERIMENTAL
    assert proposal.command == "open ."
    assert any("Structured parsing skipped: boom" in note for note in proposal.notes)


def test_detect_direct_command_respects_disabled_packs() -> None:
    proposal = detect_direct_command("ps -Af", disabled_pack_ids=frozenset({"process"}))

    assert proposal is None


def test_detect_direct_command_respects_disabled_archive_pack() -> None:
    proposal = detect_direct_command(
        "tar -tf archive.tar", disabled_pack_ids=frozenset({"archive"})
    )

    assert proposal is None


def test_detect_direct_command_respects_platform_support() -> None:
    assert detect_direct_command("open .", platform_id="linux") is None
    assert detect_direct_command("open .", platform_id="darwin") is not None


def test_detect_direct_command_for_supported_git_inspection() -> None:
    proposal = detect_direct_command("git status --short")

    assert proposal is not None
    assert proposal.mode == ProposalMode.STRUCTURED
    assert proposal.command_family == "git"


def test_detect_direct_command_rejects_unsupported_git_subcommand() -> None:
    assert detect_direct_command("git add .") is None


def test_detect_direct_command_for_supported_archive_inspection() -> None:
    tar_proposal = detect_direct_command("tar -tf archive.tar")
    unzip_proposal = detect_direct_command("unzip -l archive.zip")

    assert tar_proposal is not None
    assert tar_proposal.mode == ProposalMode.STRUCTURED
    assert tar_proposal.command_family == "tar"
    assert unzip_proposal is not None
    assert unzip_proposal.mode == ProposalMode.STRUCTURED
    assert unzip_proposal.command_family == "unzip"


def test_detect_direct_command_for_supported_archive_extraction() -> None:
    tar_proposal = detect_direct_command("tar -xf archive.tar -C out")
    unzip_proposal = detect_direct_command("unzip archive.zip -d restore")

    assert tar_proposal is not None
    assert tar_proposal.mode == ProposalMode.STRUCTURED
    assert tar_proposal.command_family == "tar"
    assert tar_proposal.arguments == {
        "operation": "extract_tar",
        "archive_path": "archive.tar",
        "destination_path": "out",
    }
    assert unzip_proposal is not None
    assert unzip_proposal.mode == ProposalMode.STRUCTURED
    assert unzip_proposal.command_family == "unzip"


def test_detect_direct_command_for_supported_archive_creation() -> None:
    tar_proposal = detect_direct_command("tar -czf backup.tar.gz src README.md")
    zip_proposal = detect_direct_command("zip -r backup.zip src README.md")

    assert tar_proposal is not None
    assert tar_proposal.mode == ProposalMode.STRUCTURED
    assert tar_proposal.command_family == "tar"
    assert tar_proposal.arguments == {
        "operation": "create_tar_gz",
        "archive_path": "backup.tar.gz",
        "source_paths": ["src", "README.md"],
    }
    assert zip_proposal is not None
    assert zip_proposal.mode == ProposalMode.STRUCTURED
    assert zip_proposal.command_family == "zip"
    assert zip_proposal.arguments == {
        "operation": "create_zip",
        "archive_path": "backup.zip",
        "source_paths": ["src", "README.md"],
    }


def test_detect_direct_command_for_supported_network_diagnostics() -> None:
    ping = detect_direct_command("ping -c 4 example.com")
    curl = detect_direct_command("curl -I https://example.com")
    dig = detect_direct_command("dig example.com")
    nslookup = detect_direct_command("nslookup example.com")

    assert ping is not None
    assert ping.mode == ProposalMode.STRUCTURED
    assert ping.command_family == "ping"
    assert ping.arguments == {"host": "example.com", "count": 4}
    assert curl is not None
    assert curl.mode == ProposalMode.STRUCTURED
    assert curl.command_family == "curl"
    assert dig is not None
    assert dig.mode == ProposalMode.STRUCTURED
    assert dig.command_family == "dig"
    assert nslookup is not None
    assert nslookup.mode == ProposalMode.STRUCTURED
    assert nslookup.command_family == "nslookup"


def test_detect_direct_command_rejects_unsupported_network_forms() -> None:
    assert detect_direct_command("ping example.com") is None
    assert detect_direct_command("ping -f example.com") is None
    assert detect_direct_command("curl -X POST https://example.com") is None
    assert detect_direct_command("curl -d x=1 https://example.com") is None
    assert detect_direct_command("curl -o out https://example.com") is None
    assert detect_direct_command("dig +short example.com") is None
    assert detect_direct_command("wget https://example.com") is None


def test_detect_direct_command_respects_disabled_network_pack() -> None:
    proposal = detect_direct_command(
        "ping -c 4 example.com", disabled_pack_ids=frozenset({"network"})
    )

    assert proposal is None


def test_detect_direct_command_respects_developer_profile_disabled_packs() -> None:
    proposal = detect_direct_command(
        "ping -c 4 example.com", disabled_pack_ids=frozenset({"dangerous", "network"})
    )

    assert proposal is None


def test_detect_direct_command_respects_beginner_profile_disabled_packs() -> None:
    proposal = detect_direct_command(
        "git status --short",
        disabled_pack_ids=frozenset(
            {"archive", "dangerous", "git", "macos", "network", "process", "project"}
        ),
    )

    assert proposal is None


def test_detect_direct_command_respects_power_profile_dangerous_pack() -> None:
    proposal = detect_direct_command("rm -rf build", disabled_pack_ids=frozenset({"dangerous"}))

    assert proposal is None


def test_detect_direct_command_routes_unsupported_archive_forms_to_validator() -> None:
    tar_proposal = detect_direct_command("tar -xf archive.tar")
    unzip_proposal = detect_direct_command("unzip archive.zip")

    assert tar_proposal is not None
    assert tar_proposal.mode == ProposalMode.EXPERIMENTAL
    assert tar_proposal.command_family == "tar"
    assert unzip_proposal is not None
    assert unzip_proposal.mode == ProposalMode.EXPERIMENTAL
    assert unzip_proposal.command_family == "unzip"


def test_detect_direct_command_routes_archive_creation_to_validator() -> None:
    proposal = detect_direct_command("tar -czf backup.tar.gz /")

    assert proposal is not None
    assert proposal.mode == ProposalMode.EXPERIMENTAL
    assert proposal.command_family == "tar"


def test_detect_direct_command_routes_unsupported_zip_creation_to_validator() -> None:
    proposal = detect_direct_command("zip backup.zip file.txt")

    assert proposal is not None
    assert proposal.mode == ProposalMode.EXPERIMENTAL
    assert proposal.command_family == "zip"


def test_detect_direct_command_routes_unsafe_archive_operands_to_validator() -> None:
    assert detect_direct_command("tar -tf '*.tar'") is not None
    assert detect_direct_command("unzip -l https://example.com/archive.zip") is not None
    assert detect_direct_command("unzip -o archive.zip -d restore") is not None
    assert detect_direct_command("zip -e backup.zip file.txt") is not None


def test_detect_direct_command_allows_archive_natural_language_to_reach_planner() -> None:
    assert detect_direct_command("unzip backup.zip into ./restore") is None
    assert detect_direct_command("zip this") is None


def test_detect_direct_command_rejects_exact_project_health_forms() -> None:
    assert detect_direct_command("poetry run pytest") is None
    assert detect_direct_command("poetry run ruff format --check .") is None


def test_detect_direct_command_rejects_non_exact_project_health_forms() -> None:
    assert detect_direct_command("poetry run pytest tests/test_validator.py") is None
    assert detect_direct_command("poetry run ruff format .") is None
