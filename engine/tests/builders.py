import subprocess
import time
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

CART_PLAN = "# TKT-1\n\n## Context pack\n- `src/cart.py` — cart logic\n\n## Steps\n"


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


def add_cart_project(client: TestClient, root: Path) -> None:
    """Add project "shop" whose repo has src/cart.py, src/payment.py, CLAUDE.md and the TKT-1 plan of feature
    cart."""
    url = make_git_repo(
        root,
        "shop",
        {
            "src/cart.py": "def total() -> int:\n    return 0\n",
            "src/payment.py": "SECRET = 1\n",
            "CLAUDE.md": "secret house rules\n",
            "work/cart/plans/TKT-1.md": CART_PLAN,
        },
    )
    r = client.post("/api/projects", json={"name": "shop", "git_url": url, "host": "github"})
    assert r.status_code == 201


def start_and_wait(client: TestClient, agent: str, ticket: str | None = "TKT-1") -> dict[str, Any]:
    """POST a run for feature cart and poll GET /api/runs/{id} until it is succeeded or failed (5 s max)."""
    r = client.post("/api/projects/shop/runs", json={"agent": agent, "feature": "cart", "ticket": ticket})
    assert r.status_code == 202
    run_id = r.json()["id"]
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        run = client.get(f"/api/runs/{run_id}").json()
        if run["status"] in ("succeeded", "failed"):
            return run
        time.sleep(0.02)
    raise AssertionError(f"run {run_id} did not finish")
