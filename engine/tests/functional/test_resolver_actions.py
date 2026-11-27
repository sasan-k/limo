import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from limo.config import Settings
from limo.llm.ports import LlmError
from tests.builders import add_cart_project, fx_env, get_status, set_status, wait_run, write_workspace_file
from tests.fakes.host import FakeHost
from tests.fakes.llm import FakeLlm, resolver_responder

STEP = "/api/projects/shop/features/cart/step"
INCIDENTS = "/api/projects/shop/features/cart/incidents"
LABEL = "factory:needs-human"
QUESTION = "## Q-3 [open] Which currency?\n- blocks: TKT-1\n- answer:\n"


def _answer(action: dict[str, Any]) -> str:
    return f"```json\n{json.dumps(action)}\n```"


def _block_with(
    client: TestClient, tmp_path: Path, settings: Settings, llm: FakeLlm, action: dict[str, Any]
) -> None:
    add_cart_project(client, tmp_path)
    set_status(settings, "shop", "TKT-1", "blocked")
    llm.responder = resolver_responder(settings.skills_dir, _answer(action))


def _flow(client: TestClient) -> dict[str, Any]:
    first = client.post(STEP)
    assert first.status_code == 200
    assert first.json()["reason"] == "resolving"
    wait_run(client, first.json()["run"]["id"])
    second = client.post(STEP)
    assert second.status_code == 200
    return second.json()


