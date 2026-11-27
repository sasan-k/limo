import subprocess
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from limo.config import Settings
from limo.llm.ports import LlmError
from tests.builders import add_cart_project, drive_to_review, wait_run, write_workspace_file
from tests.fakes.llm import FakeLlm

MAP_POSTS = """feature: posts
tickets:
  - id: TKT-1
    title: Readers can comment
    scope: [api]
    scenarios: [SC-1]
    depends_on: []
"""
MAP_BOGUS = "feature: posts\ntickets:\n  - id: TKT-1\n    bogus: x\n"
FEATURE_POSTS = """Feature: Comments

  @SC-1 @REQ-1
  Scenario: Reader comments on a post
    Given a post
    When a reader comments
    Then the comment is listed
"""
NFR_HEADER = "| id | req | category | target | how | status |\n"
NFR_ROW = "| NFR-1 | REQ-1 | performance | x | y | pending |\n"
BIG = "a" * 200_000


def _features(project: str) -> str:
    return f"/api/projects/{project}/features"


def _intake(client: TestClient, project: str = "shop", name: str = "posts") -> None:
    r = client.post(_features(project), json={"name": name, "requirements": "Readers can comment on posts."})
    assert r.status_code == 201


def _step(client: TestClient, project: str, feature: str) -> dict[str, Any]:
    r = client.post(f"{_features(project)}/{feature}/step")
    assert r.status_code == 200
    return r.json()


def _phase(client: TestClient, project: str, name: str) -> str:
    rows = client.get(_features(project)).json()
    return next(f["phase"] for f in rows if f["name"] == name)


def _spec_done(client: TestClient, settings: Settings, map_text: str, nfr: str) -> None:
    """Intake posts, run its spec stage to the end, then write the spec outputs into the workspace."""
    run = _step(client, "shop", "posts")["run"]
    assert run["agent"] == "spec"
    wait_run(client, run["id"])
    write_workspace_file(settings, "shop", "work/posts/map.yaml", map_text)
    write_workspace_file(settings, "shop", "work/posts/features/a.feature", FEATURE_POSTS)
    write_workspace_file(settings, "shop", "work/posts/nfr.md", nfr)


