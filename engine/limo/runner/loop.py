import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from limo.features.repo import FeatureRepo
from limo.projects.models import Project
from limo.projects.repo import ProjectRepo
from limo.runner.service import RunnerService

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class LoopConfig:
    tick_s: float
    host_poll_s: float


class RunnerLoop:
    """Runner switch (REQ-46): while on, steps every feature of every project each tick. Starts off;
    turning off stops new steps and lets the active run finish."""

    def __init__(
        self, runner: RunnerService, projects: ProjectRepo, features: FeatureRepo, config: LoopConfig
    ) -> None:
        self._runner = runner
        self._projects = projects
        self._features = features
        self._config = config
        self._enabled = False
        self._wake = threading.Event()
        self._stopping = threading.Event()
        self._last_poll: dict[str, float] = {}
        self._thread: threading.Thread | None = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool) -> bool:
        self._enabled = enabled
        if enabled:
            self._wake.set()
        return self._enabled

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="limo-runner", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stopping.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout=10)

    def _loop(self) -> None:
        while not self._stopping.is_set():
            self._wake.wait(self._config.tick_s)
            self._wake.clear()
            if self._enabled and not self._stopping.is_set():
                self._tick()

    def _tick(self) -> None:
        for project in self._projects.list_all():
            for feature in self._feature_names(project):
                if not self._enabled or self._stopping.is_set():
                    return
                self._advance(project.name, feature)

    def _advance(self, project: str, feature: str) -> None:
        name = f"{project}/{feature}"
        if self._poll_due(name):
            _guarded(lambda: self._runner.poll(project, feature), f"poll {name}")
        _guarded(lambda: self._runner.step(project, feature), f"step {name}")

    def _poll_due(self, name: str) -> bool:
        now = time.monotonic()
        last = self._last_poll.get(name)
        if last is not None and now - last < self._config.host_poll_s:
            return False
        self._last_poll[name] = now
        return True

    def _feature_names(self, project: Project) -> list[str]:
        mapped = {p.parent.name for p in (Path(project.workspace) / "work").glob("*/map.yaml")}
        intake = {f.name for f in self._features.list(project.id)}
        return sorted(mapped | intake)


def _guarded(action: Callable[[], object], what: str) -> None:
    """Runner top-level guard: one feature's failure must not stop the loop."""
    try:
        action()
    except Exception:
        log.exception("runner %s failed", what)
