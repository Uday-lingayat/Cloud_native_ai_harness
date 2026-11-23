"""Run the Phase 1 calculator repair and independently verify its patch."""

import io
import json
import subprocess
from collections.abc import Iterable, Iterator
from contextlib import closing, contextmanager
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from uuid import uuid4
from zipfile import ZipFile

import docker
from app.agent.loop import RepairTask, run_agent
from app.config import LLMSettings
from app.llm.base import Reply, ToolCall
from app.llm.factory import get_llm
from app.sandbox.docker_sandbox import DockerSandbox
from verify_demo_repos import ROOT, check_outcomes


@contextmanager
def workspace(engine: docker.DockerClient, repo: Path) -> Iterator[DockerSandbox]:
    box = DockerSandbox(engine)
    try:
        box.start()
        box.copy_in(repo)
        yield box
    finally:
        box.destroy()


def mock_script(repo: Path, task: RepairTask) -> Iterable[Reply]:
    source = (repo / task.source_file).read_text(encoding="utf-8")
    for index, (tool, args) in enumerate(
        [
            ("read_file", {"path": task.source_file}),
            (
                "write_file",
                {
                    "path": task.source_file,
                    "content": source.replace("left // right", "left / right"),
                },
            ),
            ("run_command", {"cmd": task.test_command}),
        ]
    ):
        yield Reply(tool_calls=(ToolCall(str(index), tool, args),))


def demo(engine: docker.DockerClient, repo: Path, settings: LLMSettings) -> None:
    manifest = json.loads((repo / "manifest.json").read_text(encoding="utf-8"))
    task = RepairTask(
        uuid4().hex, manifest["task_prompt"], "calculator.py", manifest["test_command"]
    )
    events: list[dict[str, Any]] = []

    def emit_event(task_id: str, kind: str, data: dict[str, Any]) -> None:
        event = {"task_id": task_id, "type": kind, "data": data}
        events.append(event)
        print(json.dumps(event), flush=True)

    pytest = task.test_command + " -rA --color=no"
    emit_event(
        task.id,
        "started",
        {
            "provider": settings.provider,
            "model": settings.model if settings.provider != "mock" else "scripted",
        },
    )
    with workspace(engine, repo) as box:
        baseline = box.exec(pytest, 30)
        nodes = check_outcomes(
            "baseline",
            baseline.exit_code,
            baseline.output,
            manifest["test_count"],
            set(manifest["expected_failing_tests"]),
        )
        with closing(
            get_llm(
                settings=replace(settings, max_retries=0),
                script=mock_script(repo, task),
            )
        ) as llm:
            run = run_agent(task, box, llm, emit_event)
        if run.reason not in {"model_finished", "tests_passed"}:
            raise RuntimeError(f"Agent stopped: {run.reason}")
        candidate = box.read_file(task.source_file)

    with workspace(engine, repo) as judge:
        baseline_git = judge.exec("git init -q && git add -- calculator.py", 10)
        if baseline_git.exit_code:
            raise RuntimeError(baseline_git.output)
        judge.write_file(task.source_file, candidate)
        patch = judge.exec("git diff --no-ext-diff -- calculator.py", 10)
        if patch.exit_code or patch.truncated or not patch.output.strip():
            raise RuntimeError("Expected a complete, nonempty calculator patch")
        final = judge.exec(pytest, 30)
        passed = check_outcomes(
            "independent check",
            final.exit_code,
            final.output,
            manifest["test_count"],
            set(),
        )
        if passed != nodes:
            raise RuntimeError("Independent test selection changed")
    emit_event(task.id, "done", {"tests_passed": len(nodes)})
    print(patch.output, end="")


def main() -> None:
    settings = LLMSettings.load()
    path = "demo_repos/buggy_calc"
    archive = subprocess.check_output(
        ["git", "-c", "core.autocrlf=false", "archive", "--format=zip", "HEAD", path],
        cwd=ROOT,
    )
    with TemporaryDirectory() as temp, closing(docker.from_env()) as engine:
        with ZipFile(io.BytesIO(archive)) as files:
            files.extractall(temp)
        demo(engine, Path(temp) / path, settings)


if __name__ == "__main__":
    main()
