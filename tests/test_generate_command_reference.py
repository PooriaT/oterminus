from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "generate_command_reference.py"
SPEC = spec_from_file_location("generate_command_reference", MODULE_PATH)
assert SPEC and SPEC.loader
module = module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_generated_capability_map_includes_known_capabilities() -> None:
    content = module.generate_reference_docs()[module.CAPABILITY_MAP_PATH]
    for capability_id in (
        "filesystem_inspection",
        "text_inspection",
        "process_inspection",
        "system_inspection",
        "macos_desktop",
        "destructive_operations",
    ):
        assert capability_id in content


def test_generated_command_families_include_known_commands() -> None:
    content = module.generate_reference_docs()[module.COMMAND_FAMILIES_PATH]
    for command_name in ("`ls`", "`grep`", "`ps`", "`clear`", "`open`", "`rm`"):
        assert command_name in content


def test_output_is_deterministic() -> None:
    first = module.generate_reference_docs()
    second = module.generate_reference_docs()
    assert first == second


def test_check_mode_detects_stale_docs(tmp_path: Path, monkeypatch) -> None:
    cap = tmp_path / "capability-map.md"
    fam = tmp_path / "command-families.md"
    cap.write_text("stale\n", encoding="utf-8")
    fam.write_text("stale\n", encoding="utf-8")

    monkeypatch.setattr(module, "CAPABILITY_MAP_PATH", cap)
    monkeypatch.setattr(module, "COMMAND_FAMILIES_PATH", fam)
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)

    exit_code = module.main(["--check"])
    assert exit_code == 1


def test_write_then_check_round_trip(tmp_path: Path, monkeypatch) -> None:
    cap = tmp_path / "docs" / "reference" / "capability-map.md"
    fam = tmp_path / "docs" / "reference" / "command-families.md"

    monkeypatch.setattr(module, "CAPABILITY_MAP_PATH", cap)
    monkeypatch.setattr(module, "COMMAND_FAMILIES_PATH", fam)
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)

    assert module.main(["--write"]) == 0
    assert module.main(["--check"]) == 0