def _ticket_line(settings: Settings) -> str:
    out = subprocess.run(
        ["fx", "tickets", "work/cart"],
        cwd=settings.workspaces_dir / "shop",
        env=fx_env(settings, "shop"),
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return out.splitlines()[0]


def _tkt1_issue(host: FakeHost) -> Any:
    return next(issue for issue in host.issues.values() if issue.title.startswith("TKT-1:"))


def test_ft_19_1_answer_marks_question_answered(
    client: TestClient, tmp_path: Path, settings: Settings, llm: FakeLlm
) -> None:
    """FT-19.1 an answer action marks the open question answered and sends its ticket back to todo."""
    add_cart_project(client, tmp_path)
    write_workspace_file(settings, "shop", "work/cart/questions.md", QUESTION)
    llm.responder = resolver_responder(
        settings.skills_dir,
        _answer({"type": "answer", "question": "Q-3", "answer": "use EUR", "source": "context/data.md:12"}),
    )
    body = _flow(client)
    text = (settings.workspaces_dir / "shop" / "work/cart/questions.md").read_text()
    assert body["reason"] == "resolved"
    assert "## Q-3 [answered]" in text
    assert "- answer: use EUR (source: context/data.md:12)" in text
    assert get_status(settings, "shop", "TKT-1") == "todo"


def test_ft_19_2_edit_ticket_retitles(
    client: TestClient, tmp_path: Path, settings: Settings, llm: FakeLlm, host: FakeHost
) -> None:
    """FT-19.2 an edit-ticket action retitles the ticket in the map and its issue; it is planned again."""
    _block_with(
        client,
        tmp_path,
        settings,
        llm,
        {"type": "edit-ticket", "title": "Cart total includes tax", "source": "x"},
    )
    body = _flow(client)
    nxt = client.post(STEP).json()
    assert body["reason"] == "resolved"
    assert _ticket_line(settings) == "TKT-1\tCart total includes tax"
    assert _tkt1_issue(host).title == "TKT-1: Cart total includes tax"
    assert nxt["run"]["agent"] == "plan"
    assert nxt["run"]["ticket"] == "TKT-1"


def test_ft_19_3_invalid_action_escalates(
    client: TestClient, tmp_path: Path, settings: Settings, llm: FakeLlm, host: FakeHost
) -> None:
    """FT-19.3 an action type outside the allowlist escalates to a human."""
    _block_with(client, tmp_path, settings, llm, {"type": "merge"})
    body = _flow(client)
    assert body["reason"] == "needs_human"
    assert LABEL in _tkt1_issue(host).labels


def test_ft_19_4_replan_note_reaches_next_plan(
    client: TestClient, tmp_path: Path, settings: Settings, llm: FakeLlm, host: FakeHost
) -> None:
    """FT-19.4 a replan action gives the next plan run a note; a second replan escalates."""
    fix = "define IssueRef before the fake host step"
    _block_with(client, tmp_path, settings, llm, {"type": "replan", "fix": fix, "source": "x"})
    body = _flow(client)
    assert body["reason"] == "resolved"
    assert get_status(settings, "shop", "TKT-1") == "todo"
    plan = client.post(STEP).json()
    assert plan["run"]["agent"] == "plan"
    wait_run(client, plan["run"]["id"])
    notes = [r for r in llm.requests if f"note: {fix}" in r.messages[0]["content"]]
    assert notes
    assert (settings.workspaces_dir / "shop" / "work/cart/reports/TKT-1-replan-1.md").exists()
    set_status(settings, "shop", "TKT-1", "blocked")
    again = _flow(client)
    assert again["reason"] == "needs_human"
    assert LABEL in _tkt1_issue(host).labels


@pytest.mark.parametrize(
    "action",
    [
        {"type": "answer", "question": "Q-9", "answer": "x", "source": "y"},
        {"type": "answer", "question": "Q-3", "answer": "", "source": "y"},
    ],
)
def test_ft_19_5_bad_answer_escalates(
    action: dict[str, Any], client: TestClient, tmp_path: Path, settings: Settings, llm: FakeLlm
) -> None:
    """FT-19.5 an answer for an unknown question or with an empty answer escalates."""
    _block_with(client, tmp_path, settings, llm, action)
    write_workspace_file(settings, "shop", "work/cart/questions.md", QUESTION)
    body = _flow(client)
    assert body["reason"] == "needs_human"


@pytest.mark.parametrize("title", ["", "a" * 121, "two\nlines"])
def test_ft_19_6_bad_title_escalates(
    title: str, client: TestClient, tmp_path: Path, settings: Settings, llm: FakeLlm
) -> None:
    """FT-19.6 an edit-ticket title that is empty, too long or multi-line escalates and keeps the title."""
    _block_with(client, tmp_path, settings, llm, {"type": "edit-ticket", "title": title, "source": "x"})
    body = _flow(client)
    assert body["reason"] == "needs_human"
    assert _ticket_line(settings) == "TKT-1\tCart shows a total"


def test_ft_19_7_host_failure_keeps_incident_open(
    client: TestClient, tmp_path: Path, settings: Settings, llm: FakeLlm, host: FakeHost
) -> None:
    """FT-19.7 a host failure while retitling returns 502 host_error; the next step applies the action."""
    _block_with(
        client,
        tmp_path,
        settings,
        llm,
        {"type": "edit-ticket", "title": "Cart total includes tax", "source": "x"},
    )
    first = client.post(STEP)
    wait_run(client, first.json()["run"]["id"])
    host.fail_next.add("set_issue_title")
    failed = client.post(STEP)
    incidents = client.get(INCIDENTS).json()
    assert failed.status_code == 502
    assert "host_error" in failed.text
    assert incidents[0]["status"] == "open"
    assert client.post(STEP).json()["reason"] == "resolved"


@pytest.mark.parametrize("case", ["retry", "run_failed"])
def test_ft_19_8_resolve_report_written(
    case: str, client: TestClient, tmp_path: Path, settings: Settings, llm: FakeLlm
) -> None:
    """FT-19.8 every applied incident writes its resolve report: the resolver output, or the failure."""
    add_cart_project(client, tmp_path)
    set_status(settings, "shop", "TKT-1", "blocked")
    if case == "retry":
        llm.responder = resolver_responder(settings.skills_dir, _answer({"type": "retry", "stage": "build"}))
    else:
        llm.fail_with = LlmError("down")
    _flow(client)
    report = (settings.workspaces_dir / "shop" / "work/cart/reports/TKT-1-resolve-1.md").read_text()
    if case == "retry":
        assert "retry" in report
    else:
        assert "resolver run failed" in report


def test_ft_19_9_escalate_action_needs_human(
    client: TestClient, tmp_path: Path, settings: Settings, llm: FakeLlm, host: FakeHost
) -> None:
    """FT-19.9 an explicit escalate action sends the ticket to a human with the needs-human label."""
    _block_with(
        client,
        tmp_path,
        settings,
        llm,
        {"type": "escalate", "summary": "s", "ask": "Should totals include tax?"},
    )
    body = _flow(client)
    assert body["reason"] == "needs_human"
    assert LABEL in _tkt1_issue(host).labels


def test_ft_19_10_answer_to_closed_question_escalates(
    client: TestClient, tmp_path: Path, settings: Settings, llm: FakeLlm
) -> None:
    """FT-19.10 an answer for a question that is not open escalates."""
    _block_with(
        client,
        tmp_path,
        settings,
        llm,
        {"type": "answer", "question": "Q-3", "answer": "EUR", "source": "y"},
    )
    closed = "## Q-3 [answered] Which currency?\n- blocks: TKT-1\n- answer: EUR\n"
    write_workspace_file(settings, "shop", "work/cart/questions.md", closed)
    body = _flow(client)
    assert body["reason"] == "needs_human"


def test_ft_19_11_label_failure_keeps_incident_open(
    client: TestClient, tmp_path: Path, settings: Settings, llm: FakeLlm, host: FakeHost
) -> None:
    """FT-19.11 a host failure while adding the label returns 502, then the escalation completes."""
    _block_with(client, tmp_path, settings, llm, {"type": "merge"})
    first = client.post(STEP)
    wait_run(client, first.json()["run"]["id"])
    host.fail_next.add("add_issue_label")
    failed = client.post(STEP)
    assert failed.status_code == 502
    assert "host_error" in failed.text
    assert client.post(STEP).json()["reason"] == "needs_human"
    assert LABEL in _tkt1_issue(host).labels


def test_ft_19_12_note_consumed_once(
    client: TestClient, tmp_path: Path, settings: Settings, llm: FakeLlm
) -> None:
    """FT-19.12 the replan note is passed to one plan run only."""
    fix = "define IssueRef before the fake host step"
    _block_with(client, tmp_path, settings, llm, {"type": "replan", "fix": fix, "source": "x"})
    _flow(client)
    plan = client.post(STEP).json()
    wait_run(client, plan["run"]["id"])
    llm.responder = None
    again = client.post(STEP).json()
    if again["run"] is not None:
        wait_run(client, again["run"]["id"])
    notes = [r for r in llm.requests if f"note: {fix}" in r.messages[0]["content"]]
    assert len(notes) == 1


YAML_REPLAN = """## Reasoning
- the plan writes ranges inside the backticks

```action
action: replan
fix: |
  In `## Context pack`, put line ranges after the closing backtick.
  Write builders.py as one span.
source: engine/limo/agents/context_pack.py:3; plans/TKT-20.md:82-85
```
"""


def test_action_block_in_yaml_form_is_applied(
    client: TestClient, tmp_path: Path, settings: Settings, llm: FakeLlm
) -> None:
    """A resolver answer written as an ```action block with `action:` and `key: |` lines is applied
    like the JSON form (here: replan with a two-line fix)."""
    add_cart_project(client, tmp_path)
    set_status(settings, "shop", "TKT-1", "blocked")
    llm.responder = resolver_responder(settings.skills_dir, YAML_REPLAN)
    assert _flow(client)["reason"] == "resolved"
    assert get_status(settings, "shop", "TKT-1") == "todo"
    plan = client.post(STEP).json()
    wait_run(client, plan["run"]["id"])
    note = (
        "note: In `## Context pack`, put line ranges after the closing backtick.\n"
        "Write builders.py as one span."
    )
    assert any(note in r.messages[0]["content"] for r in llm.requests)
