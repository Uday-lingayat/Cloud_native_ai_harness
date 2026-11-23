"""Check the committed demo fixtures and reference patches using local pytest."""

import argparse
import io
import json
import os
import re
import subprocess
import sys
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import docker
from app.sandbox.docker_sandbox import DockerSandbox

ROOT = Path(__file__).resolve().parents[1]
DEMOS = ("buggy_calc", "date_ranges")


def local_pytest(repo: Path, args: list[str]) -> tuple[int, str]:
    env = os.environ.copy()
    for key in ("PYTHONPATH", "PYTEST_ADDOPTS", "PYTEST_PLUGINS"):
        env.pop(key, None)
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    result = subprocess.run(
        [sys.executable, "-B", *args],
        cwd=repo,
        check=False,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=60,
    )
    return result.returncode, result.stdout


def run_tests(
    repo: Path,
    command: str,
    count: int,
    failures: set[str],
    client: docker.DockerClient | None,
) -> set[str]:
    if command != "python -m pytest -q tests":
        raise ValueError(f"{repo.name}: unsupported manifest test command {command!r}")
    args = [*command.split()[1:], "-rA", "--color=no"]
    if client is None:
        code, output = local_pytest(repo, args)
    else:
        box = DockerSandbox(client)
        try:
            box.start()
            box.copy_in(repo)
            result = box.exec("python " + " ".join(args), timeout=60)
            code, output = result.exit_code, result.output
        finally:
            box.destroy()
    return check_outcomes(repo.name, code, output, count, failures)


def check_outcomes(
    name: str, code: int, output: str, count: int, failures: set[str]
) -> set[str]:
    outcomes = re.findall(r"^(PASSED|FAILED) (tests/\S+::\S+)", output, re.MULTILINE)
    failed = {node for status, node in outcomes if status == "FAILED"}
    nodes = {node for _, node in outcomes}
    if code != int(bool(failures)) or failed != failures or len(nodes) != count:
        raise RuntimeError(f"{name}: unexpected pytest results\n{output}")
    print(f"{name}: {count - len(failed)} passed, {len(failed)} failed")
    return nodes


def verify(client: docker.DockerClient | None) -> None:
    with TemporaryDirectory() as temp:
        work = Path(temp)
        paths = [f"demo_repos/{name}" for name in DEMOS]
        archive = subprocess.check_output(
            [
                "git",
                "archive",
                "--format=zip",
                "HEAD",
                *paths,
                "scripts/reference_fixes",
            ],
            cwd=ROOT,
        )
        with ZipFile(io.BytesIO(archive)) as fixtures:
            fixtures.extractall(work)

        for name in DEMOS:
            repo = work / "demo_repos" / name
            manifest = json.loads((repo / "manifest.json").read_text(encoding="utf-8"))
            command, count = manifest["test_command"], manifest["test_count"]
            failures = set(manifest["expected_failing_tests"])
            if not failures:
                raise ValueError(f"{name}: expected at least one failing test")
            before = run_tests(repo, command, count, failures, client)
            patch = work / "scripts" / "reference_fixes" / f"{name}.patch"
            subprocess.run(
                ["git", "apply", "--no-index", "--unidiff-zero", patch],
                cwd=repo,
                check=True,
            )
            if run_tests(repo, command, count, set(), client) != before:
                raise RuntimeError(
                    f"{name}: test selection changed after the reference fix"
                )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--docker", action="store_true", help="require fresh live Docker sandboxes"
    )
    if parser.parse_args().docker:
        with closing(docker.from_env()) as engine:
            verify(engine)
    else:
        verify(None)