def _git(*args: str, cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def test_ft_6_1_intake_creates_feature_and_lists_it(
    client: TestClient, settings: Settings, tmp_path: Path
) -> None:
    """FT-6.1 intake saves the requirements and lists the feature."""
    add_cart_project(client, tmp_path)
    write_workspace_file(settings, "shop", "context/INDEX.md", "# ctx\n")
    body = {"name": "posts", "requirements": "Readers can comment on posts."}
    r = client.post(_features("shop"), json=body)
    assert r.status_code == 201
    assert r.json()["phase"] == "spec"
    path = settings.workspaces_dir / "shop" / "work/posts/requirements/posts.md"
    assert path.read_text() == "Readers can comment on posts."
    assert [f["name"] for f in client.get(_features("shop")).json()] == ["posts"]


def test_ft_6_2_first_step_runs_architecture(client: TestClient, llm: FakeLlm, tmp_path: Path) -> None:
    """FT-6.2 a project without context starts with the architecture phase."""
    add_cart_project(client, tmp_path, name="blog")
    _intake(client, "blog")
    assert _phase(client, "blog", "posts") == "architecture"
    run = _step(client, "blog", "posts")["run"]
    assert run["agent"] == "architecture"
    assert run["args"] == "mode=init-existing"
    wait_run(client, run["id"])
    assert llm.requests[0].messages[0]["content"] == "feature=posts mode=init-existing"
    assert _phase(client, "blog", "posts") == "architecture"


def test_ft_6_3_spec_done_then_nfr_phase(client: TestClient, settings: Settings, tmp_path: Path) -> None:
    """FT-6.3 a spec run with an NFR row moves the feature to the nfr phase."""
    add_cart_project(client, tmp_path)
    write_workspace_file(settings, "shop", "context/INDEX.md", "# ctx\n")
    _intake(client)
    _spec_done(client, settings, MAP_POSTS, NFR_HEADER + NFR_ROW)
    run = _step(client, "shop", "posts")["run"]
    assert run["agent"] == "architecture"
    assert run["args"] == "mode=nfr posts"
    wait_run(client, run["id"])
    assert _phase(client, "shop", "posts") == "nfr"


def test_ft_6_4_no_nfr_rows_goes_to_tickets(client: TestClient, settings: Settings, tmp_path: Path) -> None:
    """FT-6.4 without NFR rows the feature moves to tickets and dispatches TKT-1."""
    add_cart_project(client, tmp_path)
    write_workspace_file(settings, "shop", "context/INDEX.md", "# ctx\n")
    _intake(client)
    _spec_done(client, settings, MAP_POSTS, NFR_HEADER)
    run = _step(client, "shop", "posts")["run"]
    assert run["agent"] == "plan"
    assert run["ticket"] == "TKT-1"
    wait_run(client, run["id"])
    assert _phase(client, "shop", "posts") == "tickets"


def test_ft_6_5_work_stays_out_of_git(
    client: TestClient, llm: FakeLlm, settings: Settings, tmp_path: Path
) -> None:
    """FT-6.5 work/ is excluded from git in the workspace and never pushed."""
    add_cart_project(client, tmp_path)
    write_workspace_file(settings, "shop", "context/INDEX.md", "# ctx\n")
    _intake(client)
    drive_to_review(client, llm, settings)
    assert _step(client, "shop", "cart")["reason"] == "shipped"
    ws = settings.workspaces_dir / "shop"
    assert "work/" not in _git("status", "--porcelain", cwd=ws)
    tree = _git("ls-tree", "-r", "--name-only", "limo/cart/TKT-1", cwd=tmp_path / "shop.git")
    assert not any(line.startswith("work/posts/") for line in tree.splitlines())
    assert "work/" in (ws / ".git/info/exclude").read_text()


def test_ft_6_6_invalid_intake_is_422(client: TestClient, tmp_path: Path) -> None:
    """FT-6.6 invalid name, empty requirements or an extra field are rejected."""
    add_cart_project(client, tmp_path)
    for body in (
        {"name": "Posts!", "requirements": "x"},
        {"name": "posts", "requirements": ""},
        {"name": "posts", "requirements": "x", "x": 1},
    ):
        assert client.post(_features("shop"), json=body).status_code == 422


def test_ft_6_7_unknown_project_is_404(client: TestClient) -> None:
    """FT-6.7 intake and list on an unknown project return 404."""
    r = client.post(_features("nope"), json={"name": "posts", "requirements": "x"})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "project_not_found"
    r = client.get(_features("nope"))
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "project_not_found"


def test_ft_6_8_duplicate_feature_is_409(client: TestClient, tmp_path: Path) -> None:
    """FT-6.8 a repeated intake and a name whose work/ dir already exists are conflicts."""
    add_cart_project(client, tmp_path)
    _intake(client)
    r = client.post(_features("shop"), json={"name": "posts", "requirements": "x"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "feature_exists"
    r = client.post(_features("shop"), json={"name": "cart", "requirements": "x"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "feature_exists"


def test_ft_6_9_context_project_starts_with_spec(
    client: TestClient, settings: Settings, tmp_path: Path
) -> None:
    """FT-6.9 a project with context skips architecture and starts with spec."""
    add_cart_project(client, tmp_path)
    write_workspace_file(settings, "shop", "context/INDEX.md", "# ctx\n")
    _intake(client)
    run = _step(client, "shop", "posts")["run"]
    assert run["agent"] == "spec"
    wait_run(client, run["id"])


def test_ft_6_10_failed_stage_reports_stage_failed(
    client: TestClient, llm: FakeLlm, settings: Settings, tmp_path: Path
) -> None:
    """FT-6.10 a failed phase run stops the feature with reason stage_failed."""
    add_cart_project(client, tmp_path)
    write_workspace_file(settings, "shop", "context/INDEX.md", "# ctx\n")
    _intake(client)
    llm.fail_with = LlmError("down")
    run = _step(client, "shop", "posts")["run"]
    assert wait_run(client, run["id"])["status"] == "failed"
    step = _step(client, "shop", "posts")
    assert step["run"] is None
    assert step["reason"] == "stage_failed"


def test_ft_6_11_invalid_map_is_409(client: TestClient, settings: Settings, tmp_path: Path) -> None:
    """FT-6.11 a map.yaml that fx map-check rejects blocks the feature with map_invalid."""
    add_cart_project(client, tmp_path)
    write_workspace_file(settings, "shop", "context/INDEX.md", "# ctx\n")
    _intake(client)
    _spec_done(client, settings, MAP_BOGUS, NFR_HEADER)
    r = client.post(f"{_features('shop')}/posts/step")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "map_invalid"


def test_ft_6_12_requirements_size_boundary(client: TestClient, tmp_path: Path) -> None:
    """FT-6.12 requirements of 200,000 chars are accepted, 200,001 are rejected."""
    add_cart_project(client, tmp_path)
    r = client.post(_features("shop"), json={"name": "posts", "requirements": BIG})
    assert r.status_code == 201
    r = client.post(_features("shop"), json={"name": "big2", "requirements": BIG + "a"})
    assert r.status_code == 422


def test_ft_6_13_empty_list_without_intake(client: TestClient, tmp_path: Path) -> None:
    """FT-6.13 a project with no intake lists no features."""
    add_cart_project(client, tmp_path)
    assert client.get(_features("shop")).json() == []
