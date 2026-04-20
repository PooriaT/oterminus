from __future__ import annotations

import subprocess

from ollama import Client, ResponseError


class OllamaClientError(RuntimeError):
    pass


class OllamaPlannerClient:
    def __init__(self, model: str, host: str | None = None):
        self.model = model
        self.client = Client(host=host) if host else Client()

    def chat_json(self, system_prompt: str, user_prompt: str) -> str:
        try:
            response = self.client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                format="json",
            )
        except ResponseError as exc:
            raise OllamaClientError(f"Ollama response error: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise OllamaClientError(
                "Unable to reach Ollama. Ensure Ollama is running and the model is pulled."
            ) from exc

        message = response.get("message", {})
        content = message.get("content", "")
        if not content:
            raise OllamaClientError("Ollama returned an empty planning response.")
        return content


def list_installed_models() -> list[str]:
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise OllamaClientError(
            "Unable to run `ollama list`. Ensure Ollama is installed and available on PATH."
        ) from exc

    if result.returncode != 0:
        message = (result.stderr or result.stdout).strip() or "`ollama list` failed."
        raise OllamaClientError(message)

    return parse_ollama_list_output(result.stdout)


def parse_ollama_list_output(output: str) -> list[str]:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        return []

    if lines[0].lower().startswith("name"):
        lines = lines[1:]

    models: list[str] = []
    for line in lines:
        parts = line.split()
        if parts:
            models.append(parts[0])

    return list(dict.fromkeys(models))
