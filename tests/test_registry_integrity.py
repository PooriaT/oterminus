from __future__ import annotations

from pathlib import Path

from oterminus.commands import COMMAND_PACKS, COMMAND_REGISTRY, MaturityLevel, supported_base_commands, supported_categories
from oterminus.completion import build_repl_completions
from oterminus.models import RiskLevel
from oterminus.prompts import build_system_prompt
from oterminus.structured_commands import STRUCTURED_ARGUMENT_MODELS, supports_structured_family


def _completion_texts(candidates) -> set[str]:
    return {candidate.text for candidate in candidates}


def test_command_pack_names_are_globally_unique() -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for pack in COMMAND_PACKS:
        for spec in pack:
            if spec.name in seen:
                duplicates.add(spec.name)
            seen.add(spec.name)

    assert not duplicates


def test_registry_specs_have_required_metadata() -> None:
    for spec in COMMAND_REGISTRY.values():
        assert spec.capability_id.strip()
        assert spec.category.strip()
        assert isinstance(spec.risk_level, RiskLevel)


def test_registry_flag_metadata_is_consistent() -> None:
    for spec in COMMAND_REGISTRY.values():
        assert spec.allowed_flags.isdisjoint(spec.dangerous_flags)
        assert spec.flags_with_values.issubset(spec.allowed_flags | spec.flags_with_values)
        assert spec.path_valued_flags.issubset(spec.flags_with_values)


def test_direct_supported_commands_define_detection_metadata() -> None:
    for spec in COMMAND_REGISTRY.values():
        if not spec.direct_supported:
            continue

        assert spec.min_operands >= 0
        assert spec.direct_detection_mode is not None


def test_structured_maturity_commands_have_structured_renderer() -> None:
    for spec in COMMAND_REGISTRY.values():
        if spec.maturity_level != MaturityLevel.STRUCTURED:
            continue

        assert spec.name in STRUCTURED_ARGUMENT_MODELS
        assert supports_structured_family(spec.name)


def test_blocked_or_dangerous_commands_are_not_marked_safe() -> None:
    for spec in COMMAND_REGISTRY.values():
        if spec.maturity_level == MaturityLevel.BLOCKED:
            assert spec.risk_level == RiskLevel.DANGEROUS

        if spec.dangerous_flags or spec.dangerous_target_literals:
            assert spec.risk_level != RiskLevel.SAFE


def test_supported_base_commands_is_stable_and_sorted() -> None:
    commands = supported_base_commands()

    assert commands == tuple(sorted(commands))
    assert len(commands) == len(set(commands))


def test_supported_categories_match_expected_registry_values() -> None:
    assert supported_categories() == (
        "destructive",
        "filesystem_write",
        "inspection",
        "macos_integration",
        "navigation",
        "permissions",
        "privileged",
        "process_inspection",
        "search",
        "system_inspection",
    )


def test_autocomplete_uses_registry_metadata_for_first_token(tmp_path: Path) -> None:
    candidates = _completion_texts(build_repl_completions("", cwd=tmp_path))

    for command_name in supported_base_commands():
        assert command_name in candidates


def test_planner_system_prompt_stays_compact() -> None:
    prompt = build_system_prompt()

    # Guardrail to avoid unbounded growth as metadata expands.
    assert len(prompt) < 12000
