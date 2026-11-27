import json
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from limo.app import Deps, create_app
from limo.config import Settings
from limo.executor.local import LocalExecutor
from limo.llm.ports import LlmError, LlmRequest
from tests.builders import (
    add_cart_project,
    get_status,
    set_status,
    wait_run,
    write_workspace_file,
)
from tests.fakes.host import FakeHost
from tests.fakes.llm import FakeLlm, final, resolver_responder

STEP = "/api/projects/shop/features/cart/step"
INCIDENTS = "/api/projects/shop/features/cart/incidents"
RETRY_BUILD = '```json\n{"type": "retry", "stage": "build"}\n```'


@contextmanager
def _shop(
    tmp_path: Path, llm: FakeLlm, run_timeout_s: float = 1800.0
) -> Iterator[tuple[TestClient, Settings]]:
    settings = Settings(
        data_dir=tmp_path / "data",
        run_timeout_s=run_timeout_s,
        anthropic_api_key="sk-canary-123",
        _env_file=None,
    )
    deps = Deps(LocalExecutor(path_prefix=settings.scripts_dir), llm, FakeHost())
    with TestClient(create_app(settings, deps)) as client:
        add_cart_project(client, tmp_path)
        yield client, settings


def _step(client: TestClient) -> dict[str, Any]:
    r = client.post(STEP)
    assert r.status_code == 200
    return r.json()


def _slow(request: LlmRequest) -> Any:
    time.sleep(0.5)
    return final()


def _resolve_blocked(client: TestClient, llm: FakeLlm, settings: Settings, output: str) -> str:
    """Block TKT-1, let the resolver answer `output`, wait for it; return the resolver run id."""
    set_status(settings, "shop", "TKT-1", "blocked")
    llm.responder = resolver_responder(settings.skills_dir, output)
    body = _step(client)
    assert body["reason"] == "resolving"
    wait_run(client, body["run"]["id"])
    return body["run"]["id"]


@pytest.mark.parametrize("trigger", ["blocked", "no-transition", "crash", "timeout", "question"])
def test_ft_9_1_stuck_ticket_opens_incident(trigger: str, tmp_path: Path, llm: FakeLlm) -> None:
    """FT-9.1 a stuck ticket opens one incident and starts a resolver run."""
    timeout = 0.2 if trigger == "timeout" else 1800.0
    with _shop(tmp_path, llm, timeout) as (client, settings):
        if trigger == "blocked":
            set_status(settings, "shop", "TKT-1", "blocked")
        elif trigger == "question":
            write_workspace_file(
                settings, "shop", "work/cart/questions.md", "## Q-3 [open] Which currency?\n- blocks: TKT-1\n"
            )
        elif trigger == "no-transition":
            wait_run(client, _step(client)["run"]["id"])
        elif trigger == "crash":
            llm.fail_with = LlmError("x")
            wait_run(client, _step(client)["run"]["id"])
            llm.fail_with = None
        else:
            llm.responder = _slow
            _step(client)
            time.sleep(0.3)
        body = _step(client)
        incidents = client.get(INCIDENTS).json()
    assert body["reason"] == "resolving"
    assert body["run"]["agent"] == "resolver"
    assert body["run"]["args"] == "incident=1"
    assert len(incidents) == 1
    assert incidents[0]["ticket"] == "TKT-1"
    assert incidents[0]["trigger"] == trigger
    assert incidents[0]["status"] == "open"
    bundle = (settings.workspaces_dir / "shop" / "work/cart/incidents/TKT-1-1.md").read_text()
    assert f"- trigger: {trigger}" in bundle


def test_ft_9_2_retry_action_moves_ticket_back(tmp_path: Path, llm: FakeLlm) -> None:
    """FT-9.2 a resolver retry action sets the ticket to the stage's status; the next step runs that stage."""
    with _shop(tmp_path, llm) as (client, settings):
        _resolve_blocked(client, llm, settings, RETRY_BUILD)
        body = _step(client)
        status = get_status(settings, "shop", "TKT-1")
        incident = client.get(INCIDENTS).json()[0]
        nxt = _step(client)
    assert body["reason"] == "resolved"
    assert status == "planned"
    assert incident["status"] == "resolved"
    assert "retry" in incident["action"]
    assert nxt["run"]["agent"] == "build"


