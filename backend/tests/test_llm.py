import json
import logging
from collections.abc import Callable
from contextlib import closing
from pathlib import Path
from typing import Any

import httpx
import pytest
from app.config import LLMSettings
from app.llm.base import Reply, ToolCall
from app.llm.factory import get_llm
from app.llm.mock import MockLLM
from app.llm.openai_compatible import LLMError, OpenAICompatibleLLM


@pytest.fixture(autouse=True)
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    for name in (
        "PROVIDER",
        "BASE_URL",
        "MODEL",
        "API_KEY",
        "MAX_RETRIES",
        "TIMEOUT_S",
    ):
        monkeypatch.delenv(f"LLM_{name}", raising=False)


def test_scripted_mock(caplog: pytest.LogCaptureFixture) -> None:
    call = ToolCall("one", "echo", {"text": "hello"})
    with closing(
        get_llm(script=[Reply(tool_calls=(call,)), Reply(text="done")])
    ) as client:
        assert isinstance(client, MockLLM)
        with caplog.at_level(logging.INFO):
            first = client.complete([], [], task_id="task-a")
        assert first.tool_calls == (call,)
        assert (
            json.loads(
                first.assistant_message["tool_calls"][0]["function"]["arguments"]
            )
            == call.arguments
        )
        assert client.complete([], [], task_id="task-a").text == "done"
        assert client.complete([], [], task_id="task-a").tool_calls == ()
        assert (
            "task_id=task-a" in caplog.text
            and "input_tokens=0 output_tokens=0" in caplog.text
        )


@pytest.fixture
def endpoint(monkeypatch: pytest.MonkeyPatch) -> Callable:
    Path(".env").write_text(
        "LLM_PROVIDER=openai_compatible\nLLM_MODEL=from-file\nLLM_BASE_URL=https://fixture.invalid/v1\nLLM_API_KEY=test-only\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("LLM_MODEL", "from-process")

    def install(*responses: tuple[int, dict[str, Any]]) -> list[httpx.Request]:
        queue = iter(responses)
        requests = []

        def handle(
            transport: httpx.HTTPTransport, request: httpx.Request
        ) -> httpx.Response:
            requests.append(request)
            status, body = next(queue)
            return httpx.Response(status, json=body)

        monkeypatch.setattr(httpx.HTTPTransport, "handle_request", handle)
        return requests

    return install


def completion(arguments: str = '{"text":"hello"}') -> dict[str, Any]:
    return {
        "model": "fixture/routed-model",
        "choices": [
            {
                "index": 0,
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "one",
                            "type": "function",
                            "function": {"name": "echo", "arguments": arguments},
                            "extra_content": {
                                "google": {"thought_signature": "fixture"}
                            },
                        }
                    ],
                },
            }
        ],
        "usage": {"prompt_tokens": 12, "completion_tokens": 4, "total_tokens": 16},
    }


def test_compatible_tool_call(
    endpoint: Callable, caplog: pytest.LogCaptureFixture
) -> None:
    reqs = endpoint((200, completion()))
    messages = [{"role": "user", "content": "echo hello"}]
    tools = [
        {
            "type": "function",
            "function": {"name": "echo", "parameters": {"type": "object"}},
        }
    ]
    with closing(get_llm()) as client, caplog.at_level(logging.INFO):
        assert isinstance(client, OpenAICompatibleLLM)
        reply = client.complete(messages, tools, task_id="task-b")
    assert str(reqs[0].url) == "https://fixture.invalid/v1/chat/completions"
    assert json.loads(reqs[0].content) == {
        "model": "from-process",
        "messages": messages,
        "tools": tools,
    }
    assert reply.tool_calls == (ToolCall("one", "echo", {"text": "hello"}),)
    assert (
        reply.assistant_message["tool_calls"][0]["extra_content"]["google"][
            "thought_signature"
        ]
        == "fixture"
    )
    assert (reply.input_tokens, reply.output_tokens) == (12, 4)
    assert reply.model == "fixture/routed-model"
    assert "input_tokens=12 output_tokens=4" in caplog.text
    assert "test-only" not in caplog.text and "test-only" not in repr(
        LLMSettings.load()
    )


@pytest.mark.parametrize("arguments", ["[]", "bad-json"])
def test_invalid_tool_arguments(endpoint: Callable, arguments: str) -> None:
    endpoint((200, completion(arguments)))
    with closing(get_llm()) as client, pytest.raises(LLMError, match="arguments"):
        client.complete([], [], task_id="invalid")


@pytest.mark.parametrize("status", [200, 429, 401])
def test_rate_limit(
    endpoint: Callable, monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    monkeypatch.setenv("LLM_MAX_RETRIES", "2")
    sleeps = []
    monkeypatch.setattr("app.llm.openai_compatible.time.sleep", sleeps.append)
    error = {"error": {"message": "private response body"}}
    body = {"choices": [{"message": {"role": "assistant", "content": "done"}}]}
    reqs = endpoint(
        (429, error), (429, error), (status, body if status == 200 else error)
    )
    with closing(get_llm()) as client:
        if status == 200:
            reply = client.complete([], [], task_id="retry")
            assert (
                reply.text == "done"
                and reply.input_tokens is None
                and not reply.tool_calls
            )
        else:
            with pytest.raises(LLMError, match=str(status)) as caught:
                client.complete([], [], task_id="retry")
            assert "private response body" not in str(caught.value)
    assert len(reqs) == 3 and len(sleeps) == 2
    assert 1 <= sleeps[0] <= 1.5 and 2 <= sleeps[1] <= 3


def test_unsupported_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    with pytest.raises(ValueError, match="Unsupported LLM_PROVIDER"):
        get_llm()
