from __future__ import annotations

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
