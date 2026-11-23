from collections.abc import Iterator

import docker
import pytest
from docker.errors import DockerException


@pytest.fixture
def engine() -> Iterator[docker.DockerClient]:
    try:
        client = docker.from_env()
    except DockerException as exc:
        pytest.skip(f"Docker engine unavailable: {exc}")
    try:
        try:
            client.ping()
        except (DockerException, OSError) as exc:
            pytest.skip(f"Docker engine unavailable: {exc}")
        yield client
    finally:
        client.close()