@pytest.mark.parametrize(
    "output",
    ["no json here", '```json\n{"type": "merge"}\n```'],
)
def test_ft_9_3_invalid_action_needs_human(output: str, tmp_path: Path, llm: FakeLlm) -> None:
    """FT-9.3 a resolver answer that is not a valid allowlisted action escalates to a human."""
    with _shop(tmp_path, llm) as (client, settings):
        _resolve_blocked(client, llm, settings, output)
        body = _step(client)
        incident = client.get(INCIDENTS).json()[0]
        status = get_status(settings, "shop", "TKT-1")
    assert body["reason"] == "needs_human"
    assert incident["status"] == "needs_human"
    assert status == "blocked"


def test_ft_9_4_answer_action_needs_human(tmp_path: Path, llm: FakeLlm) -> None:
    """FT-9.4 an answer action is not applied yet (TKT-19) and escalates to a human."""
    action = json.dumps({"type": "answer", "question": "Q-3", "answer": "EUR", "source": "x"})
    with _shop(tmp_path, llm) as (client, settings):
        _resolve_blocked(client, llm, settings, f"```json\n{action}\n```")
        body = _step(client)
    assert body["reason"] == "needs_human"


def test_ft_9_5_needs_human_is_not_reopened(tmp_path: Path, llm: FakeLlm) -> None:
    """FT-9.5 a ticket with a needs_human incident gets no new incident or resolver run on repeated steps."""
    with _shop(tmp_path, llm) as (client, settings):
        _resolve_blocked(client, llm, settings, "no json here")
        assert _step(client)["reason"] == "needs_human"
        second = _step(client)
        incidents = client.get(INCIDENTS).json()
    assert len(incidents) == 1
    assert second["reason"] != "resolving"


def test_ft_9_6_one_incident_for_first_stuck_ticket(tmp_path: Path, llm: FakeLlm) -> None:
    """FT-9.6 with two stuck tickets only the first (map order) gets an incident."""
    with _shop(tmp_path, llm) as (client, settings):
        set_status(settings, "shop", "TKT-1", "blocked")
        set_status(settings, "shop", "TKT-3", "blocked")
        _step(client)
        incidents = client.get(INCIDENTS).json()
    assert len(incidents) == 1
    assert incidents[0]["ticket"] == "TKT-1"


def test_ft_9_7_resolver_run_failure_needs_human(tmp_path: Path, llm: FakeLlm) -> None:
    """FT-9.7 a resolver run that fails escalates the incident to a human."""
    with _shop(tmp_path, llm) as (client, settings):
        set_status(settings, "shop", "TKT-1", "blocked")
        llm.fail_with = LlmError("down")
        body = _step(client)
        wait_run(client, body["run"]["id"])
        after = _step(client)
    assert after["reason"] == "needs_human"


def test_ft_9_8_unknown_project_is_not_found(tmp_path: Path, llm: FakeLlm) -> None:
    """FT-9.8 listing incidents of an unknown project is a 404."""
    with _shop(tmp_path, llm) as (client, _settings):
        r = client.get("/api/projects/nope/features/cart/incidents")
    assert r.status_code == 404
    assert "project_not_found" in r.text


def test_ft_9_9_no_incidents_lists_empty(tmp_path: Path, llm: FakeLlm) -> None:
    """FT-9.9 a feature with nothing stuck lists no incidents."""
    with _shop(tmp_path, llm) as (client, _settings):
        r = client.get(INCIDENTS)
    assert r.status_code == 200
    assert r.json() == []


def test_ft_9_10_late_worker_does_not_overwrite_timeout(tmp_path: Path, llm: FakeLlm) -> None:
    """FT-9.10 a run timed out by the sweep stays failed when its slow worker returns later."""
    with _shop(tmp_path, llm, 0.2) as (client, _settings):
        llm.responder = _slow
        run_id = _step(client)["run"]["id"]
        time.sleep(0.3)
        _step(client)
        time.sleep(0.4)
        run = client.get(f"/api/runs/{run_id}").json()
    assert run["status"] == "failed"
    assert run["error"] == "timeout"
