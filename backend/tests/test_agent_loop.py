from dataclasses import replace
from unittest.mock import Mock

import pytest
from app.agent.loop import RepairTask, run_agent
from app.llm.base import Reply, ToolCall
from app.llm.mock import MockLLM
from app.sandbox.base import Sandbox

TASK = RepairTask(
    "fixture", "Fix division", "calculator.py", "python -m pytest -q tests"
)
READ = ToolCall("first", "read_file", {"path": "calculator.py"})


@pytest.mark.parametrize(
    ("task", "script", "reason", "steps"),
    [
        (replace(TASK, max_steps=1), [Reply(tool_calls=(READ,))], "step_limit", 1),
        (replace(TASK, max_tokens=20), [], "token_limit", 0),
        (TASK, [Reply(input_tokens=20000, tool_calls=(READ,))], "token_limit", 1),
        (TASK, [Reply(input_tokens=None, tool_calls=(READ,))], "usage_unavailable", 1),
        (replace(TASK, timeout_s=0), [], "time_limit", 0),
        (
            TASK,
            [
                Reply(tool_calls=(READ,)),
                Reply(tool_calls=(replace(READ, id="second"),)),
            ],
            "repeated_action",
            2,
        ),
    ],
)
def test_stop(task: RepairTask, script: list[Reply], reason: str, steps: int) -> None:
    box = Mock(spec=Sandbox)
    box.read_file.return_value = "calculator source"
    emit = Mock()
    result = run_agent(task, box, MockLLM(script), emit)
    assert (result.reason, result.steps) == (reason, steps)
    assert box.read_file.call_count == int(reason in {"step_limit", "repeated_action"})
    assert emit.call_args.args[:2] == ("fixture", "agent_stopped")


def test_message_history_and_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    box = Mock(spec=Sandbox)
    box.read_file.return_value = "calculator source"
    llm = MockLLM([Reply(tool_calls=(READ,)), Reply(text="finished")])
    spy = Mock(wraps=llm)
    emit = Mock()
    result = run_agent(TASK, box, spy, emit)
    assert [
        e.args[2]["model"] for e in emit.call_args_list if e.args[1] == "model_response"
    ] == ["scripted", "scripted"]
    assert result.reason == "model_finished"
    history = spy.complete.call_args.args[0]
    assert history[2]["tool_calls"][0]["id"] == history[3]["tool_call_id"] == "first"
    assert "calculator source" in history[3]["content"]
    clock = iter([0, 1, 181])
    monkeypatch.setattr("app.agent.loop.time", Mock(monotonic=lambda: next(clock)))
    result = run_agent(TASK, box, MockLLM([Reply(tool_calls=(READ,))]), Mock())
    assert result.reason == "time_limit"
    box.read_file.assert_called_once()
