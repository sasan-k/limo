---
ticket: TKT-16
feature: limo
scenarios: [SC-50, SC-51, SC-52]
scope: [runner, api, ui]
revision: 0
run: all
read: [work/limo/map.yaml, work/limo/features/runner.feature#SC-50..52, work/limo/reqs.md#REQ-46, DESIGN.md (Runner switch, Scheduler), context/INDEX.md, context/code-rules.md, context/security.md, context/performance.md, context/testing.md, context/api.md, context/glossary.md, context/adr/ADR-11.md, engine/limo/runner/service.py, engine/limo/runner/models.py, engine/limo/features/repo.py, engine/limo/projects/repo.py, engine/limo/app.py, engine/limo/config.py, engine/tests/builders.py, engine/tests/fakes/llm.py, ui/src/App.tsx, ui/tests/harness.tsx]
---
# TKT-16: A runner switch in the UI turns the runner on and off, starting off

## Design
- where: new `runner/loop.py` (`RunnerLoop`, the in-process loop of ADR-11), `api/switch_routes.py`; `runner/models.py` (switch models), `runner/service.py` (re-entrant lock around `step`/`poll`), `config.py` (`runner_tick_s`, `host_poll_s`), `app.py` (loop started/stopped in the lifespan); UI `RunnerSwitch` in the header.
- responsibilities:
  - `RunnerLoop` — holds the switch (in memory, starts off); a daemon thread wakes every `runner_tick_s` (or at once when turned on) and, while on, calls `runner.poll` (at most every `host_poll_s` per feature) and `runner.step` for every feature of every project (features = `work/*/map.yaml` dirs ∪ intake features); a failure in one feature is logged and the loop goes on
  - `RunnerService` — `step`/`poll` serialized by an `RLock` so loop and HTTP callers never dispatch twice
  - `switch_router` — `GET/PUT /api/runner`
  - UI `RunnerSwitch` — `Runner off`/`Runner on` button (`aria-pressed`) next to the theme toggle
- reuse: `RunnerService.step` / `poll` (dispatch, one-run limit `max_concurrent_tickets`, ADR-11); `ProjectRepo.list_all`; `FeatureRepo.list`; UI `getJson`/`putJson`, `Button`, Vitest `serveApi`. Searched `limo/runner`, `limo/api` for an existing loop/switch: none (steps only via `POST …/step`).
- contracts:
  - `GET /api/runner` → `{"enabled": bool}` (false after every engine start, SC-50)
  - `PUT /api/runner` body `{"enabled": StrictBool}` (extra forbid) → `{"enabled": bool}`; 422 `validation_error` otherwise; turning on wakes the loop at once; turning off stops new steps, the active run finishes (SC-52); repeating a value is a no-op
  - UI query key `["runner"]`, set from the PUT response
- data: none (switch is in memory by design: "starts off")
- decisions: follows ADR-11 (loop calls the runner; concurrency still only from `max_concurrent_tickets`; run state stays in the db), DESIGN.md › Runner switch. Polling every `host_poll_s` = 180 s (performance.md › polling). No new ADR, no dependency.

## Quality
### Security
- authn: n/a: ADR-7, 127.0.0.1 only
- authz (permission/ownership): n/a: single local user (ADR-7)
- input validation: `RunnerSwitchIn` with `StrictBool`, `extra="forbid"`
- injection: n/a: no strings used
- data exposure / PII: only a boolean
- secrets: none
- rate limit / abuse: one loop thread; steps limited by `max_concurrent_tickets`; host polls throttled per feature (`host_poll_s`)
- audit: runs started by the loop are recorded as runs (unchanged)
### Performance
- queries (N+1, indexes): per tick one project list + one feature list per project; `step` unchanged
- pagination / limits: n/a: projects/features are few
- payload size: tiny
- caching: none
- external calls (timeouts/retries): host polls at most every 180 s per feature (performance.md); existing adapter timeouts
- sync vs async: loop in its own daemon thread; runs stay in the run worker (performance.md › Async); HTTP handlers only flip the switch
- NFR targets: NFR-11 → concurrency still from `max_concurrent_tickets` only (FT-16.4 one run); NFR-10 → FT-16.10 (axe both modes)

## Operation matrix
| Op | happy | validation | not-found | conflict | invalid-state | idempotency | boundary | external-failure |
|---|---|---|---|---|---|---|---|---|
| OP-1 switch `GET/PUT /api/runner` | FT-16.1, FT-16.2 | FT-16.5 | n/a: single resource | n/a: last write wins | FT-16.3 | FT-16.4 | FT-16.1 | n/a: no external call |
| OP-2 runner loop `engine/limo/runner/loop.py` | FT-16.2, FT-16.3 | n/a: no input | n/a: iterates existing projects | FT-16.4 | FT-16.6 | FT-16.4 | FT-16.1 | FT-16.6 |
| OP-3 switch button `ui/src/components/RunnerSwitch.tsx` | FT-16.8 | n/a: boolean toggle | n/a: single resource | n/a: last write wins | n/a: any state | n/a: disabled while pending | FT-16.10 | FT-16.9 |

## Functional tests
| FT | Covers | File | Given (via production action) | When | Then (observable) |
|---|---|---|---|---|---|
| FT-16.1 | SC-50, OP-1:happy, OP-1:boundary, OP-2:boundary | `engine/tests/functional/test_runner_switch.py` | own app (`create_app(settings, deps)`), `add_cart_project` (TKT-1 todo); switch on then off; app closed; second app on the same settings (restart) | `GET /api/runner`; wait 0.5 s | `{"enabled": false}` on both starts; no Claude request after the restart; no card active |
| FT-16.2 | SC-51, OP-1:happy, OP-2:happy | same | `add_cart_project`; slow fake (1 s per request); 0.2 s idle → plan card `last_run` null | `PUT /api/runner {"enabled": true}` | within 5 s plan card `last_run` set, `ticket == "TKT-1"`, `state == "active"` (no step call) |
| FT-16.3 | SC-52, OP-1:invalid-state, OP-2:happy | same | `add_cart_project`; `set_status(TKT-1, planned)`; `blocking_build(skills, 1.0)`; switch on; build card active | `PUT {"enabled": false}` | response `{"enabled": false}`; the build run finishes `succeeded`; 0.5 s later plan card `last_run` null (no run for TKT-3); build `tries == 1` |
| FT-16.4 | OP-1:idempotency, OP-2:conflict, OP-2:idempotency | same | `add_cart_project`; slow fake | `PUT true` twice | second response `{"enabled": true}`; one plan run (`tries == 1`) |
| FT-16.5 | OP-1:validation | same | none | PUT `{"enabled": "yes"}`, `{"enabled": 1}`, `{}`, `{"enabled": true, "force": true}` | each 422 `validation_error`; switch still off |
| FT-16.6 | OP-2:invalid-state, OP-2:external-failure | same | `add_cart_project`; `work/aaa/map.yaml` invalid (sorted before `cart`); slow fake | switch on | plan run starts for feature `cart` (the failing feature is logged and skipped) |
| FT-16.8 | SC-50, SC-51, OP-3:happy | `ui/tests/RunnerSwitch.test.tsx` | `serveApi`: `/api/runner` → off; `PUT /api/runner` → on | click `Runner off` | `aria-pressed` false → button `Runner on` with `aria-pressed` true; PUT body `{enabled: true}` |
| FT-16.9 | OP-3:external-failure | same | PUT → 500 `{"error": {"message": "runner unavailable"}}` | click | message shown; button still `Runner off` |
| FT-16.10 | SC-50, OP-3:boundary | `ui/e2e/runner.spec.ts` | e2e engine just started | per mode light/dark: set `limo-theme`, reload | header button `Runner off` with `aria-pressed="false"`; axe `color-contrast` violations `[]` |

## Context pack
- `engine/limo/config.py` — add settings
- `engine/limo/runner/models.py` — add switch models
- `engine/limo/runner/service.py` — lock around step/poll
- `engine/limo/features/repo.py:48-60` — `FeatureRepo.list` (read)
- `engine/limo/projects/repo.py:44-55` — `ProjectRepo.list_all` (read)
- `engine/limo/app.py` — wiring + lifespan
- `engine/tests/conftest.py`, `engine/tests/builders.py`, `engine/tests/fakes/llm.py`, `engine/tests/fakes/host.py:1-40` — read
- `ui/src/api/types.ts`, `ui/src/App.tsx` — edit
- `ui/tests/harness.tsx` — read
- `ui/e2e/board.spec.ts` — e2e style to imitate

## Steps
### STEP-1 Settings
- file: `engine/limo/config.py` (edit)
- do: after `sse_heartbeat_s` add `runner_tick_s: float = 2.0` and `host_poll_s: float = 180.0`
- verify: `cd engine && uv run python -c "from limo.config import Settings; s = Settings(_env_file=None); print(s.runner_tick_s, s.host_poll_s)"` → `2.0 180.0`

### STEP-2 Switch models
- file: `engine/limo/runner/models.py` (edit)
- do: import line becomes `from pydantic import BaseModel, ConfigDict, StrictBool`; append
```python
class RunnerSwitch(BaseModel):
    enabled: bool


class RunnerSwitchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: StrictBool
```
- verify: `cd engine && uv run mypy` → `Success`

### STEP-3 Engine functional tests
- file: `engine/tests/functional/test_runner_switch.py` (create)
- do: exact contents:
```python
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from limo.app import Deps, create_app
from limo.config import Settings
from limo.executor.local import LocalExecutor
from limo.llm.ports import LlmRequest, LlmResponse
from tests.builders import add_cart_project, set_status, wait_run, write_workspace_file
from tests.fakes.host import FakeHost
from tests.fakes.llm import FakeLlm, blocking_build, final

RUNNER = "/api/runner"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path / "data", anthropic_api_key="sk-canary-123", runner_tick_s=0.05, _env_file=None
    )


def _card(client: TestClient, agent: str) -> dict[str, Any]:
    return next(c for c in client.get("/api/agent-cards").json() if c["agent"] == agent)


def _until(check: Callable[[], bool], timeout_s: float = 5.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(0.02)
    raise AssertionError("condition not met in time")


def _slow(request: LlmRequest) -> LlmResponse:
    time.sleep(1.0)
    return final()


def test_ft_16_1_runner_starts_off_and_starts_nothing(
    settings: Settings, llm: FakeLlm, tmp_path: Path
) -> None:
    """FT-16.1 a fresh engine reports the runner off and starts no run, also after a restart."""
    deps = Deps(LocalExecutor(path_prefix=settings.scripts_dir), llm, FakeHost())
    with TestClient(create_app(settings, deps)) as client:
        add_cart_project(client, tmp_path)
        assert client.get(RUNNER).json() == {"enabled": False}
        assert client.put(RUNNER, json={"enabled": True}).json() == {"enabled": True}
        assert client.put(RUNNER, json={"enabled": False}).json() == {"enabled": False}
    llm.requests.clear()
    with TestClient(create_app(settings, deps)) as client:
        assert client.get(RUNNER).json() == {"enabled": False}
        time.sleep(0.5)
        assert all(
            c["last_run"] is None or c["state"] != "active" for c in client.get("/api/agent-cards").json()
        )
    assert llm.requests == []


def test_ft_16_2_turning_on_starts_a_plan_run(client: TestClient, llm: FakeLlm, tmp_path: Path) -> None:
    """FT-16.2 turning the runner on starts a plan run for TKT-1 without a step call."""
    add_cart_project(client, tmp_path)
    llm.responder = _slow
    time.sleep(0.2)
    assert _card(client, "plan")["last_run"] is None
    assert client.put(RUNNER, json={"enabled": True}).status_code == 200
    _until(lambda: _card(client, "plan")["last_run"] is not None)
    card = _card(client, "plan")
    assert card["ticket"] == "TKT-1"
    assert card["state"] == "active"
    client.put(RUNNER, json={"enabled": False})


def test_ft_16_3_turning_off_lets_the_active_run_finish(
    client: TestClient, llm: FakeLlm, settings: Settings, tmp_path: Path
) -> None:
    """FT-16.3 turning off during a build run lets it finish and starts no plan run for TKT-3."""
    add_cart_project(client, tmp_path)
    set_status(settings, "shop", "TKT-1", "planned")
    llm.responder = blocking_build(settings.skills_dir, 1.0)
    client.put(RUNNER, json={"enabled": True})
    _until(lambda: _card(client, "build")["state"] == "active")
    assert client.put(RUNNER, json={"enabled": False}).json() == {"enabled": False}
    run = wait_run(client, _card(client, "build")["last_run"]["id"])
    assert run["status"] == "succeeded"
    time.sleep(0.5)
    assert _card(client, "plan")["last_run"] is None
    assert _card(client, "build")["last_run"]["tries"] == 1


def test_ft_16_4_turning_on_twice_starts_one_run(client: TestClient, llm: FakeLlm, tmp_path: Path) -> None:
    """FT-16.4 two PUT enabled=true calls give one active plan run."""
    add_cart_project(client, tmp_path)
    llm.responder = _slow
    client.put(RUNNER, json={"enabled": True})
    assert client.put(RUNNER, json={"enabled": True}).json() == {"enabled": True}
    _until(lambda: _card(client, "plan")["last_run"] is not None)
    time.sleep(0.3)
    assert _card(client, "plan")["last_run"]["tries"] == 1
    client.put(RUNNER, json={"enabled": False})


def test_ft_16_5_invalid_switch_bodies_are_rejected(client: TestClient) -> None:
    """FT-16.5 non-boolean, missing and extra fields give 422 validation_error; the switch stays off."""
    for body in ({"enabled": "yes"}, {"enabled": 1}, {}, {"enabled": True, "force": True}):
        r = client.put(RUNNER, json=body)
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "validation_error"
    assert client.get(RUNNER).json() == {"enabled": False}


def test_ft_16_6_a_broken_feature_does_not_stop_the_runner(
    client: TestClient, llm: FakeLlm, settings: Settings, tmp_path: Path
) -> None:
    """FT-16.6 a feature whose map is invalid is skipped; the cart feature still gets its plan run."""
    add_cart_project(client, tmp_path)
    write_workspace_file(
        settings, "shop", "work/aaa/map.yaml", "feature: aaa\ntickets:\n  - id: TKT-1\n    bogus: x\n"
    )
    llm.responder = _slow
    client.put(RUNNER, json={"enabled": True})
    _until(lambda: _card(client, "plan")["last_run"] is not None)
    assert _card(client, "plan")["feature"] == "cart"
    client.put(RUNNER, json={"enabled": False})
```
- verify: `mise run test:engine -- -k ft_16` → `FAIL: 404` on `/api/runner` (FT-16.5 may fail on 404 too)

### STEP-4 Serialize runner steps
- file: `engine/limo/runner/service.py` (edit)
- do: `import threading` (first import); in `__init__` add `self._lock = threading.RLock()` as the last line; rename the body of `step` into a new private `_step(self, project_name: str, feature: str) -> StepResult` (body unchanged) and make `step`
```python
    def step(self, project_name: str, feature: str) -> StepResult:
        """One runner step; serialized so the runner loop and HTTP callers never dispatch twice."""
        with self._lock:
            return self._step(project_name, feature)
```
  same for `poll` → `_poll` with `poll` = `with self._lock: return self._poll(project_name, feature)`. Other methods unchanged (they call `step`, the lock is re-entrant).
- verify: `mise run test:engine -- -k "ft_5 or ft_9 or ft_10"` → all pass

### STEP-5 Runner loop
- file: `engine/limo/runner/loop.py` (create)
- do: exact contents:
```python
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
```
- verify: `cd engine && uv run mypy` → `Success`

### STEP-6 Switch routes
- file: `engine/limo/api/switch_routes.py` (create)
- do: exact contents:
```python
from fastapi import APIRouter

from limo.runner.loop import RunnerLoop
from limo.runner.models import RunnerSwitch, RunnerSwitchIn


def switch_router(loop: RunnerLoop) -> APIRouter:
    router = APIRouter(prefix="/api/runner")

    @router.get("", response_model=RunnerSwitch)
    def get_switch() -> RunnerSwitch:
        return RunnerSwitch(enabled=loop.enabled)

    @router.put("", response_model=RunnerSwitch)
    def set_switch(body: RunnerSwitchIn) -> RunnerSwitch:
        return RunnerSwitch(enabled=loop.set_enabled(body.enabled))

    return router
```
- verify: `cd engine && uv run mypy` → `Success`

### STEP-7 Wiring
- file: `engine/limo/app.py` (edit)
- do: import `switch_router` (`limo.api.switch_routes`) and `LoopConfig, RunnerLoop` (`limo.runner.loop`). After the `runner = RunnerService(...)` block and before `lifespan`:
```python
    loop = RunnerLoop(
        runner,
        ProjectRepo(settings.db_path),
        feature_repo,
        LoopConfig(settings.runner_tick_s, settings.host_poll_s),
    )
```
  `lifespan` becomes: `loop.start()`, `yield`, `loop.stop()`, `runs.close()`. After `app.include_router(runner_router(runner))` add `app.include_router(switch_router(loop))`.
- verify: `mise run test:engine -- -k ft_16` → 6 passed; `mise run test:engine` → all pass; `mise run arch` → kept

### STEP-8 Regenerate API types
- file: `ui/src/api/schema.d.ts` (generated), `ui/src/api/types.ts` (edit)
- do: `mise run gen:api`; in `types.ts` add `export type RunnerSwitch = components["schemas"]["RunnerSwitch"];` before the `Project` line
- verify: `cd ui && npx tsc --noEmit` → no errors

### STEP-9 Switch component tests
- file: `ui/tests/RunnerSwitch.test.tsx` (create)
- do: exact contents:
```tsx
import { fireEvent, screen } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import { renderApp, serveApi } from "./harness";

beforeEach(() => {
  vi.unstubAllGlobals();
  window.matchMedia = vi.fn().mockReturnValue({ matches: false });
});

test("FT-16.8 the switch shows off, and a click turns the runner on", async () => {
  const calls = serveApi({
    current: {
      "/api/runner": { enabled: false },
      "PUT /api/runner": { status: 200, body: { enabled: true } },
    },
  });
  renderApp();
  const button = await screen.findByRole("button", { name: "Runner off" });
  await vi.waitFor(() => expect(button).toBeEnabled());
  expect(button).toHaveAttribute("aria-pressed", "false");
  fireEvent.click(button);
  const on = await screen.findByRole("button", { name: "Runner on" });
  expect(on).toHaveAttribute("aria-pressed", "true");
  expect(calls.find((c) => c.method === "PUT")?.body).toEqual({ enabled: true });
});

test("FT-16.9 a failed switch shows the engine's message and stays off", async () => {
  serveApi({
    current: {
      "/api/runner": { enabled: false },
      "PUT /api/runner": {
        status: 500,
        body: { error: { code: "internal", message: "runner unavailable" } },
      },
    },
  });
  renderApp();
  const button = await screen.findByRole("button", { name: "Runner off" });
  await vi.waitFor(() => expect(button).toBeEnabled());
  fireEvent.click(button);
  expect(await screen.findByText("runner unavailable")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Runner off" })).toBeInTheDocument();
});
```
- verify: `mise run test:ui -- -t "FT-16"` → `FAIL: no button named "Runner off"`

### STEP-10 Switch component in the header
- file: `ui/src/components/RunnerSwitch.tsx` (create), `ui/src/App.tsx` (edit)
- do: `ui/src/components/RunnerSwitch.tsx`:
```tsx
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getJson, putJson } from "@/api/client";
import type { RunnerSwitch as RunnerSwitchState } from "@/api/types";
import { Button } from "@/components/ui/button";

/** Header switch that turns the runner on and off; the engine starts with it off (REQ-46). */
export function RunnerSwitch() {
  const queryClient = useQueryClient();
  const state = useQuery({ queryKey: ["runner"], queryFn: () => getJson<RunnerSwitchState>("/api/runner") });
  const toggle = useMutation({
    mutationFn: (enabled: boolean) => putJson<RunnerSwitchState>("/api/runner", { enabled }),
    onSuccess: (data) => queryClient.setQueryData(["runner"], data),
  });
  const on = state.data?.enabled === true;
  return (
    <div className="flex items-center gap-2">
      {toggle.isError && <span className="text-destructive text-sm">{toggle.error.message}</span>}
      <Button
        variant={on ? "default" : "outline"}
        size="sm"
        aria-pressed={on}
        disabled={!state.isSuccess || toggle.isPending}
        onClick={() => toggle.mutate(!on)}
      >
        Runner {on ? "on" : "off"}
      </Button>
    </div>
  );
}
```
  `ui/src/App.tsx`: import `RunnerSwitch` from `@/components/RunnerSwitch` (before the ThemeToggle import) and replace the header's `<ThemeToggle />` with
```tsx
        <div className="flex items-center gap-2">
          <RunnerSwitch />
          <ThemeToggle />
        </div>
```
- verify: `mise run test:ui` → 20 passed

### STEP-11 E2E switch
- file: `ui/e2e/runner.spec.ts` (create)
- like: `ui/e2e/board.spec.ts`
- do:
```ts
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("FT-16.10 the runner switch starts off, in light and dark with AA contrast", async ({ page }) => {
  for (const mode of ["light", "dark"]) {
    await page.goto("/");
    await page.evaluate((m) => localStorage.setItem("limo-theme", m), mode);
    await page.reload();
    const runner = page.getByRole("button", { name: "Runner off" });
    await expect(runner).toBeEnabled();
    await expect(runner).toHaveAttribute("aria-pressed", "false");
    expect((await new AxeBuilder({ page }).withRules(["color-contrast"]).analyze()).violations).toEqual([]);
  }
});
```
- verify: `mise run test:e2e` → all pass

### STEP-12 Format and full gates
- file: none (format only)
- do: `mise run fmt` (if its ruff check step stops on E501, run `cd engine && uv run ruff format .` then fix the reported lines this ticket created)
- verify: `mise run gates` → all pass; `mise run test` → all suites pass

## Do not
- persist the switch (it must start off after every start)
- turn the runner on in e2e (the e2e engine is shared by all specs)
- start runs from the HTTP thread of `PUT /api/runner`; add packages; hard-code colors

## Doc updates
- context/api.md: Reference implementations — add `- runner switch: engine/limo/api/switch_routes.py (GET/PUT /api/runner {"enabled"}; in memory, off at start; loop in engine/limo/runner/loop.py)`
- context/INDEX.md: Shape `engine/limo/runner` line — add "`loop.py`: runner switch + loop thread (steps every feature while on, polls hosts every `host_poll_s`)"
- context/stack.md: none
- context/glossary.md: Runner switch code name `runner_enabled` → `RunnerLoop.enabled` (`/api/runner`)
- context/performance.md: none (polling 3 min already stated)
- adr: none
- adr/INDEX.md: none
