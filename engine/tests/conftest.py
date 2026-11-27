from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from limo.app import Deps, create_app
from limo.config import Settings
from limo.executor.local import LocalExecutor
from tests.fakes.llm import FakeLlm


@pytest.fixture
def llm() -> FakeLlm:
    return FakeLlm()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data", anthropic_api_key="sk-canary-123", _env_file=None)


@pytest.fixture
def client(settings: Settings, llm: FakeLlm) -> Iterator[TestClient]:
    deps = Deps(executor=LocalExecutor(path_prefix=settings.scripts_dir), llm=llm)
    with TestClient(create_app(settings, deps)) as c:
        yield c
