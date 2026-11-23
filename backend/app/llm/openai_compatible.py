import json
import random
import time

from openai import APIConnectionError, APIStatusError, OpenAI, RateLimitError

from app.config import LLMSettings

from .base import Message, Reply, Tool, ToolCall, log_usage


class LLMError(RuntimeError):
    pass


class OpenAICompatibleLLM:
    def __init__(self, settings: LLMSettings) -> None:
        settings.validate_endpoint()
        self.settings = settings
        self.client = OpenAI(
            api_key=settings.api_key,
            base_url=settings.base_url,
            timeout=settings.timeout_s,
            max_retries=0,
        )

    def complete(
        self,
        messages: list[Message],
        tools: list[Tool],
        *,
        task_id: str,
        max_output_tokens: int | None = None,
        timeout_s: float | None = None,
    ) -> Reply:
        for attempt in range(self.settings.max_retries + 1):
            try:
                completion = self.client.chat.completions.create(
                    model=self.settings.model,
                    messages=messages,
                    timeout=min(self.settings.timeout_s, timeout_s)
                    if timeout_s is not None
                    else self.settings.timeout_s,
                    **(
                        {"max_tokens": max_output_tokens}
                        if max_output_tokens is not None
                        else {}
                    ),
                    **({"tools": tools} if tools else {}),
                )
                break
            except RateLimitError:
                if attempt == self.settings.max_retries:
                    raise LLMError(
                        f"Provider rate limit (429) after {attempt + 1} attempts"
                    ) from None
                delay = 2 ** min(attempt, 4)
                time.sleep(delay + random.uniform(0, delay / 2))
            except APIStatusError as exc:
                raise LLMError(f"Provider returned HTTP {exc.status_code}") from None
            except APIConnectionError:
                raise LLMError("Provider connection failed or timed out") from None

        usage = completion.usage
        input_tokens = usage.prompt_tokens if usage else None
        output_tokens = usage.completion_tokens if usage else None
        log_usage(
            task_id,
            "openai_compatible",
            self.settings.model,
            input_tokens,
            output_tokens,
        )
        if not completion.choices:
            raise LLMError("Provider returned no choices")
        message = completion.choices[0].message
        calls = []
        for call in message.tool_calls or ():
            if (
                call.type != "function"
                or not call.id
                or not call.function
                or not call.function.name
            ):
                raise LLMError("Invalid provider tool call")
            args = call.function.arguments
            try:
                arguments = json.loads(args) if isinstance(args, str) else args
            except ValueError:
                raise LLMError("Tool arguments contain invalid JSON") from None
            if not isinstance(arguments, dict):
                raise LLMError("Tool arguments must be an object")
            calls.append(ToolCall(call.id, call.function.name, arguments))

        return Reply(
            message.content or "",
            tuple(calls),
            input_tokens,
            output_tokens,
            message.model_dump(exclude_none=True),
        )

    def close(self) -> None:
        self.client.close()
