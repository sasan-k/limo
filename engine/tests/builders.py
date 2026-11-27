import os
import subprocess
import time
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from limo.config import Settings
from tests.fakes.llm import FakeLlm, stage_responder

CART_PLAN = "# TKT-1\n\n## Context pack\n- `src/cart.py` — cart logic\n\n## Steps\n"
CART_MAP = """feature: cart
tickets:
  - id: TKT-1
    title: Cart shows a total
    scope: [api]
    scenarios: [SC-1]
    depends_on: []
  - id: TKT-2
    title: Cart total includes tax
    scope: [api]
    scenarios: [SC-2]
    depends_on: [TKT-1]
  - id: TKT-3
    title: Cart can be emptied
    scope: [api]
    scenarios: [SC-3]
    depends_on: []
"""


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def make_git_repo(root: Path, name: str, files: dict[str, str]) -> str:
    """Create bare repo <root>/<name>.git whose branch main holds `files`; return its file:// URL."""
    src = root / f"{name}-src"
    src.mkdir(parents=True)
    for rel, text in files.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text(text)
    _git("init", "-b", "main", cwd=src)
    _git("add", ".", cwd=src)
    _git("-c", "user.name=limo", "-c", "user.email=limo@example.com", "commit", "-m", "init", cwd=src)
    bare = root / f"{name}.git"
    _git("clone", "--bare", str(src), str(bare), cwd=root)
    return bare.as_uri()


def make_empty_bare_repo(root: Path, name: str) -> str:
    """Create an empty bare repo <root>/<name>.git (no commits); return its file:// URL."""
    bare = root / f"{name}.git"
    _git("init", "--bare", str(bare), cwd=root)
    return bare.as_uri()


def add_cart_project(client: TestClient, root: Path, name: str = "shop") -> None:
    """Add project `name` whose repo has src/cart.py, src/payment.py, CLAUDE.md, the feature cart map and the
    TKT-1 and TKT-3 plans."""
    url = make_git_repo(
        root,
        name,
        {
            "src/cart.py": "def total() -> int:\n    return 0\n",
            "src/payment.py": "SECRET = 1\n",
            "CLAUDE.md": "secret house rules\n",
            "work/cart/map.yaml": CART_MAP,
            "work/cart/plans/TKT-1.md": CART_PLAN,
            "work/cart/plans/TKT-3.md": CART_PLAN,
        },
    )
    r = client.post("/api/projects", json={"name": name, "git_url": url, "host": "github"})
    assert r.status_code == 201


def fx_env(settings: Settings, project: str) -> dict[str, str]:
    env = dict(os.environ)
    env["PATH"] = f"{settings.scripts_dir}{os.pathsep}{env.get('PATH', '')}"
    env["FX_DB"] = str(settings.db_path)
    env["FX_SCOPE"] = project
    return env


def set_status(settings: Settings, project: str, ticket: str, status: str) -> None:
    subprocess.run(
        ["fx", "set", "work/cart", ticket, f"status={status}"],
        cwd=settings.workspaces_dir / project,
        env=fx_env(settings, project),
        check=True,
        capture_output=True,
    )


def get_status(settings: Settings, project: str, ticket: str) -> str:
    out = subprocess.run(
        ["fx", "status", "work/cart", ticket],
        cwd=settings.workspaces_dir / project,
        env=fx_env(settings, project),
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return out.split("status=", 1)[1].split()[0]


def write_workspace_file(settings: Settings, project: str, rel: str, text: str) -> None:
    path = settings.workspaces_dir / project / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def wait_run(client: TestClient, run_id: str) -> dict[str, Any]:
    """Poll GET /api/runs/{id} until it is succeeded or failed (5 s max)."""
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        run = client.get(f"/api/runs/{run_id}").json()
        if run["status"] in ("succeeded", "failed"):
            return run
        time.sleep(0.02)
    raise AssertionError(f"run {run_id} did not finish")


def start_and_wait(
    client: TestClient, agent: str, ticket: str | None = "TKT-1", project: str = "shop"
) -> dict[str, Any]:
    """POST a run for feature cart and wait for it to finish (see wait_run)."""
    body = {"agent": agent, "feature": "cart", "ticket": ticket}
    r = client.post(f"/api/projects/{project}/runs", json=body)
    assert r.status_code == 202
    return wait_run(client, r.json()["id"])


def drive_to_review(client: TestClient, llm: FakeLlm, settings: Settings, project: str = "shop") -> None:
    """Run plan/build/verify/close for TKT-1 through POST step until its status is review (max 8 steps)."""
    llm.responder = stage_responder(settings.skills_dir)
    for _ in range(8):
        if get_status(settings, project, "TKT-1") == "review":
            return
        r = client.post(f"/api/projects/{project}/features/cart/step")
        assert r.status_code == 200
        run = r.json()["run"]
        if run is not None:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                state = client.get(f"/api/runs/{run['id']}").json()["status"]
                if state in ("succeeded", "failed"):
                    break
                time.sleep(0.02)
    raise AssertionError("TKT-1 did not reach review")
