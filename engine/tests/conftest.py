import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from limo.app import Deps, create_app
from limo.config import Settings
from limo.executor.local import LocalExecutor
from tests.fakes.host import FakeHost
from tests.fakes.llm import FakeLlm

# Tests drive the Messages API fake unless a test picks the claude-cli backend (ADR-14).
os.environ.setdefault("LIMO_AGENT_BACKEND", "api")
# Tests expect one default model for every agent unless a test sets one.
os.environ.setdefault("LIMO_AGENT_MODELS", "{}")


@pytest.fixture
def llm() -> FakeLlm:
    return FakeLlm()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data", anthropic_api_key="sk-canary-123", _env_file=None)


@pytest.fixture
def host() -> FakeHost:
    return FakeHost()


@pytest.fixture
def client(settings: Settings, llm: FakeLlm, host: FakeHost) -> Iterator[TestClient]:
    deps = Deps(executor=LocalExecutor(path_prefix=settings.scripts_dir), llm=llm, host=host)
    with TestClient(create_app(settings, deps)) as c:
        yield c
