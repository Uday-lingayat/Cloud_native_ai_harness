import json
import re
from datetime import timedelta
from pathlib import Path

import docker
import pytest
from app.sandbox.docker_sandbox import DockerSandbox, cleanup_orphans
from docker.errors import NotFound

pytestmark = pytest.mark.docker


def test_calculator_failure_and_cleanup(engine: docker.DockerClient) -> None:
    repo = Path(__file__).resolve().parents[2] / "demo_repos" / "buggy_calc"
    manifest = json.loads((repo / "manifest.json").read_text(encoding="utf-8"))
    box = DockerSandbox(engine)
    try:
        box.start()
        assert box.container is not None
        container_id = box.container.id
        box.container.reload()
        mounts = box.container.attrs["Mounts"]
        assert [(m["Type"], m["Destination"]) for m in mounts] == [
            ("volume", "/workspace")
        ]
        volume = mounts[0]["Name"]
        config = box.container.attrs["HostConfig"]
        assert config["ReadonlyRootfs"] and config["Init"]
        assert config["NetworkMode"] == "none"
        assert (
            config["CapDrop"] == ["ALL"]
            and "no-new-privileges" in config["SecurityOpt"]
        )
        assert (config["Memory"], config["NanoCpus"], config["PidsLimit"]) == (
            512 * 1024**2,
            10**9,
            128,
        )
        assert box.container.labels["codeharness"] == "1"
        box.copy_in(repo)
        assert box.exec("id -u", 5).output.strip() == "10001"
        result = box.exec(manifest["test_command"], 30)
        assert result.exit_code == 1
        assert (
            re.findall(r"^FAILED (\S+)", result.output, re.MULTILINE)
            == manifest["expected_failing_tests"]
        )
        assert "1 failed, 3 passed" in result.output
    finally:
        box.destroy()
    with pytest.raises(NotFound):
        engine.containers.get(container_id)
    with pytest.raises(NotFound):
        engine.volumes.get(volume)


def test_timeout_output_and_workspace(engine: docker.DockerClient) -> None:
    box = DockerSandbox(engine)
    try:
        box.start()
        result = box.exec("(sleep 2 && touch late) & wait", 0.5)
        assert result.exit_code == 124
        assert box.exec("sleep 2 && test ! -e late", 5).exit_code == 0
        result = box.exec(
            """python -c "print('A'*3000+'B'*20000+'Z'*9000,end='')" """, 10
        )
        assert result.truncated
        assert result.output == "A" * 2048 + "\n[output truncated]\n" + "Z" * 8192
        box.write_file("example", "an example\n")
        assert box.read_file("example") == "an example\n"
        assert box.exec("ln -s /etc alias", 5).exit_code == 0
        for path in ("../etc/passwd", "/etc/passwd", "alias/passwd"):
            with pytest.raises(ValueError):
                box.read_file(path)
            with pytest.raises(ValueError):
                box.write_file(path, "example")
        assert box.container is not None
        ident = box.container.id
        assert ident in cleanup_orphans(engine, timedelta(0), set(), dry_run=True)
        assert ident not in cleanup_orphans(engine, timedelta(0), {ident}, dry_run=True)
        assert ident not in cleanup_orphans(
            engine, timedelta(days=1), set(), dry_run=True
        )
    finally:
        box.destroy()
