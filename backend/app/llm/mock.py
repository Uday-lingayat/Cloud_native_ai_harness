import json
from collections.abc import Iterable
from dataclasses import replace

from .base import Message, Reply, Tool, log_usage


class MockLLM:
    def __init__(self, script: Iterable[Reply] = ()) -> None:
        self._script = iter(script)

    def complete(
        self,
        messages: list[Message],
        tools: list[Tool],
        *,
        task_id: str,
        max_output_tokens: int | None = None,
        timeout_s: float | None = None,
    ) -> Reply:
        reply = next(self._script, Reply())
        message: Message = {"role": "assistant", "content": reply.text}
        if reply.tool_calls:
            message["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": json.dumps(call.arguments),
                    },
                }
                for call in reply.tool_calls
            ]
        reply = replace(reply, assistant_message=message)
        log_usage(task_id, "mock", "scripted", reply.input_tokens, reply.output_tokens)
        return reply

    def close(self) -> None:
        pass
