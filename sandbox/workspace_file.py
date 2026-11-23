"""Open UTF-8 workspace files as the sandbox user, without following links."""

import base64
import os
import stat
import sys
from contextlib import ExitStack
from pathlib import PurePosixPath, PureWindowsPath


def main() -> None:
    mode, path, *data = sys.argv[1:]
    parts = PurePosixPath(path).parts
    directory = mode in {"list", "search"}
    if (
        not path
        or (not directory and not parts)
        or PurePosixPath(path).is_absolute()
        or PureWindowsPath(path).drive
        or ".." in parts
        or "\\" in path
    ):
        raise ValueError("expected a relative workspace path")
    flags = os.O_NOFOLLOW | os.O_DIRECTORY | os.O_RDONLY
    with ExitStack() as files:
        parent = os.open("/workspace", flags)
        files.callback(os.close, parent)
        for part in parts if directory else parts[:-1]:
            parent = os.open(part, flags, dir_fd=parent)
            files.callback(os.close, parent)
        if directory:
            os.fchdir(parent)
            if mode == "list":
                os.execl("/bin/ls", "ls", "-1Abp", "--", ".")
            # Recursive grep skips symlinks encountered below the opened directory.
            os.execl(
                "/bin/grep", "grep", "-rInHF", "--devices=skip", "--", data[0], "."
            )
        access = os.O_WRONLY | os.O_CREAT if mode == "write" else os.O_RDONLY
        fd = os.open(
            parts[-1], access | os.O_NONBLOCK | os.O_NOFOLLOW, 0o600, dir_fd=parent
        )
        file = files.enter_context(os.fdopen(fd, "wb" if mode == "write" else "rb"))
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError("expected a regular workspace file")
        if mode == "write":
            content = base64.b64decode("".join(data), validate=True)
            file.truncate(0)
            file.write(content)
        else:
            content = file.read(1024 * 1024 + 1)
            if len(content) > 1024 * 1024:
                raise ValueError("file exceeds 1 MiB")
            sys.stdout.buffer.write(content)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        sys.exit(str(error))
