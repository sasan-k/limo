import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from limo.config import Settings
from tests.builders import add_cart_project, get_status, set_status, write_workspace_file
from tests.fakes.llm import FakeLlm, stage_responder


def post_step(client: TestClient, project: str = "shop", feature: str = "cart") -> Any:
    return client.post(f"/api/projects/{project}/features/{feature}/step")


def wait_for_run(client: TestClient, run_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        run = client.get(f"/api/runs/{run_id}").json()
        if run["status"] in ("succeeded", "failed"):
            return run
        time.sleep(0.02)
    raise AssertionError(f"run {run_id} did not finish")


@pytest.mark.parametrize(
    ("status", "agent"),
    [("todo", "plan"), ("planned", "build"), ("built", "verify"), ("verified", "close")],
)
def test_ft_5_1_step_starts_the_stage_for_the_ticket_status(
    client: TestClient, settings: Settings, tmp_path: Path, status: str, agent: str
) -> None:
    """FT-5.1 `step` starts the stage that matches the first ticket status."""
    add_cart_project(client, tmp_path)
    set_status(settings, "shop", "TKT-1", status)
    r = post_step(client)
    assert r.status_code == 200
    assert r.json()["reason"] == "started"
    assert r.json()["run"]["agent"] == agent
    assert r.json()["run"]["ticket"] == "TKT-1"


def test_ft_5_2_blocked_ticket_leaves_its_dependents_unstarted(
    client: TestClient, settings: Settings, tmp_path: Path
) -> None:
    """FT-5.2 TKT-1 blocked, TKT-3 done: TKT-2 waits on TKT-1 and is not started."""
    add_cart_project(client, tmp_path)
    set_status(settings, "shop", "TKT-1", "blocked")
    set_status(settings, "shop", "TKT-3", "done")
    r = post_step(client)
    assert r.status_code == 200
    run = r.json()["run"]
    assert run is None or run["ticket"] != "TKT-2"


def test_ft_5_3_ticket_in_review_is_not_started(
    client: TestClient, settings: Settings, tmp_path: Path
) -> None:
    """FT-5.3 TKT-1 in review, TKT-3 done: `step` starts nothing."""
    add_cart_project(client, tmp_path)
    set_status(settings, "shop", "TKT-1", "review")
    set_status(settings, "shop", "TKT-3", "done")
    r = post_step(client)
    assert r.status_code == 200
    assert r.json()["run"] is None
    assert r.json()["reason"] == "shipped"
    again = post_step(client)
    assert again.json()["run"] is None
    assert again.json()["reason"] == "no_ready_ticket"


def test_ft_5_4_one_run_at_a_time_and_stages_in_order(
    client: TestClient, settings: Settings, llm: FakeLlm, tmp_path: Path
) -> None:
    """FT-5.4 a step while a run is active starts nothing; runs go plan, build, verify, close per ticket."""
    add_cart_project(client, tmp_path)
    llm.responder = stage_responder(settings.skills_dir)
    started: list[tuple[str, str]] = []
    for _ in range(16):
        first = post_step(client).json()
        if first["reason"] == "no_ready_ticket":
            break
        if first["reason"] == "shipped":
            continue
        assert first["reason"] == "started"
        second = post_step(client).json()
        assert second["reason"] == "run_active"
        started.append((first["run"]["agent"], first["run"]["ticket"]))
        wait_for_run(client, first["run"]["id"])
    else:
        raise AssertionError("step kept starting runs")
    assert started == [
        ("plan", "TKT-1"),
        ("build", "TKT-1"),
        ("verify", "TKT-1"),
        ("close", "TKT-1"),
        ("plan", "TKT-3"),
        ("build", "TKT-3"),
        ("verify", "TKT-3"),
        ("close", "TKT-3"),
    ]
    assert get_status(settings, "shop", "TKT-1") == "review"


def test_ft_5_5_build_run_starts_with_only_the_task_message(
    client: TestClient, settings: Settings, llm: FakeLlm, tmp_path: Path
) -> None:
    """FT-5.5 the build run's first LLM request holds exactly one message: the task."""
    add_cart_project(client, tmp_path)
    llm.responder = stage_responder(settings.skills_dir)
    for _ in range(2):
        r = post_step(client).json()
        assert r["reason"] == "started"
        wait_for_run(client, r["run"]["id"])
    build_system = (settings.skills_dir / "build" / "SKILL.md").read_text()
    first = next(req for req in llm.requests if req.system == build_system)
    assert len(first.messages) == 1


def test_ft_5_6_invalid_feature_name_is_rejected(client: TestClient, tmp_path: Path) -> None:
    """FT-5.6 feature `Bad!` gives 422 validation_error."""
    add_cart_project(client, tmp_path)
    r = post_step(client, feature="Bad!")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_ft_5_7_unknown_project_or_feature_is_not_found(client: TestClient, tmp_path: Path) -> None:
    """FT-5.7 project `nope` gives 404 project_not_found; feature `posts` gives 404 feature_not_found."""
    add_cart_project(client, tmp_path)
    r = post_step(client, project="nope")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "project_not_found"
    r = post_step(client, feature="posts")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "feature_not_found"


def test_ft_5_8_broken_map_is_a_conflict(client: TestClient, settings: Settings, tmp_path: Path) -> None:
    """FT-5.8 a map.yaml with an unknown key gives 409 map_invalid."""
    add_cart_project(client, tmp_path)
    write_workspace_file(
        settings, "shop", "work/cart/map.yaml", "feature: cart\ntickets:\n  - id: TKT-1\n    bogus: x\n"
    )
    r = post_step(client)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "map_invalid"


def test_ft_5_9_all_tickets_done_starts_nothing(
    client: TestClient, settings: Settings, tmp_path: Path
) -> None:
    """FT-5.9 with all three tickets done, `step` starts nothing."""
    add_cart_project(client, tmp_path)
    for ticket in ("TKT-1", "TKT-2", "TKT-3"):
        set_status(settings, "shop", ticket, "done")
    r = post_step(client)
    assert r.json()["run"] is None
    assert r.json()["reason"] == "no_ready_ticket"


def test_ft_5_10_same_feature_in_two_projects_keeps_state_apart(
    client: TestClient, settings: Settings, tmp_path: Path
) -> None:
    """FT-5.10 TKT-1 review in shop leaves TKT-1 todo in blog; a step on blog plans TKT-1 there."""
    add_cart_project(client, tmp_path)
    add_cart_project(client, tmp_path, name="blog")
    set_status(settings, "shop", "TKT-1", "review")
    assert get_status(settings, "blog", "TKT-1") == "todo"
    r = post_step(client, project="blog")
    assert r.json()["reason"] == "started"
    assert r.json()["run"]["project"] == "blog"
    assert r.json()["run"]["agent"] == "plan"
    assert r.json()["run"]["ticket"] == "TKT-1"
