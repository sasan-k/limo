from typing import Any

from fastapi.testclient import TestClient
from httpx import Response

from limo.config import Settings
from tests.builders import add_cart_project, set_status, wait_run, write_workspace_file
from tests.fakes.host import FakeHost

POSTS_MAP = """feature: posts
tickets:
  - id: TKT-1
    title: Posts can be listed
    scope: [api]
    scenarios: [SC-1]
    depends_on: []
"""
POSTS_FEATURE = """Feature: Posts

  @SC-1 @REQ-1
  Scenario: Reader lists posts
    Given a post
    When a reader lists posts
    Then the post is listed
"""
NFR_HEADER = "| id | req | category | target | how | status |\n"
CART_TITLES = ["TKT-1: Cart shows a total", "TKT-2: Cart total includes tax", "TKT-3: Cart can be emptied"]


def _features(project: str) -> str:
    return f"/api/projects/{project}/features"


def _post_step(client: TestClient, feature: str, project: str = "shop") -> Response:
    return client.post(f"{_features(project)}/{feature}/step")


def _run_step(client: TestClient, feature: str, project: str = "shop") -> dict[str, Any]:
    """POST step, expect 200, and wait for the started run (if any) to finish."""
    r = _post_step(client, feature, project)
    assert r.status_code == 200
    body = r.json()
    if body["run"] is not None:
        wait_run(client, body["run"]["id"])
    return body


def _issue_by_title(host: FakeHost, title: str) -> tuple[int, Any]:
    for number, issue in host.issues.items():
        if issue.title == title:
            return number, issue
    raise AssertionError(f"no issue titled {title}")


def test_ft_8_1_first_sync_creates_issue_per_ticket(
    client: TestClient, host: FakeHost, settings: Settings, tmp_path: Any
) -> None:
    """FT-8.1 the first step in the tickets phase creates one issue per ticket with its status label."""
    add_cart_project(client, tmp_path)
    write_workspace_file(settings, "shop", "context/INDEX.md", "# ctx\n")
    r = client.post(_features("shop"), json={"name": "posts", "requirements": "Posts can be listed."})
    assert r.status_code == 201
    _run_step(client, "posts")
    write_workspace_file(settings, "shop", "work/posts/map.yaml", POSTS_MAP)
    write_workspace_file(settings, "shop", "work/posts/features/a.feature", POSTS_FEATURE)
    write_workspace_file(settings, "shop", "work/posts/nfr.md", NFR_HEADER)
    _run_step(client, "posts")
    assert [i.title for i in host.issues.values()] == ["TKT-1: Posts can be listed"]
    assert host.issues[1].labels == ["limo:todo"]


def test_ft_8_2_status_change_moves_label(
    client: TestClient, host: FakeHost, settings: Settings, tmp_path: Any
) -> None:
    """FT-8.2 a changed ticket status replaces the issue's limo label."""
    add_cart_project(client, tmp_path)
    _run_step(client, "cart")
    set_status(settings, "shop", "TKT-1", "planned")
    _run_step(client, "cart")
    set_status(settings, "shop", "TKT-1", "built")
    _run_step(client, "cart")
    _, issue = _issue_by_title(host, "TKT-1: Cart shows a total")
    assert "limo:built" in issue.labels
    assert "limo:planned" not in issue.labels


def test_ft_8_3_repeated_sync_creates_no_duplicates(
    client: TestClient, host: FakeHost, tmp_path: Any
) -> None:
    """FT-8.3 a second step does not create issues again."""
    add_cart_project(client, tmp_path)
    _run_step(client, "cart")
    _run_step(client, "cart")
    assert len(host.issues) == 3
    assert sum(1 for c in host.calls if c[0] == "create_issue") == 3


def test_ft_8_4_issues_in_map_order(client: TestClient, host: FakeHost, tmp_path: Any) -> None:
    """FT-8.4 issues are created in map order with the ticket id in the title."""
    add_cart_project(client, tmp_path)
    _run_step(client, "cart")
    assert [host.issues[n].title for n in sorted(host.issues)] == CART_TITLES


def test_ft_8_5_create_failure_is_502_then_retried(client: TestClient, host: FakeHost, tmp_path: Any) -> None:
    """FT-8.5 a host failure during create returns 502 host_error and the next step retries."""
    add_cart_project(client, tmp_path)
    host.fail_next.add("create_issue")
    r = _post_step(client, "cart")
    assert r.status_code == 502
    assert r.json()["error"]["code"] == "host_error"
    assert host.issues == {}
    _run_step(client, "cart")
    assert len(host.issues) == 3


def test_ft_8_6_unchanged_status_makes_no_host_call(
    client: TestClient, host: FakeHost, tmp_path: Any
) -> None:
    """FT-8.6 a ticket whose status did not change gets no set_issue_status call."""
    add_cart_project(client, tmp_path)
    _run_step(client, "cart")
    number, _ = _issue_by_title(host, "TKT-1: Cart shows a total")
    _run_step(client, "cart")
    assert host.calls.count(("set_issue_status", number)) == 1


def test_ft_8_7_label_failure_is_502_then_retried(
    client: TestClient, host: FakeHost, settings: Settings, tmp_path: Any
) -> None:
    """FT-8.7 a host failure during a label change returns 502 host_error and the next step retries."""
    add_cart_project(client, tmp_path)
    _run_step(client, "cart")
    set_status(settings, "shop", "TKT-1", "planned")
    host.fail_next.add("set_issue_status")
    r = _post_step(client, "cart")
    assert r.status_code == 502
    assert r.json()["error"]["code"] == "host_error"
    _run_step(client, "cart")
    _, issue = _issue_by_title(host, "TKT-1: Cart shows a total")
    assert "limo:planned" in issue.labels


def test_issue_sync_skips_tickets_finished_before_first_sync(
    client: TestClient, host: FakeHost, settings: Settings, tmp_path: Any
) -> None:
    """Tickets already done or abandoned when first seen get no issue; open tickets still do."""
    add_cart_project(client, tmp_path)
    set_status(settings, "shop", "TKT-1", "done")
    set_status(settings, "shop", "TKT-3", "abandoned")
    _run_step(client, "cart")
    assert [i.title for i in host.issues.values()] == ["TKT-2: Cart total includes tax"]
    _run_step(client, "cart")
    assert len(host.issues) == 1
