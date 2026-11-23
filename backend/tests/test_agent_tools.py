from collections.abc import Iterator
from pathlib import Path

import docker
import pytest
from app.agent.tools import TOOLS, execute_tool
from app.llm.base import ToolCall
from app.sandbox.base import ExecResult
from app.sandbox.docker_sandbox import DockerSandbox

pytestmark = pytest.mark.docker


@pytest.fixture
def box(engine: docker.DockerClient) -> Iterator[DockerSandbox]:
    sandbox = DockerSandbox(engine)
    try:
        sandbox.start()
        sandbox.copy_in(
            Path(__file__).resolve().parents[2] / "demo_repos" / "buggy_calc"
        )
        yield sandbox
    finally:
        sandbox.destroy()


def invoke(box: DockerSandbox, name: str, **arguments: str) -> ExecResult:
    return execute_tool(ToolCall("call-1", name, arguments), box)


def test_tools_on_demo_repo(box: DockerSandbox) -> None:
    assert {tool["function"]["name"] for tool in TOOLS} == {
        "list_dir",
        "read_file",
        "search",
        "write_file",
        "run_command",
    }
    listing = invoke(box, "list_dir", path=".")
    assert listing.exit_code == 0 and "calculator.py" in listing.output.splitlines()
    assert "tests/" in listing.output.splitlines()
    path = "tests/notes from 'review'.txt"
    content = "first\n--literal [v1].*\n"
    assert invoke(box, "write_file", path=path, content=content).exit_code == 0
    assert invoke(box, "read_file", path=path) == ExecResult(0, content, False)
    found = invoke(box, "search", path="tests", query="--literal [v1].*")
    assert found == ExecResult(
        0, "./notes from 'review'.txt:2:--literal [v1].*\n", False
    )
    assert invoke(box, "search", path="tests", query="absent-marker").exit_code == 1
    result = invoke(box, "run_command", cmd="python -m pytest -q tests")
    assert result.exit_code == 1 and "1 failed, 3 passed" in result.output
    assert invoke(box, "read_file", path="calculator.py", extra="unused").exit_code != 0


def test_tool_output_bounds_and_paths(box: DockerSandbox) -> None:
    line = "a" * 2048 + "b" * 12000 + "z" * 8192
    assert invoke(box, "write_file", path="long.txt", content=line).exit_code == 0
    for result in (
        invoke(box, "read_file", path="long.txt"),
        invoke(box, "run_command", cmd="cat long.txt"),
        invoke(box, "search", path=".", query="bbbb"),
    ):
        assert result.exit_code == 0 and result.truncated
        assert (
            "[output truncated]" in result.output
            and result.output.rstrip().endswith("z" * 100)
        )
        assert len(result.output) < 10300
    assert box.exec("ln -s /etc outside", 5).exit_code == 0
    for path in ("../", "/etc", "C:/Windows", "outside"):
        assert invoke(box, "list_dir", path=path).exit_code != 0
        assert invoke(box, "search", path=path, query="marker").exit_code != 0
        assert invoke(box, "read_file", path=f"{path}/sample").exit_code != 0
        assert (
            invoke(box, "write_file", path=f"{path}/sample", content="test").exit_code
            != 0
        )
