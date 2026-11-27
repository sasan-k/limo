import shutil
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from limo.app import Deps, create_app
from limo.config import Settings
from limo.executor.local import LocalExecutor
from tests.builders import add_cart_project, make_skills_repo, next_event, start_and_wait
from tests.fakes.host import FakeHost
from tests.fakes.llm import FakeLlm

FILE = "/api/agents/build/file?path=SKILL.md"
HISTORY = "/api/agents/build/history?path=SKILL.md"
ROLLBACK = "/api/agents/build/rollback?path=SKILL.md"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path / "data",
        skills_dir=make_skills_repo(tmp_path),
        anthropic_api_key="sk-canary-123",
        sse_heartbeat_s=0.2,
        _env_file=None,
    )


def _save(client: TestClient, content: str, base: str | None = None) -> httpx.Response:
    body: dict[str, str] = {"content": content}
    if base is not None:
        body["base_version"] = base
    return client.put(FILE, json=body)


def test_ft_14_1_save_commits_version_and_next_run_uses_it(
    client: TestClient, llm: FakeLlm, tmp_path: Path
) -> None:
    """FT-14.1 a saved prompt becomes a new version that the next run uses (SC-46)."""
    add_cart_project(client, tmp_path)
    f = client.get(FILE).json()
    h0 = len(client.get(HISTORY).json())
    r = client.put(
        FILE,
        json={"content": f["content"] + "Always run the formatter last.\n", "base_version": f["version"]},
    )
    assert r.status_code == 200
    saved = r.json()
    assert saved["version"] != f["version"]
    history = client.get(HISTORY).json()
    assert len(history) == h0 + 1
    assert history[0]["version"] == saved["version"]
    assert history[0]["message"] == "prompt: build SKILL.md"
    start_and_wait(client, "build")
    assert "Always run the formatter last." in llm.requests[-1].system


def test_ft_14_2_reference_file_is_listed_and_saved(client: TestClient, tmp_path: Path) -> None:
    """FT-14.2 a reference template is listed and saves as a new version (SC-47)."""
    add_cart_project(client, tmp_path)
    files = client.get("/api/agents/build/files").json()
    assert files[0] == "SKILL.md"
    assert "templates/build-report.md" in files
    ref = "/api/agents/build/file?path=templates/build-report.md"
    ref_history = "/api/agents/build/history?path=templates/build-report.md"
    f = client.get(ref).json()
    h0 = len(client.get(ref_history).json())
    r = client.put(
        ref, json={"content": f["content"] + "- duration: <minutes>\n", "base_version": f["version"]}
    )
    assert r.status_code == 200
    assert len(client.get(ref_history).json()) == h0 + 1
    assert "- duration: <minutes>" in client.get(ref).json()["content"]


def test_ft_14_3_rollback_restores_older_version_as_new_commit(client: TestClient, tmp_path: Path) -> None:
    """FT-14.3 rollback restores an older version as a new commit on top (SC-48)."""
    add_cart_project(client, tmp_path)
    f0 = client.get(FILE).json()
    content0 = f0["content"]
    va = _save(client, content0 + "A\n", f0["version"]).json()["version"]
    vb = _save(client, content0 + "B\n", va).json()["version"]
    r = client.post(ROLLBACK, json={"version": va})
    assert r.status_code == 200
    body = r.json()
    assert body["content"] == content0 + "A\n"
    assert body["version"] not in (va, vb)
    history = client.get(HISTORY).json()
    assert history[0]["version"] == body["version"]
    assert history[1]["version"] == vb
    assert history[0]["message"].startswith("prompt: rollback build SKILL.md to ")
    assert all(h["saved_at"].endswith("+00:00") for h in history)


def test_ft_14_4_invalid_path_body_or_version_is_422(client: TestClient, tmp_path: Path) -> None:
    """FT-14.4 invalid paths, bodies and versions are rejected with 422 validation_error."""
    add_cart_project(client, tmp_path)
    responses = [
        client.get("/api/agents/build/file", params={"path": p})
        for p in ("../SKILL.md", "templates/../x.md", "notes.md")
    ]
    responses.append(_save(client, "x" * 262145))
    responses.append(client.put(FILE, json={"content": "x", "extra": 1}))
    responses.append(client.post(ROLLBACK, json={"version": "abc"}))
    for r in responses:
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "validation_error"


