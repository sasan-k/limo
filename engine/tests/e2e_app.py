"""Engine for the UI e2e tests: the real app on 127.0.0.1:8701 with fake Claude API and fake repo host.
`python -m tests.e2e_app --openapi` prints the OpenAPI document instead (used by `mise run gen:api`)."""

import json
import sys
import tempfile
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from limo.app import Deps, create_app
from limo.config import Settings
from limo.executor.local import LocalExecutor
from tests.fakes.host import FakeHost
from tests.fakes.llm import FakeLlm

PORT = 8701


def build_app() -> FastAPI:
    settings = Settings(data_dir=Path(tempfile.mkdtemp(prefix="limo-e2e-")), _env_file=None)
    deps = Deps(executor=LocalExecutor(path_prefix=settings.scripts_dir), llm=FakeLlm(), host=FakeHost())
    return create_app(settings, deps)


def main() -> None:
    app = build_app()
    if "--openapi" in sys.argv:
        print(json.dumps(app.openapi(), indent=2))
        return
    uvicorn.run(app, host="127.0.0.1", port=PORT)


if __name__ == "__main__":
    main()
