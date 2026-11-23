"""Check the committed demo fixtures and reference patches using local pytest."""

import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
DEMOS = ("buggy_calc", "date_ranges")


def run_tests(repo: Path, command: str, count: int, failures: set[str]) -> set[str]:
    if command != "python -m pytest -q tests":
        raise ValueError(f"{repo.name}: unsupported manifest test command {command!r}")
    env = os.environ.copy()
    for key in ("PYTHONPATH", "PYTEST_ADDOPTS", "PYTEST_PLUGINS"):
        env.pop(key, None)
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    result = subprocess.run(
        [sys.executable, "-B", *command.split()[1:], "-rA", "--color=no"],
        cwd=repo,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=60,
    )
    outcomes = re.findall(r"^(PASSED|FAILED) (tests/\S+::\S+)", result.stdout, re.M)
    failed = {node for status, node in outcomes if status == "FAILED"}
    nodes = {node for _, node in outcomes}
    if (
        result.returncode != int(bool(failures))
        or failed != failures
        or len(nodes) != count
    ):
        raise RuntimeError(f"{repo.name}: unexpected pytest results\n{result.stdout}")
    print(f"{repo.name}: {count - len(failed)} passed, {len(failed)} failed")
    return nodes


def main() -> None:
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
            before = run_tests(repo, command, count, failures)
            patch = work / "scripts" / "reference_fixes" / f"{name}.patch"
            subprocess.run(
                ["git", "apply", "--no-index", "--unidiff-zero", patch],
                cwd=repo,
                check=True,
            )
            if run_tests(repo, command, count, set()) != before:
                raise RuntimeError(
                    f"{name}: test selection changed after the reference fix"
                )


if __name__ == "__main__":
    main()
