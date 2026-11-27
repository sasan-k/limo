import json
import queue
import threading
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime

from limo.common.constants import EVENT_TYPES

MAX_QUEUED = 1000


@dataclass(frozen=True)
class Event:
    type: str
    at: str
    project_id: str | None
    payload: dict[str, object]

    def to_sse(self) -> str:
        data = {"type": self.type, "at": self.at, "project_id": self.project_id, "payload": self.payload}
        return f"event: {self.type}\ndata: {json.dumps(data)}\n\n"


class EventBus:
    """In-process fan-out of change events to SSE subscribers; publish is safe from any thread."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: list[queue.Queue[Event]] = []

    def subscribe(self) -> queue.Queue[Event]:
        sub: queue.Queue[Event] = queue.Queue(maxsize=MAX_QUEUED)
        with self._lock:
            self._subscribers.append(sub)
        return sub

    def unsubscribe(self, sub: queue.Queue[Event]) -> None:
        with self._lock:
            if sub in self._subscribers:
                self._subscribers.remove(sub)

    def publish(self, event_type: str, project_id: str | None, payload: dict[str, object]) -> None:
        if event_type not in EVENT_TYPES:
            raise ValueError(f"unknown event type {event_type}")
        event = Event(event_type, datetime.now(UTC).isoformat(), project_id, payload)
        with self._lock:
            subscribers = list(self._subscribers)
        for sub in subscribers:
            with suppress(queue.Full):  # slow client drops hints; REST stays the truth (ADR-2)
                sub.put_nowait(event)
