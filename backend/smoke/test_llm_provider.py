"""Explicit, single-request provider smoke test. Outside default test discovery."""

import os
from contextlib import closing
from dataclasses import replace

import pytest
from app.config import LLMSettings
from app.llm.openai_compatible import OpenAICompatibleLLM


def test_provider_requests_echo() -> None:
    settings = LLMSettings.load()
    if not settings.api_key:
        pytest.skip("LLM_API_KEY is unset")
    if os.environ.get("RUN_LIVE_LLM") != "1":
        pytest.skip("set RUN_LIVE_LLM=1 for one live request")
    assert settings.provider == "openai_compatible"
    tool = {
        "type": "function",
        "function": {
            "name": "echo",
            "description": "Return the supplied text.",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
    }
    with closing(OpenAICompatibleLLM(replace(settings, max_retries=0))) as client:
        reply = client.complete(
            [{"role": "user", "content": "Call echo once with text equal to hello."}],
            [tool],
            task_id="provider-smoke",
        )
    assert len(reply.tool_calls) == 1
    call = reply.tool_calls[0]
    assert call.id and call.name == "echo" and call.arguments == {"text": "hello"}
