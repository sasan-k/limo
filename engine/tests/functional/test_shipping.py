import subprocess
import time
from pathlib import Path

from fastapi.testclient import TestClient

from limo.config import Settings
from tests.builders import add_cart_project, drive_to_review, get_status, write_workspace_file
from tests.fakes.llm import FakeLlm

S = "/api/projects/shop/features/cart/step"
P = "/api/projects/shop/features/cart/poll"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout


def _workspace(settings: Settings) -> Path:
    return settings.workspaces_dir / "shop"


def _wait_run(client: TestClient, run: dict) -> None:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if client.get(f"/api/runs/{run['id']}").json()["status"] in ("succeeded", "failed"):
            return
        time.sleep(0.02)
    raise AssertionError(f"run {run['id']} did not finish")


def _ship(client: TestClient, llm: FakeLlm, settings: Settings) -> None:
    drive_to_review(client, llm, settings)
    r = client.post(S)
    assert r.json()["reason"] == "shipped"


def test_ft_7_1_ship_pushes_ticket_branch_without_work(client, llm, settings, host, tmp_path):
    """FT-7.1 SC-24 OP-1:happy"""
    add_cart_project(client, tmp_path)
    drive_to_review(client, llm, settings)
    write_workspace_file(settings, "shop", "src/cart.py", "def total() -> int:\n    return 1\n")
    write_workspace_file(settings, "shop", "work/cart/reports/x.md", "local")
    r = client.post(S)
    assert r.status_code == 200
    assert r.json()["reason"] == "shipped"
    bare = tmp_path / "shop.git"
    assert "return 1" in _git(bare, "show", "limo/cart/TKT-1:src/cart.py")
    assert "work/cart/reports/x.md" not in _git(bare, "ls-tree", "-r", "--name-only", "limo/cart/TKT-1")
    mr = host.mrs[1]
    assert (mr.branch, mr.base, mr.state) == ("limo/cart/TKT-1", "main", "open")
    assert get_status(settings, "shop", "TKT-1") == "review"


def test_ft_7_2_ship_enables_auto_merge_and_never_merges(client, llm, settings, host, tmp_path):
    """FT-7.2 SC-25 OP-4:happy"""
    add_cart_project(client, tmp_path)
    _ship(client, llm, settings)
    assert ("enable_auto_merge", 1) in host.calls
    assert not any(name == "merge" for name, _ in host.calls)


def test_ft_7_3_merged_mr_finishes_ticket(client, llm, settings, host, tmp_path):
    """FT-7.3 SC-26 OP-2:happy"""
    add_cart_project(client, tmp_path)
    _ship(client, llm, settings)
    host.approve(1)
    host.merge(1)
    r = client.post(P)
    assert r.status_code == 200
    assert r.json()["merged"] == ["TKT-1"]
    assert get_status(settings, "shop", "TKT-1") == "done"


def test_ft_7_4_unapproved_mr_changes_nothing(client, llm, settings, host, tmp_path):
    """FT-7.4 SC-27 OP-2:invalid-state"""
    add_cart_project(client, tmp_path)
    _ship(client, llm, settings)
    r = client.post(P)
    assert r.json() == {"merged": [], "changes_requested": []}
    assert get_status(settings, "shop", "TKT-1") == "review"


def test_ft_7_5_next_ticket_branches_from_merged_base(client, llm, settings, host, tmp_path):
    """FT-7.5 SC-28 OP-3:happy"""
    add_cart_project(client, tmp_path)
    _ship(client, llm, settings)
    host.approve(1)
    host.merge(1)
    client.post(P)
    r = client.post(S)
    assert r.status_code == 200
    run = r.json()["run"]
    assert (run["agent"], run["ticket"]) == ("plan", "TKT-2")
    _wait_run(client, run)
    ws = _workspace(settings)
    assert _git(ws, "rev-parse", "--abbrev-ref", "HEAD").strip() == "limo/cart/TKT-2"
    main_sha = _git(tmp_path / "shop.git", "rev-parse", "main").strip()
    check = subprocess.run(["git", "-C", str(ws), "merge-base", "--is-ancestor", main_sha, "HEAD"])
    assert check.returncode == 0


