import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from limo.config import Settings
from tests.builders import add_cart_project, set_status, wait_run
from tests.fakes.host import FakeHost
from tests.fakes.llm import FakeLlm, resolver_responder

STEP = "/api/projects/shop/features/cart/step"
POLL = "/api/projects/shop/features/cart/poll"
INCIDENTS = "/api/projects/shop/features/cart/incidents"
INBOX = "/api/inbox"
LABEL = "factory:needs-human"
ESCALATE = (
    "```json\n"
    + json.dumps({"type": "escalate", "summary": "Tax rule unclear", "ask": "Should totals include tax?"})
    + "\n```"
)
RETRY = "```json\n" + json.dumps({"type": "retry", "stage": "build"}) + "\n```"


def _flow(client: TestClient) -> dict[str, Any]:
    first = client.post(STEP)
    assert first.status_code == 200
    assert first.json()["reason"] == "resolving"
    wait_run(client, first.json()["run"]["id"])
    second = client.post(STEP)
    assert second.status_code == 200
    return second.json()


def _tkt1_number(host: FakeHost) -> int:
    return next(number for number, issue in host.issues.items() if issue.title.startswith("TKT-1:"))


def _tkt1_issue(host: FakeHost) -> Any:
    return host.issues[_tkt1_number(host)]


def _escalation_item(client: TestClient) -> dict[str, Any]:
    return next(item for item in client.get(INBOX).json() if item["kind"] == "escalation")


def _escalated(client: TestClient, tmp_path: Path, settings: Settings, llm: FakeLlm) -> dict[str, Any]:
    add_cart_project(client, tmp_path)
    set_status(settings, "shop", "TKT-1", "blocked")
    llm.responder = resolver_responder(settings.skills_dir, ESCALATE)
    return _flow(client)


def _two_resolves(client: TestClient, tmp_path: Path, settings: Settings, llm: FakeLlm) -> None:
    add_cart_project(client, tmp_path)
    llm.responder = resolver_responder(settings.skills_dir, RETRY)
    for _ in range(2):
        set_status(settings, "shop", "TKT-1", "blocked")
        assert _flow(client)["reason"] == "resolved"
    set_status(settings, "shop", "TKT-1", "blocked")


def _limit_escalated(client: TestClient, tmp_path: Path, settings: Settings, llm: FakeLlm) -> None:
    _two_resolves(client, tmp_path, settings, llm)
    body = client.post(STEP).json()
    assert body["reason"] == "needs_human"


def test_ft_10_1_resolve_limit_escalates(
    client: TestClient, tmp_path: Path, settings: Settings, llm: FakeLlm, host: FakeHost
) -> None:
    """FT-10.1 a third blocked incident after two resolver attempts goes to a human without a resolver run."""
    _two_resolves(client, tmp_path, settings, llm)
    body = client.post(STEP).json()
    incidents = client.get(INCIDENTS).json()
    issue = _tkt1_issue(host)
    assert body["reason"] == "needs_human"
    assert body["run"] is None
    assert incidents[2]["status"] == "needs_human"
    assert incidents[2]["trigger"] == "blocked"
    assert LABEL in issue.labels
    assert len(issue.comments) == 1
    assert issue.comments[0].mine is True


def test_ft_10_2_escalation_comments_on_issue(
    client: TestClient, tmp_path: Path, settings: Settings, llm: FakeLlm, host: FakeHost
) -> None:
    """FT-10.2 an escalate action labels the issue and comments the question; the next ticket is planned."""
    body = _escalated(client, tmp_path, settings, llm)
    issue = _tkt1_issue(host)
    assert body["reason"] == "needs_human"
    assert any("Should totals include tax?" in comment.body for comment in issue.comments)
    assert LABEL in issue.labels
    nxt = client.post(STEP).json()
    assert nxt["run"]["ticket"] == "TKT-3"


def test_ft_10_3_reply_resumes_resolver(
    client: TestClient, tmp_path: Path, settings: Settings, llm: FakeLlm, host: FakeHost
) -> None:
    """FT-10.3 a human reply on the issue is picked up by poll and starts a resolver run with the reply."""
    _escalated(client, tmp_path, settings, llm)
    host.reply(_tkt1_number(host), "Yes, 21% VAT")
    assert client.post(POLL).status_code == 200
    body = client.post(STEP).json()
    assert body["reason"] == "resolving"
    assert body["run"]["agent"] == "resolver"
    bundle = (settings.workspaces_dir / "shop" / "work/cart/incidents/TKT-1-2.md").read_text()
    assert "Yes, 21% VAT" in bundle
    incidents = client.get(INCIDENTS).json()
    assert incidents[0]["status"] == "resolved"
    assert incidents[1]["human_input"] is True


def test_ft_10_4_inbox_continue_resumes_resolver(
    client: TestClient, tmp_path: Path, settings: Settings, llm: FakeLlm, host: FakeHost
) -> None:
    """FT-10.4 an escalation is listed in the inbox; Continue with a response resumes the ticket."""
    _limit_escalated(client, tmp_path, settings, llm)
    item = _escalation_item(client)
    assert item["ticket"] == "TKT-1"
    assert item["link"] == f"https://host.example/issues/{_tkt1_number(host)}"
    r = client.post(f"{INBOX}/{item['id']}/continue", json={"response": "Yes, 21% VAT"})
    assert r.status_code == 200
    assert r.json()["reason"] == "resolving"
    assert r.json()["run"]["agent"] == "resolver"
    issue = _tkt1_issue(host)
    assert any(comment.mine and "Yes, 21% VAT" in comment.body for comment in issue.comments)
    bundle = (settings.workspaces_dir / "shop" / "work/cart/incidents/TKT-1-4.md").read_text()
    assert "Yes, 21% VAT" in bundle
    assert not any(entry["kind"] == "escalation" for entry in client.get(INBOX).json())


