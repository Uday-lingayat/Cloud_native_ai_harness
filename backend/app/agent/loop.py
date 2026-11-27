"""Bounded tool-calling loop for a single repair task."""

import json
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

from app.agent.tools import TOOLS, execute_tool
from app.llm.base import LLM, Message
from app.sandbox.base import ExecResult, Sandbox


@dataclass(frozen=True)
class RepairTask:
    id: str
    prompt: str
    source_file: str
    test_command: str
    max_steps: int = 8
    max_tokens: int = 20_000
    timeout_s: float = 180


@dataclass
class RunResult:
    reason: str = "step_limit"
    steps: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


EmitEvent = Callable[[str, str, dict[str, Any]], None]


def run_agent(
    task: RepairTask, sandbox: Sandbox, llm: LLM, emit_event: EmitEvent
) -> RunResult:
    deadline = time.monotonic() + task.timeout_s
    messages: list[Message] = [
        {
            "role": "system",
            "content": (
                f"Repair {task.source_file} in the offline workspace. Read the source and tests before editing. "
                f"Use write_file for edits and run_command only for this exact command: {task.test_command}. "
                "Never change, delete, or weaken the tests. Stop when the tests pass."
            ),
        },
        {"role": "user", "content": task.prompt},
    ]
    run = RunResult()
    previous = None
    while run.steps < task.max_steps:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            run.reason = "time_limit"
            break
        # Reserve the serialized request byte length plus framing before asking for output.
        reserve = len(json.dumps([messages, TOOLS], ensure_ascii=False).encode()) + 64
        allowance = task.max_tokens - run.input_tokens - run.output_tokens - reserve
        if allowance <= 0:
            run.reason = "token_limit"
            break
        run.steps += 1
        reply = llm.complete(
            messages,
            TOOLS,
            task_id=task.id,
            max_output_tokens=min(2048, allowance),
            timeout_s=remaining,
        )
        emit_event(
            task.id,
            "model_response",
            {
                "step": run.steps,
                "model": reply.model or "unreported",
                "input_tokens": reply.input_tokens,
                "output_tokens": reply.output_tokens,
            },
        )
        if reply.input_tokens is None or reply.output_tokens is None:
            run.reason = "usage_unavailable"
            break
        run.input_tokens += reply.input_tokens
        run.output_tokens += reply.output_tokens
        if time.monotonic() >= deadline:
            run.reason = "time_limit"
            break
        if run.input_tokens + run.output_tokens >= task.max_tokens:
            run.reason = "token_limit"
            break
        messages.append(reply.assistant_message)
        if reply.text:
            emit_event(task.id, "reasoning", {"text": reply.text})
        if not reply.tool_calls:
            run.reason = "model_finished"
            break
        for call in reply.tool_calls:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                run.reason = "time_limit"
                break
            action = (call.name, json.dumps(call.arguments, sort_keys=True))
            if action == previous:
                run.reason = "repeated_action"
                break
            previous = action
            emit_event(task.id, "tool_call", {"id": call.id, "name": call.name})
            if (
                call.name == "run_command"
                and call.arguments.get("cmd") != task.test_command
            ):
                result = ExecResult(
                    2, f"Use the configured test command: {task.test_command}", False
                )
            elif (
                call.name == "write_file"
                and call.arguments.get("path") != task.source_file
            ):
                result = ExecResult(2, f"Only {task.source_file} may be edited", False)
            else:
                result = execute_tool(call, sandbox, timeout=remaining)
            data = asdict(result)
            emit_event(
                task.id,
                "terminal_output" if call.name == "run_command" else "tool_result",
                {"id": call.id, **data},
            )
            messages.append(
                {"role": "tool", "tool_call_id": call.id, "content": json.dumps(data)}
            )
            if time.monotonic() >= deadline:
                run.reason = "time_limit"
                break
            if call.name == "run_command" and result.exit_code == 0:
                run.reason = "tests_passed"
                break
        else:
            continue
        break
    emit_event(task.id, "agent_stopped", asdict(run))
    return run
