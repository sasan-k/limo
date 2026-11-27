import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from limo.common.errors import Conflict, ExternalError
from limo.hosts.issue_repo import IssueRepo
from limo.hosts.ports import HostError, HostProject, RepoHost
from limo.incidents.actions import RETRY_STATUS
from limo.incidents.models import IncidentRow
from limo.incidents.repo import IncidentRepo
from limo.projects.models import Project
from limo.runner.tickets import TicketBoard, TicketRef

NEEDS_HUMAN_LABEL = "factory:needs-human"
QUESTION_ID = re.compile(r"^Q-\d+$")


@dataclass(frozen=True)
class ApplyContext:
    project: Project
    feature: str
    incident: IncidentRow


def _line(value: Any, limit: int) -> bool:
    return isinstance(value, str) and 1 <= len(value) <= limit and "\n" not in value


class ActionApplier:
    def __init__(self, board: TicketBoard, host: RepoHost, issues: IssueRepo, repo: IncidentRepo) -> None:
        self._board = board
        self._host = host
        self._issues = issues
        self._repo = repo

    def apply(self, ctx: ApplyContext, action: dict[str, Any] | None) -> Literal["resolved", "needs_human"]:
        try:
            if self._handle(ctx, action):
                return "resolved"
            self._escalate(ctx)
            return "needs_human"
        except HostError as e:
            raise ExternalError("host_error", "repo host call failed") from e

    def _handle(self, ctx: ApplyContext, action: dict[str, Any] | None) -> bool:
        if action is None:
            return False
        handlers = {
            "retry": self._retry,
            "answer": self._answer,
            "edit-ticket": self._edit_ticket,
            "replan": self._replan,
        }
        kind = action.get("type")
        handler = handlers.get(kind) if isinstance(kind, str) else None
        return handler is not None and handler(ctx, action)

    def _ref(self, ctx: ApplyContext) -> TicketRef:
        return TicketRef(Path(ctx.project.workspace), ctx.project.name, ctx.feature, ctx.incident.ticket)

    def _host_project(self, ctx: ApplyContext) -> HostProject:
        return HostProject(name=ctx.project.name, git_url=ctx.project.git_url, kind=ctx.project.host)

    def _retry(self, ctx: ApplyContext, action: dict[str, Any]) -> bool:
        stage = action.get("stage")
        if not isinstance(stage, str) or stage not in RETRY_STATUS:
            return False
        self._board.set_status(self._ref(ctx), RETRY_STATUS[stage])
        return True

    def _answer(self, ctx: ApplyContext, action: dict[str, Any]) -> bool:
        question, answer, source = action.get("question"), action.get("answer"), action.get("source")
        if not (isinstance(question, str) and QUESTION_ID.match(question)):
            return False
        if not (_line(answer, 500) and _line(source, 500)):
            return False
        path = Path(ctx.project.workspace) / "work" / ctx.feature / "questions.md"
        if not path.is_file():
            return False
        lines = path.read_text().splitlines(keepends=True)
        head = next((i for i, line in enumerate(lines) if line.startswith(f"## {question} [open]")), None)
        if head is None:
            return False
        end = next((j for j in range(head + 1, len(lines)) if lines[j].startswith("## ")), len(lines))
        lines[head] = lines[head].replace(f"## {question} [open]", f"## {question} [answered]", 1)
        text = f"- answer: {answer} (source: {source})\n"
        found = next((j for j in range(head + 1, end) if lines[j].startswith("- answer:")), None)
        if found is not None:
            lines[found] = text
        else:
            last = max(j for j in range(head, end) if lines[j].strip())
            lines.insert(last + 1, text)
        path.write_text("".join(lines))
        return True

    def _edit_ticket(self, ctx: ApplyContext, action: dict[str, Any]) -> bool:
        title = action.get("title")
        if not isinstance(title, str) or not _line(title, 120):
            return False
        ref = self._ref(ctx)
        try:
            self._board.retitle(ref, title)
        except Conflict:
            return False
        issue = self._issues.for_feature(ctx.project.id, ctx.feature).get(ctx.incident.ticket)
        if issue is not None:
            self._host.set_issue_title(
                self._host_project(ctx), issue.number, f"{ctx.incident.ticket}: {title}"
            )
        self._board.set_status(ref, "todo")
        return True

    def _replan(self, ctx: ApplyContext, action: dict[str, Any]) -> bool:
        fix = action.get("fix")
        if not _line(fix, 500) or self._has_replan(ctx):
            return False
        report = (
            Path(ctx.project.workspace)
            / "work"
            / ctx.feature
            / "reports"
            / f"{ctx.incident.ticket}-replan-{ctx.incident.k}.md"
        )
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(f"{fix}\n")
        self._repo.set_note_pending(ctx.incident.id, True)
        self._board.set_status(self._ref(ctx), "todo")
        return True

    def _has_replan(self, ctx: ApplyContext) -> bool:
        actions = self._repo.actions_for(ctx.project.id, ctx.feature, ctx.incident.ticket)
        return any(json.loads(text).get("type") == "replan" for text in actions)

    def _escalate(self, ctx: ApplyContext) -> None:
        issue = self._issues.for_feature(ctx.project.id, ctx.feature).get(ctx.incident.ticket)
        if issue is not None:
            self._host.add_issue_label(self._host_project(ctx), issue.number, NEEDS_HUMAN_LABEL)
