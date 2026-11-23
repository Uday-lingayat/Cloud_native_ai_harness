import base64
import math
import stat
import tarfile
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryFile

import docker
from docker.errors import NotFound
from docker.models.containers import Container

from .base import ExecResult

LABEL = "codeharness=1"
USER = "10001:10001"
HEAD, TAIL = 2048, 8192


class DockerSandbox:
    """One task's container. Its owner calls the methods sequentially."""

    def __init__(self, client: docker.DockerClient) -> None:
        self.client = client
        self.container: Container | None = None
        self._fresh = False

    def start(self) -> None:
        if self.container is not None:
            raise RuntimeError("sandbox already started")
        self.container = self.client.containers.create(
            "codeharness-sandbox",
            user=USER,
            working_dir="/workspace",
            network_mode="none",
            use_config_proxy=False,
            read_only=True,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges"],
            init=True,
            mem_limit="512m",
            memswap_limit="512m",
            nano_cpus=1_000_000_000,
            pids_limit=128,
            labels={"codeharness": "1"},
            mounts=[
                docker.types.Mount(target="/workspace", source=None, type="volume")
            ],
        )
        try:
            self.container.start()
            status, output = self.container.exec_run(["mkdir", "-p", "/workspace/.tmp"])
            if status:
                raise RuntimeError(output.decode(errors="replace"))
            self._fresh = True
        except BaseException:
            self.destroy()
            raise

    def _running(self) -> Container:
        if self.container is None:
            raise RuntimeError("sandbox is not running")
        return self.container

    def copy_in(self, local_dir: Path) -> None:
        box = self._running()
        if not self._fresh:
            raise RuntimeError("copy_in requires a fresh workspace")
        self._fresh = False

        def checked(info: tarfile.TarInfo) -> tarfile.TarInfo:
            source = local_dir / info.name
            attributes = getattr(source.lstat(), "st_file_attributes", 0)
            if attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise ValueError(f"unsupported reparse point: {info.name}")
            if not (info.isfile() or info.isdir()) or "\\" in info.name:
                raise ValueError(f"unsupported archive entry: {info.name}")
            info.uid = info.gid = 10001
            info.uname = info.gname = ""
            info.mode = 0o755 if info.isdir() or info.mode & 0o111 else 0o644
            return info

        if not local_dir.is_dir() or local_dir.is_symlink():
            raise ValueError("expected a regular directory")
        with TemporaryFile() as data:
            with tarfile.open(fileobj=data, mode="w") as tar:
                tar.add(local_dir, arcname=".", filter=checked)
            data.seek(0)
            if not box.put_archive("/workspace", data):
                raise RuntimeError("workspace upload failed")

    def exec(self, cmd: str, timeout: float) -> ExecResult:
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be finite and positive")
        box = self._running()
        self._fresh = False
        api = self.client.api

        def collect() -> ExecResult:
            exec_id = api.exec_create(
                box.id,
                ["timeout", "-k", "1s", f"{timeout}s", "sh", "-c", cmd],
                user=USER,
                workdir="/workspace",
            )["Id"]
            head, tail = bytearray(), bytearray()
            size = 0
            for chunk in api.exec_start(exec_id, stream=True):
                size += len(chunk)
                take = min(HEAD - len(head), len(chunk))
                head.extend(chunk[:take])
                tail.extend(chunk[take:])
                del tail[: max(0, len(tail) - TAIL)]
            truncated = size > HEAD + TAIL
            marker = b"\n[output truncated]\n" if truncated else b""
            code = api.exec_inspect(exec_id)["ExitCode"]
            if code is None:
                raise RuntimeError("Docker returned no command exit status")
            return ExecResult(
                code, (head + marker + tail).decode(errors="replace"), truncated
            )

        pool = ThreadPoolExecutor(max_workers=1)
        try:
            future = pool.submit(collect)
            return future.result(timeout=timeout + 5)
        except TimeoutError:
            self.destroy()
            raise TimeoutError("host deadline expired; sandbox removed") from None
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

    def _file(self, mode: str, path: str, *payload: str) -> str:
        box = self._running()
        self._fresh = False
        code, data = box.exec_run(
            [
                "python",
                "-I",
                "/usr/local/lib/codeharness/workspace_file.py",
                mode,
                path,
                *payload,
            ],
            user=USER,
        )
        if code:
            raise ValueError(data.decode(errors="replace"))
        return data.decode("utf-8")

    def read_file(self, path: str) -> str:
        return self._file("read", path)

    def write_file(self, path: str, content: str) -> None:
        data = content.encode()
        if len(data) > 1024 * 1024:
            raise ValueError("file exceeds 1 MiB")
        encoded = base64.b64encode(data).decode("ascii")
        self._file(
            "write",
            path,
            *(encoded[i : i + 32768] for i in range(0, len(encoded), 32768)),
        )

    def destroy(self) -> None:
        if self.container is not None:
            try:
                self.container.remove(force=True, v=True)
            except NotFound:
                pass
            self.container = None


def cleanup_orphans(
    client: docker.DockerClient,
    min_age: timedelta,
    active_ids: set[str],
    *,
    dry_run: bool = True,
) -> list[str]:
    """The owner supplies the full IDs of all live tasks sharing this daemon."""
    if min_age < timedelta(0):
        raise ValueError("minimum age must be non-negative")
    cutoff = datetime.now(UTC) - min_age
    removed = []
    for box in client.containers.list(
        all=True, filters={"label": LABEL}, ignore_removed=True
    ):
        created = datetime.fromisoformat(box.attrs["Created"])
        if box.id in active_ids or created > cutoff:
            continue
        removed.append(box.id)
        if not dry_run:
            try:
                box.remove(force=True, v=True)
            except NotFound:
                pass
    return removed
