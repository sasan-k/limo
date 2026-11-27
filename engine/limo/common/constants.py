AGENT_NAMES: tuple[str, ...] = ("architecture", "spec", "plan", "build", "verify", "close", "resolver")
EVENT_TYPES: tuple[str, ...] = (
    "run.started",
    "run.updated",
    "run.finished",
    "ticket.changed",
    "incident.opened",
    "cost.updated",
    "prompt.saved",
)
TICKET_STATUSES: tuple[str, ...] = (
    "todo",
    "planned",
    "built",
    "verified",
    "review",
    "done",
    "blocked",
    "abandoned",
)