def test_ft_7_6_requested_changes_return_ticket_to_todo(client, llm, settings, host, tmp_path):
    """FT-7.6 SC-29 OP-3:idempotency"""
    add_cart_project(client, tmp_path)
    _ship(client, llm, settings)
    host.request_changes(1, "rename total() to cart_total()")
    r = client.post(P)
    assert r.json()["changes_requested"] == ["TKT-1"]
    report = _workspace(settings) / "work/cart/reports/TKT-1-review-1.md"
    assert "rename total() to cart_total()" in report.read_text()
    assert get_status(settings, "shop", "TKT-1") == "todo"
    r = client.post(S)
    run = r.json()["run"]
    assert (run["agent"], run["ticket"]) == ("plan", "TKT-1")
    _wait_run(client, run)
    assert _git(_workspace(settings), "rev-parse", "--abbrev-ref", "HEAD").strip() == "limo/cart/TKT-1"


def test_ft_7_7_reship_updates_existing_mr(client, llm, settings, host, tmp_path):
    """FT-7.7 OP-1:conflict"""
    add_cart_project(client, tmp_path)
    _ship(client, llm, settings)
    host.request_changes(1, "rename total() to cart_total()")
    client.post(P)
    r = client.post(S)
    _wait_run(client, r.json()["run"])
    drive_to_review(client, llm, settings)
    write_workspace_file(settings, "shop", "src/cart.py", "def total() -> int:\n    return 2\n")
    r = client.post(S)
    assert r.json()["reason"] == "shipped"
    assert len(host.mrs) == 1
    assert "return 2" in _git(tmp_path / "shop.git", "show", "limo/cart/TKT-1:src/cart.py")


def test_ft_7_8_ship_is_idempotent(client, llm, settings, host, tmp_path):
    """FT-7.8 OP-1:idempotency, OP-4:idempotency"""
    add_cart_project(client, tmp_path)
    _ship(client, llm, settings)
    r = client.post(S)
    assert r.json()["reason"] != "shipped"
    assert len(host.mrs) == 1
    assert host.calls.count(("enable_auto_merge", 1)) == 1


def test_ft_7_9_host_failure_is_retried_by_next_step(client, llm, settings, host, tmp_path):
    """FT-7.9 OP-1:external-failure, OP-4:external-failure"""
    add_cart_project(client, tmp_path)
    drive_to_review(client, llm, settings)
    host.fail_next.add("open_merge_request")
    r = client.post(S)
    assert r.status_code == 502
    assert r.json()["error"]["code"] == "host_error"
    assert host.mrs == {}
    assert get_status(settings, "shop", "TKT-1") == "review"
    r = client.post(S)
    assert r.json()["reason"] == "shipped"
    assert len(host.mrs) == 1


def test_ft_7_10_poll_rejects_invalid_feature(client, llm, settings, host, tmp_path):
    """FT-7.10 OP-2:validation"""
    add_cart_project(client, tmp_path)
    r = client.post("/api/projects/shop/features/Bad!/poll")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_ft_7_11_poll_unknown_project(client, llm, settings, host, tmp_path):
    """FT-7.11 OP-2:not-found"""
    add_cart_project(client, tmp_path)
    r = client.post("/api/projects/nope/features/cart/poll")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "project_not_found"


def test_ft_7_12_poll_is_idempotent_after_merge(client, llm, settings, host, tmp_path):
    """FT-7.12 OP-2:idempotency"""
    add_cart_project(client, tmp_path)
    _ship(client, llm, settings)
    host.approve(1)
    host.merge(1)
    client.post(P)
    r = client.post(P)
    assert r.json()["merged"] == []
    assert get_status(settings, "shop", "TKT-1") == "done"


def test_ft_7_13_poll_with_nothing_shipped(client, llm, settings, host, tmp_path):
    """FT-7.13 OP-2:boundary"""
    add_cart_project(client, tmp_path)
    r = client.post(P)
    assert r.json() == {"merged": [], "changes_requested": []}


def test_ft_7_14_poll_host_failure(client, llm, settings, host, tmp_path):
    """FT-7.14 OP-2:external-failure"""
    add_cart_project(client, tmp_path)
    _ship(client, llm, settings)
    host.fail_next.add("merge_request_status")
    r = client.post(P)
    assert r.status_code == 502
    assert r.json()["error"]["code"] == "host_error"
    assert get_status(settings, "shop", "TKT-1") == "review"