def test_ft_10_5_comment_failure_keeps_incident_open(
    client: TestClient, tmp_path: Path, settings: Settings, llm: FakeLlm, host: FakeHost
) -> None:
    """FT-10.5 a host failure while commenting returns 502 and keeps the incident open; retry escalates."""
    add_cart_project(client, tmp_path)
    set_status(settings, "shop", "TKT-1", "blocked")
    llm.responder = resolver_responder(settings.skills_dir, ESCALATE)
    first = client.post(STEP)
    wait_run(client, first.json()["run"]["id"])
    host.fail_next.add("comment_issue")
    failed = client.post(STEP)
    assert failed.status_code == 502
    assert "host_error" in failed.text
    assert client.get(INCIDENTS).json()[0]["status"] == "open"
    assert client.post(STEP).json()["reason"] == "needs_human"


def test_ft_10_6_one_prior_resolve_is_under_limit(
    client: TestClient, tmp_path: Path, settings: Settings, llm: FakeLlm
) -> None:
    """FT-10.6 one earlier resolver attempt does not reach the limit, so the ticket is resolved again."""
    add_cart_project(client, tmp_path)
    llm.responder = resolver_responder(settings.skills_dir, RETRY)
    set_status(settings, "shop", "TKT-1", "blocked")
    assert _flow(client)["reason"] == "resolved"
    set_status(settings, "shop", "TKT-1", "blocked")
    assert client.post(STEP).json()["reason"] == "resolving"


def test_ft_10_7_reply_is_applied_once(
    client: TestClient, tmp_path: Path, settings: Settings, llm: FakeLlm, host: FakeHost
) -> None:
    """FT-10.7 polling again and stepping again does not create a second human-reply incident."""
    _escalated(client, tmp_path, settings, llm)
    host.reply(_tkt1_number(host), "Yes, 21% VAT")
    client.post(POLL)
    client.post(STEP)
    assert client.post(POLL).status_code == 200
    client.post(STEP)
    incidents = client.get(INCIDENTS).json()
    assert sum(1 for incident in incidents if incident["human_input"]) == 1


def test_ft_10_8_own_comment_is_not_a_reply(
    client: TestClient, tmp_path: Path, settings: Settings, llm: FakeLlm
) -> None:
    """FT-10.8 Limo's own escalation comment is never read as a human reply."""
    _escalated(client, tmp_path, settings, llm)
    before = len(client.get(INCIDENTS).json())
    assert client.post(POLL).status_code == 200
    body = client.post(STEP).json()
    assert len(client.get(INCIDENTS).json()) == before
    assert body["reason"] != "resolving"


def test_ft_10_9_continue_validates_response(
    client: TestClient, tmp_path: Path, settings: Settings, llm: FakeLlm
) -> None:
    """FT-10.9 Continue on an escalation needs a non-empty response."""
    _limit_escalated(client, tmp_path, settings, llm)
    item = _escalation_item(client)
    missing = client.post(f"{INBOX}/{item['id']}/continue", json={})
    empty = client.post(f"{INBOX}/{item['id']}/continue", json={"response": ""})
    assert missing.status_code == 422
    assert missing.json()["error"]["code"] == "response_required"
    assert empty.status_code == 422
    assert empty.json()["error"]["code"] == "validation_error"


def test_ft_10_10_continue_unknown_item(client: TestClient) -> None:
    """FT-10.10 Continue on an unknown inbox id returns 404 hold_not_found."""
    r = client.post(f"{INBOX}/nope/continue", json={"response": "x"})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "hold_not_found"


def test_ft_10_11_continue_twice_conflicts(
    client: TestClient, tmp_path: Path, settings: Settings, llm: FakeLlm
) -> None:
    """FT-10.11 a second Continue on the same escalation returns 409 hold_cleared."""
    _limit_escalated(client, tmp_path, settings, llm)
    item = _escalation_item(client)
    first = client.post(f"{INBOX}/{item['id']}/continue", json={"response": "Yes, 21% VAT"})
    assert first.status_code == 200
    again = client.post(f"{INBOX}/{item['id']}/continue", json={"response": "Yes, 21% VAT"})
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "hold_cleared"


def test_ft_10_12_comment_failure_keeps_escalation(
    client: TestClient, tmp_path: Path, settings: Settings, llm: FakeLlm, host: FakeHost
) -> None:
    """FT-10.12 a host failure while posting the response returns 502 and the escalation stays listed."""
    _limit_escalated(client, tmp_path, settings, llm)
    item = _escalation_item(client)
    host.fail_next.add("comment_issue")
    r = client.post(f"{INBOX}/{item['id']}/continue", json={"response": "x"})
    assert r.status_code == 502
    assert r.json()["error"]["code"] == "host_error"
    assert any(entry["kind"] == "escalation" for entry in client.get(INBOX).json())


def test_ft_10_13_poll_host_failure(
    client: TestClient, tmp_path: Path, settings: Settings, llm: FakeLlm, host: FakeHost
) -> None:
    """FT-10.13 a host failure while reading comments returns 502 host_error from poll."""
    _escalated(client, tmp_path, settings, llm)
    host.fail_next.add("issue_comments")
    r = client.post(POLL)
    assert r.status_code == 502
    assert r.json()["error"]["code"] == "host_error"


def test_ft_10_14_inbox_empty_on_fresh_app(client: TestClient) -> None:
    """FT-10.14 a fresh workspace has an empty inbox."""
    assert client.get(INBOX).json() == []
