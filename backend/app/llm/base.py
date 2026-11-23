import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

Message = dict[str, Any]
Tool = dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class Reply:
    text: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    input_tokens: int | None = 0
    output_tokens: int | None = 0
    # Preserve provider-specific message fields for the next request (e.g. Gemini signatures).
    assistant_message: Message = field(default_factory=dict, repr=False)


class LLM(Protocol):
    def complete(
        self,
        messages: list[Message],
        tools: list[Tool],
        *,
        task_id: str,
        max_output_tokens: int | None = None,
        timeout_s: float | None = None,
    ) -> Reply: ...
    def close(self) -> None: ...


def log_usage(
    task_id: str,
    provider: str,
    model: str,
    input_tokens: int | None,
    output_tokens: int | None,
) -> None:
    logging.getLogger(__name__).info(
        "task_id=%s provider=%s model=%s input_tokens=%s output_tokens=%s",
        task_id,
        provider,
        model,
        input_tokens,
        output_tokens,
    )
