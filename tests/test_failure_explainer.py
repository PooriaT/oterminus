"""Compatibility test module for failure explainer behavior."""

from oterminus.failure_explainer import FailureExplainerConfig


def test_failure_explainer_config_defaults_to_disabled() -> None:
    assert FailureExplainerConfig().enabled is False
