import re
from pathlib import Path

from limo.agents.models import Run
from limo.runner.tickets import TicketState

QUESTION_HEAD = re.compile(r"^## (Q-\d+) \[open\]")
TICKET_ID = re.compile(r"TKT-\d+")


def blocking_questions(workspace: Path, feature: str) -> dict[str, str]:
    path = workspace / "work" / feature / "questions.md"
    if not path.is_file():
        return {}
    result: dict[str, str] = {}
    current: str | None = None
    for line in path.read_text().splitlines():
        if line.startswith("## "):
            head = QUESTION_HEAD.match(line)
            current = head.group(1) if head else None
        elif current is not None and line.startswith("- blocks:"):
            for ticket in TICKET_ID.findall(line):
                result[ticket] = current
    return result


def trigger_for(
    state: TicketState, latest: Run | None, questions: dict[str, str]
) -> tuple[str, str | None] | None:
    if state.id in questions:
        return ("question", None)
    if state.status == "blocked":
        return ("blocked", None)
    if latest is not None and latest.status == "failed":
        error = latest.error or ""
        if error == "timeout":
            return ("timeout", latest.id)
        if not error.startswith("budget:"):
            return ("crash", latest.id)
    if latest is not None and latest.status == "succeeded" and latest.ticket_status == state.status:
        return ("no-transition", latest.id)
    return None


def write_bundle(workspace: Path, feature: str, ticket: str, k: int, lines: list[str]) -> None:
    path = workspace / "work" / feature / "incidents" / f"{ticket}-{k}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")
