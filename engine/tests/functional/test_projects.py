from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from limo.config import Settings
from tests.builders import make_empty_bare_repo, make_git_repo


def _body(name: str, git_url: str, host: str = "github") -> dict[str, object]:
    return {"name": name, "git_url": git_url, "host": host}


def test_ft_1_1_add_project_and_list(client: TestClient, settings: Settings, tmp_path: Path) -> None:
    """FT-1.1 add a project from a git URL, then list it."""
    url = make_git_repo(tmp_path, "shop", {"README.md": "# shop\n"})
    r = client.post("/api/projects", json=_body("shop", url))
    assert r.status_code == 201
    assert r.json()["status"] == "ready"
    assert r.json()["default_branch"] == "main"
    listed = client.get("/api/projects").json()
    assert [p["name"] for p in listed] == ["shop"]
    assert (Path(r.json()["workspace"]) / "README.md").exists()


def test_ft_1_2_invalid_name(client: TestClient, tmp_path: Path) -> None:
    """FT-1.2 a project name with invalid characters is rejected."""
    url = make_git_repo(tmp_path, "shop", {"README.md": "# shop\n"})
    r = client.post("/api/projects", json=_body("Shop!", url))
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"
    assert client.get("/api/projects").json() == []


@pytest.mark.parametrize("git_url", ["-uhttps://x", "ftp://x/y", ""])
def test_ft_1_3_invalid_git_url(client: TestClient, git_url: str) -> None:
    """FT-1.3 a git URL outside the allowed forms is rejected."""
    r = client.post("/api/projects", json=_body("shop", git_url))
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


@pytest.mark.parametrize("override", [{"host": "bitbucket"}, {"token": "x"}])
def test_ft_1_4_invalid_host_or_extra_field(
    client: TestClient, tmp_path: Path, override: dict[str, str]
) -> None:
    """FT-1.4 an unknown host or an unknown extra field is rejected."""
    url = make_git_repo(tmp_path, "shop", {"README.md": "# shop\n"})
    r = client.post("/api/projects", json={**_body("shop", url), **override})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_ft_1_5_duplicate_name_conflicts(client: TestClient, tmp_path: Path) -> None:
    """FT-1.5 adding a project with an existing name is a conflict."""
    url = make_git_repo(tmp_path, "shop", {"README.md": "# shop\n"})
    assert client.post("/api/projects", json=_body("shop", url)).status_code == 201
    r = client.post("/api/projects", json=_body("shop", url))
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "project_exists"
    listed = client.get("/api/projects").json()
    assert [p["name"] for p in listed] == ["shop"]


def test_ft_1_6_name_length_boundary(client: TestClient, tmp_path: Path) -> None:
    """FT-1.6 a 40-character name is accepted and a 41-character name is rejected."""
    url = make_git_repo(tmp_path, "shop", {"README.md": "# shop\n"})
    assert client.post("/api/projects", json=_body("a" * 40, url)).status_code == 201
    assert client.post("/api/projects", json=_body("a" * 41, url)).status_code == 422


def test_ft_1_7_clone_failure(client: TestClient, settings: Settings, tmp_path: Path) -> None:
    """FT-1.7 a clone that fails returns 502 and leaves no project or workspace behind."""
    missing = (tmp_path / "missing.git").as_uri()
    r = client.post("/api/projects", json=_body("shop", missing))
    assert r.status_code == 502
    assert r.json()["error"]["code"] == "clone_failed"
    assert client.get("/api/projects").json() == []
    assert not (settings.workspaces_dir / "shop").exists()


def test_ft_1_8_empty_list_on_fresh_app(client: TestClient) -> None:
    """FT-1.8 listing projects on a fresh app returns an empty list."""
    r = client.get("/api/projects")
    assert r.status_code == 200
    assert r.json() == []


def test_ft_1_11_empty_repo_clone_fails(client: TestClient, settings: Settings, tmp_path: Path) -> None:
    """FT-1.11 cloning a repository with no commits returns 502 and leaves no project or workspace behind."""
    url = make_empty_bare_repo(tmp_path, "empty")
    r = client.post("/api/projects", json=_body("empty", url))
    assert r.status_code == 502
    assert r.json()["error"]["code"] == "clone_failed"
    assert client.get("/api/projects").json() == []
    assert not (settings.workspaces_dir / "empty").exists()
