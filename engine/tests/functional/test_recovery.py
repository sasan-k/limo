import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from limo.app import Deps, create_app
from limo.config import Settings
from limo.executor.local import LocalExecutor
from tests.builders import add_cart_project, set_status, wait_run, write_workspace_file
from tests.fakes.host import FakeHost
from tests.fakes.llm import FakeLlm, blocking_build, stage_responder


def restart(settings: Settings, llm: FakeLlm, host: FakeHost) -> TestClient:
    """Second app on the same settings; recovery runs inside create_app."""
    deps = Deps(executor=LocalExecutor(path_prefix=settings.scripts_dir), llm=llm, host=host)
    return TestClient(create_app(settings, deps))


def start_blocking_build(client: TestClient, llm: FakeLlm, settings: Settings) -> dict[str, Any]:
    llm.responder = blocking_build(settings.skills_dir, seconds=1.5)
    r = client.post("/api/projects/shop/features/cart/step")
    assert r.status_code == 200
    run = r.json()["run"]
    assert run is not None
    return run


def wait_for_status(client: TestClient, run_id: str, status: str) -> dict[str, Any]:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        run = client.get(f"/api/runs/{run_id}").json()
        if run["status"] == status:
            return run
        time.sleep(0.02)
    raise AssertionError(f"run {run_id} did not reach {status}")


def committed(workspace: Path, rel: str) -> str:
    return subprocess.run(
        ["git", "show", f"HEAD:{rel}"], cwd=workspace, check=True, capture_output=True, text=True
    ).stdout


def test_ft_11_1_restart_interrupts_running_build_and_resets_workspace(
    client: TestClient, llm: FakeLlm, settings: Settings, host: FakeHost, tmp_path: Path
) -> None:
    """FT-11.1 restart interrupts the running build, resets its workspace; next step retries as attempt 2."""
    add_cart_project(client, tmp_path)
    set_status(settings, "shop", "TKT-1", "planned")
    first = start_blocking_build(client, llm, settings)
    assert first["attempt"] == 1
    wait_for_status(client, first["id"], "running")
    write_workspace_file(settings, "shop", "src/cart.py", "changed\n")

    restarted = restart(settings, llm, host)
    run = restarted.get(f"/api/runs/{first['id']}").json()
    assert run["status"] == "interrupted"
    assert run["error"] == "interrupted by restart"
    workspace = settings.workspaces_dir / "shop"
    assert (workspace / "src/cart.py").read_text() == committed(workspace, "src/cart.py")

    r = restarted.post("/api/projects/shop/features/cart/step")
    assert r.status_code == 200
    second = r.json()["run"]
    assert second["agent"] == "build"
    assert second["attempt"] == 2


def test_ft_11_2_restart_with_exhausted_build_tries_opens_limits_incident(
    client: TestClient, llm: FakeLlm, settings: Settings, host: FakeHost, tmp_path: Path
) -> None:
    """FT-11.2 an interrupted build with build_tries=2 is not retried; a limits incident opens for TKT-1."""
    add_cart_project(client, tmp_path)
    set_status(settings, "shop", "TKT-1", "planned", "build_tries=2")
    first = start_blocking_build(client, llm, settings)
    wait_for_status(client, first["id"], "running")

    restarted = restart(settings, llm, host)
    r = restarted.post("/api/projects/shop/features/cart/step")
    assert r.status_code == 200
    run = r.json()["run"]
    assert run is None or run["agent"] != "build"
    incidents = restarted.get("/api/projects/shop/features/cart/incidents").json()
    items = incidents["items"] if isinstance(incidents, dict) else incidents
    assert any(i["ticket"] == "TKT-1" and i["trigger"] == "limits" for i in items)


def test_ft_11_3_second_restart_keeps_interrupted_run(
    client: TestClient, llm: FakeLlm, settings: Settings, host: FakeHost, tmp_path: Path
) -> None:
    """FT-11.3 a second restart leaves the interrupted run unchanged and does not fail."""
    add_cart_project(client, tmp_path)
    set_status(settings, "shop", "TKT-1", "planned")
    first = start_blocking_build(client, llm, settings)
    wait_for_status(client, first["id"], "running")

    restart(settings, llm, host)
    again = restart(settings, llm, host)
    run = again.get(f"/api/runs/{first['id']}").json()
    assert run["status"] == "interrupted"
    assert run["error"] == "interrupted by restart"


def test_ft_11_4_restart_without_interrupted_runs_keeps_workspace(
    client: TestClient, llm: FakeLlm, settings: Settings, host: FakeHost, tmp_path: Path
) -> None:
    """FT-11.4 with no active runs the workspace is not reset on restart."""
    add_cart_project(client, tmp_path)
    write_workspace_file(settings, "shop", "src/cart.py", "local edit\n")
    restart(settings, llm, host)
    assert (settings.workspaces_dir / "shop" / "src/cart.py").read_text() == "local edit\n"


def test_ft_11_5_restart_with_missing_workspace_still_starts(
    client: TestClient, llm: FakeLlm, settings: Settings, host: FakeHost, tmp_path: Path
) -> None:
    """FT-11.5 a missing workspace is skipped; the app starts and the run is still interrupted."""
    add_cart_project(client, tmp_path)
    set_status(settings, "shop", "TKT-1", "planned")
    first = start_blocking_build(client, llm, settings)
    wait_for_status(client, first["id"], "running")
    shutil.rmtree(settings.workspaces_dir / "shop")

    restarted = restart(settings, llm, host)
    assert restarted.get("/api/agents").status_code == 200
    run = restarted.get(f"/api/runs/{first['id']}").json()
    assert run["status"] == "interrupted"


def test_ft_11_6_late_finish_does_not_overwrite_interrupted(
    client: TestClient, llm: FakeLlm, settings: Settings, host: FakeHost, tmp_path: Path
) -> None:
    """FT-11.6 the old worker finishing after the restart leaves the run interrupted."""
    add_cart_project(client, tmp_path)
    set_status(settings, "shop", "TKT-1", "planned")
    first = start_blocking_build(client, llm, settings)
    wait_for_status(client, first["id"], "running")

    restarted = restart(settings, llm, host)
    restarted.post("/api/projects/shop/features/cart/step")
    time.sleep(2)
    run = restarted.get(f"/api/runs/{first['id']}").json()
    assert run["status"] == "interrupted"


def test_ft_11_7_first_build_run_has_attempt_one(
    client: TestClient, llm: FakeLlm, settings: Settings, tmp_path: Path
) -> None:
    """FT-11.7 the first build run of a ticket has attempt 1."""
    add_cart_project(client, tmp_path)
    set_status(settings, "shop", "TKT-1", "planned")
    llm.responder = stage_responder(settings.skills_dir)
    r = client.post("/api/projects/shop/features/cart/step")
    assert r.status_code == 200
    run = wait_run(client, r.json()["run"]["id"])
    assert run["agent"] == "build"
    assert run["attempt"] == 1
