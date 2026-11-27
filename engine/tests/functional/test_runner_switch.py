import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from limo.app import Deps, create_app
from limo.config import Settings
from limo.executor.local import LocalExecutor
from limo.llm.ports import LlmRequest, LlmResponse
from tests.builders import add_cart_project, set_status, wait_run, write_workspace_file
from tests.fakes.host import FakeHost
from tests.fakes.llm import FakeLlm, blocking_build, final

RUNNER = "/api/runner"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path / "data", anthropic_api_key="sk-canary-123", runner_tick_s=0.05, _env_file=None
    )


def _card(client: TestClient, agent: str) -> dict[str, Any]:
    return next(c for c in client.get("/api/agent-cards").json() if c["agent"] == agent)


def _until(check: Callable[[], bool], timeout_s: float = 5.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(0.02)
    raise AssertionError("condition not met in time")


def _slow(request: LlmRequest) -> LlmResponse:
    time.sleep(1.0)
    return final()


def test_ft_16_1_runner_starts_off_and_starts_nothing(
    settings: Settings, llm: FakeLlm, tmp_path: Path
) -> None:
    """FT-16.1 a fresh engine reports the runner off and starts no run, also after a restart."""
    deps = Deps(LocalExecutor(path_prefix=settings.scripts_dir), llm, FakeHost())
    with TestClient(create_app(settings, deps)) as client:
        add_cart_project(client, tmp_path)
        assert client.get(RUNNER).json() == {"enabled": False}
        assert client.put(RUNNER, json={"enabled": True}).json() == {"enabled": True}
        assert client.put(RUNNER, json={"enabled": False}).json() == {"enabled": False}
    llm.requests.clear()
    with TestClient(create_app(settings, deps)) as client:
        assert client.get(RUNNER).json() == {"enabled": False}
        time.sleep(0.5)
        assert all(
            c["last_run"] is None or c["state"] != "active" for c in client.get("/api/agent-cards").json()
        )
    assert llm.requests == []


def test_ft_16_2_turning_on_starts_a_plan_run(client: TestClient, llm: FakeLlm, tmp_path: Path) -> None:
    """FT-16.2 turning the runner on starts a plan run for TKT-1 without a step call."""
    add_cart_project(client, tmp_path)
    llm.responder = _slow
    time.sleep(0.2)
    assert _card(client, "plan")["last_run"] is None
    assert client.put(RUNNER, json={"enabled": True}).status_code == 200
    _until(lambda: _card(client, "plan")["last_run"] is not None)
    card = _card(client, "plan")
    assert card["ticket"] == "TKT-1"
    assert card["state"] == "active"
    client.put(RUNNER, json={"enabled": False})


def test_ft_16_3_turning_off_lets_the_active_run_finish(
    client: TestClient, llm: FakeLlm, settings: Settings, tmp_path: Path
) -> None:
    """FT-16.3 turning off during a build run lets it finish and starts no plan run for TKT-3."""
    add_cart_project(client, tmp_path)
    set_status(settings, "shop", "TKT-1", "planned")
    llm.responder = blocking_build(settings.skills_dir, 1.0)
    client.put(RUNNER, json={"enabled": True})
    _until(lambda: _card(client, "build")["state"] == "active")
    assert client.put(RUNNER, json={"enabled": False}).json() == {"enabled": False}
    run = wait_run(client, _card(client, "build")["last_run"]["id"])
    assert run["status"] == "succeeded"
    time.sleep(0.5)
    assert _card(client, "plan")["last_run"] is None
    assert _card(client, "build")["last_run"]["tries"] == 1


def test_ft_16_4_turning_on_twice_starts_one_run(client: TestClient, llm: FakeLlm, tmp_path: Path) -> None:
    """FT-16.4 two PUT enabled=true calls give one active plan run."""
    add_cart_project(client, tmp_path)
    llm.responder = _slow
    client.put(RUNNER, json={"enabled": True})
    assert client.put(RUNNER, json={"enabled": True}).json() == {"enabled": True}
    _until(lambda: _card(client, "plan")["last_run"] is not None)
    time.sleep(0.3)
    assert _card(client, "plan")["last_run"]["tries"] == 1
    client.put(RUNNER, json={"enabled": False})


def test_ft_16_5_invalid_switch_bodies_are_rejected(client: TestClient) -> None:
    """FT-16.5 non-boolean, missing and extra fields give 422 validation_error; the switch stays off."""
    for body in ({"enabled": "yes"}, {"enabled": 1}, {}, {"enabled": True, "force": True}):
        r = client.put(RUNNER, json=body)
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "validation_error"
    assert client.get(RUNNER).json() == {"enabled": False}


def test_ft_16_6_a_broken_feature_does_not_stop_the_runner(
    client: TestClient, llm: FakeLlm, settings: Settings, tmp_path: Path
) -> None:
    """FT-16.6 a feature whose map is invalid is skipped; the cart feature still gets its plan run."""
    add_cart_project(client, tmp_path)
    write_workspace_file(
        settings, "shop", "work/aaa/map.yaml", "feature: aaa\ntickets:\n  - id: TKT-1\n    bogus: x\n"
    )
    llm.responder = _slow
    client.put(RUNNER, json={"enabled": True})
    _until(lambda: _card(client, "plan")["last_run"] is not None)
    assert _card(client, "plan")["feature"] == "cart"
    client.put(RUNNER, json={"enabled": False})