def test_ft_14_5_unknown_agent_file_or_version_is_404(client: TestClient, tmp_path: Path) -> None:
    """FT-14.5 unknown agent, file and version are 404 with their codes."""
    add_cart_project(client, tmp_path)
    r = client.get("/api/agents/deploy/file?path=SKILL.md")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "agent_not_found"
    r = client.put("/api/agents/build/file?path=templates/nope.md", json={"content": "x"})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "file_not_found"
    r = client.post(ROLLBACK, json={"version": "0" * 40})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "version_not_found"


def test_ft_14_6_stale_base_version_is_409_and_file_unchanged(client: TestClient, tmp_path: Path) -> None:
    """FT-14.6 a save against a stale base version is a 409 and leaves the file unchanged (OP-1 conflict)."""
    add_cart_project(client, tmp_path)
    v0 = client.get(FILE).json()["version"]
    assert _save(client, "X\n", v0).status_code == 200
    r = _save(client, "Y\n", v0)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "version_conflict"
    assert client.get(FILE).json()["content"] == "X\n"


def test_ft_14_7_same_content_or_same_version_makes_no_commit(client: TestClient, tmp_path: Path) -> None:
    """FT-14.7 saving unchanged content or rolling back to the current version adds no version."""
    add_cart_project(client, tmp_path)
    f = client.get(FILE).json()
    h0 = len(client.get(HISTORY).json())
    r = _save(client, f["content"], f["version"])
    assert r.status_code == 200
    assert r.json()["version"] == f["version"]
    r = client.post(ROLLBACK, json={"version": f["version"]})
    assert r.status_code == 200
    assert r.json()["version"] == f["version"]
    assert len(client.get(HISTORY).json()) == h0


def test_ft_14_8_content_at_size_limit_is_accepted(client: TestClient, tmp_path: Path) -> None:
    """FT-14.8 content of exactly 262144 characters is accepted."""
    add_cart_project(client, tmp_path)
    assert _save(client, "x" * 262143 + "\n").status_code == 200
    assert len(client.get(FILE).json()["content"]) == 262144


def test_ft_14_9_save_publishes_prompt_saved_event(client: TestClient, tmp_path: Path) -> None:
    """FT-14.9 a save publishes prompt.saved with the agent, path and new version (NFR-9)."""
    add_cart_project(client, tmp_path)
    f = client.get(FILE).json()
    with client.stream("GET", "/api/events") as r:
        lines = r.iter_lines()
        assert next(lines) == ": connected"
        saved = _save(client, f["content"] + "Added line.\n", f["version"]).json()
        ev = next_event(lines, "prompt.saved")
    assert ev["project_id"] is None
    assert ev["payload"] == {"agent": "build", "path": "SKILL.md", "version": saved["version"]}


def test_ft_14_10_without_git_repo_prompt_routes_return_git_failed(
    settings: Settings, tmp_path: Path
) -> None:
    """FT-14.10 prompt history, save and rollback return 409 git_failed when skills/ is not a git repo."""
    plain = tmp_path / "plain" / "skills"
    shutil.copytree(Settings(_env_file=None).skills_dir, plain)
    plain_settings = Settings(data_dir=tmp_path / "data2", skills_dir=plain, _env_file=None)
    deps = Deps(
        executor=LocalExecutor(path_prefix=settings.scripts_dir),
        llm=FakeLlm(),
        host=FakeHost(),
    )
    before = (plain / "build" / "SKILL.md").read_text()
    with TestClient(create_app(plain_settings, deps)) as c:
        r = c.get(HISTORY)
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "git_failed"
        r = c.put(FILE, json={"content": "x"})
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "git_failed"
        r = c.post(ROLLBACK, json={"version": "a" * 40})
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "git_failed"
    assert (plain / "build" / "SKILL.md").read_text() == before
