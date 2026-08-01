"""Answer generation.

Two things v1 got wrong, fixed structurally here.

*Cancellation.* v1 ran the model call on a daemon thread and used
``thread.join(timeout=30)``. That returns control to the caller but does not stop the
request: the socket stays open and the quota keeps being spent. Here the timeout is a
client-level ``httpx.Timeout`` on the request itself, so expiry closes the connection.

*Streaming.* The answer streams, so the interface can show tokens as they arrive rather
than blocking behind a spinner for the whole generation.
"""

from __future__ import annotations

import abc
import json
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Any

import httpx

_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"

# Published Gemini 2.5 Flash rates, dollars per million tokens. Used only to turn
# measured token counts into a cost estimate, and labelled an estimate wherever it
# surfaces.
USD_PER_MTOK_IN = 0.30
USD_PER_MTOK_OUT = 2.50


class GenerationUnavailable(RuntimeError):
    pass


@dataclass(slots=True)
class GenerationUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def cost_usd(self) -> float:
        return (
            self.prompt_tokens * USD_PER_MTOK_IN + self.completion_tokens * USD_PER_MTOK_OUT
        ) / 1_000_000


class GenerationProvider(abc.ABC):
    name: str = "unset"

    @property
    @abc.abstractmethod
    def available(self) -> bool: ...

    @abc.abstractmethod
    def stream(
        self, system: str, user: str, history: Sequence[tuple[str, str]] = ()
    ) -> Iterator[str]: ...

    @abc.abstractmethod
    def usage(self) -> GenerationUsage: ...


class GeminiGeneration(GenerationProvider):
    def __init__(
        self,
        api_key: str | None,
        model: str = "gemini-2.5-flash",
        temperature: float = 0.2,
        timeout_seconds: float = 30.0,
        retry_attempts: int = 3,
        retry_max_seconds: float = 20.0,
    ) -> None:
        self.name = model
        self._key = api_key
        self._temperature = temperature
        self._usage = GenerationUsage()
        self._retry_attempts = retry_attempts
        self._retry_max_seconds = retry_max_seconds
        # Connect, read, write and pool timeouts are all bounded. A hung upstream cannot
        # hold a request open past this.
        self._timeout = httpx.Timeout(timeout_seconds, connect=min(10.0, timeout_seconds))

    @property
    def available(self) -> bool:
        return bool(self._key)

    def usage(self) -> GenerationUsage:
        return self._usage

    def stream(
        self, system: str, user: str, history: Sequence[tuple[str, str]] = ()
    ) -> Iterator[str]:
        if not self._key:
            raise GenerationUnavailable(
                "GOOGLE_API_KEY is not configured, so no answer can be generated. "
                "Retrieval still works and citations are still returned."
            )
        contents: list[dict[str, Any]] = [
            {
                "role": "user" if role == "human" else "model",
                "parts": [{"text": content}],
            }
            for role, content in history
        ]
        contents.append({"role": "user", "parts": [{"text": user}]})
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": contents,
            "generationConfig": {"temperature": self._temperature},
        }
        with (
            httpx.Client(timeout=self._timeout) as client,
            client.stream(
                "POST",
                f"{_GEMINI_BASE}/models/{self.name}:streamGenerateContent",
                params={"key": self._key, "alt": "sse"},
                json=payload,
            ) as response,
        ):
            response.raise_for_status()
            for line in response.iter_lines():
                if not line.startswith("data:"):
                    continue
                body = json.loads(line[5:].strip())
                usage = body.get("usageMetadata")
                if usage:
                    self._usage = GenerationUsage(
                        prompt_tokens=int(usage.get("promptTokenCount", 0)),
                        completion_tokens=int(usage.get("candidatesTokenCount", 0)),
                    )
                for candidate in body.get("candidates", []):
                    for part in candidate.get("content", {}).get("parts", []):
                        if text := part.get("text"):
                            yield str(text)


class UnavailableGeneration(GenerationProvider):
    """Stands in when no provider is configured, and says why."""

    name = "unavailable"

    def __init__(self, reason: str) -> None:
        self.reason = reason

    @property
    def available(self) -> bool:
        return False

    def stream(
        self,
        system: str,  # noqa: ARG002 - signature fixed by the GenerationProvider interface
        user: str,  # noqa: ARG002
        history: Sequence[tuple[str, str]] = (),  # noqa: ARG002
    ) -> Iterator[str]:
        raise GenerationUnavailable(self.reason)

    def usage(self) -> GenerationUsage:
        return GenerationUsage()
