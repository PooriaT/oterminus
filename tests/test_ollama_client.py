import pytest
from ollama import ResponseError

import oterminus.ollama_client as ollama_client
from oterminus.ollama_client import OllamaClientError, OllamaPlannerClient, proposal_output_schema


class _FakeOllamaClient:
    def __init__(self, response: dict[str, object] | None = None, error: Exception | None = None):
        self.response = response or {"message": {"content": '{"ok": true}'}}
        self.error = error
        self.calls: list[dict[str, object]] = []

    def chat(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


def test_chat_json_sends_json_schema_format_and_temperature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeOllamaClient()
    monkeypatch.setattr(ollama_client, "Client", lambda: fake)
    schema = proposal_output_schema()

    client = OllamaPlannerClient("gemma4")
    content = client.chat_json("system", "user", output_schema=schema)

    assert content == '{"ok": true}'
    call = fake.calls[0]
    assert call["model"] == "gemma4"
    assert call["format"] == schema
    assert call["options"] == {"temperature": 0}


def test_proposal_output_schema_requires_all_top_level_proposal_fields() -> None:
    schema = proposal_output_schema()

    assert schema["properties"]["needs_confirmation"] == {"type": "boolean", "enum": [True]}
    assert "oneOf" not in schema
    assert schema["required"] == [
        "action_type",
        "mode",
        "command_family",
        "arguments",
        "command",
        "summary",
        "explanation",
        "risk_level",
        "needs_confirmation",
        "notes",
    ]


def test_chat_json_allows_explicit_temperature(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeOllamaClient()
    monkeypatch.setattr(ollama_client, "Client", lambda: fake)

    client = OllamaPlannerClient("gemma4")
    client.chat_json("system", "user", output_schema=proposal_output_schema(), temperature=0.2)

    assert fake.calls[0]["options"] == {"temperature": 0.2}


def test_chat_json_defaults_to_json_format_without_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeOllamaClient()
    monkeypatch.setattr(ollama_client, "Client", lambda: fake)

    client = OllamaPlannerClient("gemma4")
    client.chat_json("system", "user")

    assert fake.calls[0]["format"] == "json"


def test_chat_json_response_error_handling_is_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeOllamaClient(error=ResponseError("bad response", 500))
    monkeypatch.setattr(ollama_client, "Client", lambda: fake)

    client = OllamaPlannerClient("gemma4")

    with pytest.raises(OllamaClientError, match="Ollama response error"):
        client.chat_json("system", "user", output_schema=proposal_output_schema())


def test_chat_json_empty_response_handling_is_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeOllamaClient(response={"message": {"content": ""}})
    monkeypatch.setattr(ollama_client, "Client", lambda: fake)

    client = OllamaPlannerClient("gemma4")

    with pytest.raises(OllamaClientError, match="empty planning response"):
        client.chat_json("system", "user", output_schema=proposal_output_schema())
