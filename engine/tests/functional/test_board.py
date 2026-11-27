from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from limo.common.constants import TICKET_STATUSES
from limo.config import Settings
from tests.builders import add_cart_project, set_status, write_workspace_file

BETA_MAP = (
    "feature: beta\ntickets:\n  - id: TKT-1\n    title: Beta works\n    scope: [api]\n"
    "    scenarios: [SC-1]\n    depends_on: []\n"
)


def _tickets(feature: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {t["id"]: t for t in feature["tickets"]}


def test_ft_13_1_board_groups_tickets_by_status_with_dependencies(
    client: TestClient, settings: Settings, tmp_path: Path
) -> None:
    """FT-13.1 board lists the feature's tickets with status and dependencies (SC-43)."""
    add_cart_project(client, tmp_path)
    set_status(settings, "shop", "TKT-1", "review")
    r = client.get("/api/projects/shop/board")
    assert r.status_code == 200
    body = r.json()
    assert body["project"] == "shop"
    assert body["statuses"] == list(TICKET_STATUSES)
    assert [f["name"] for f in body["features"]] == ["cart"]
    tickets = _tickets(body["features"][0])
    assert tickets["TKT-1"]["status"] == "review"
    assert tickets["TKT-1"]["title"] == "Cart shows a total"
    assert tickets["TKT-1"]["depends_on"] == []
    assert tickets["TKT-2"]["status"] == "todo"
    assert tickets["TKT-2"]["depends_on"] == ["TKT-1"]
    assert tickets["TKT-2"]["build_tries"] == 0
    assert tickets["TKT-2"]["plan_tries"] == 0


def test_ft_13_2_board_of_unknown_project_is_not_found(client: TestClient) -> None:
    """FT-13.2 board of an unknown project is 404 project_not_found."""
    r = client.get("/api/projects/nope/board")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "project_not_found"


def test_ft_13_3_invalid_map_is_map_invalid(client: TestClient, settings: Settings, tmp_path: Path) -> None:
    """FT-13.3 a feature whose map.yaml cannot be read makes the board 409 map_invalid."""
    add_cart_project(client, tmp_path)
    write_workspace_file(
        settings, "shop", "work/broken/map.yaml", "feature: broken\ntickets:\n  - id: TKT-1\n    bogus: x\n"
    )
    r = client.get("/api/projects/shop/board")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "map_invalid"


def test_ft_13_4_board_lists_only_features_with_a_map_sorted(
    client: TestClient, settings: Settings, tmp_path: Path
) -> None:
    """FT-13.4 features are the work/ directories holding a map.yaml, sorted by name (SC-43)."""
    add_cart_project(client, tmp_path)
    write_workspace_file(settings, "shop", "work/alpha/requirements/r.md", "x")
    write_workspace_file(settings, "shop", "work/beta/map.yaml", BETA_MAP)
    r = client.get("/api/projects/shop/board")
    assert r.status_code == 200
    features = r.json()["features"]
    assert [f["name"] for f in features] == ["beta", "cart"]
    assert features[0]["tickets"] == [
        {
            "id": "TKT-1",
            "title": "Beta works",
            "status": "todo",
            "depends_on": [],
            "build_tries": 0,
            "plan_tries": 0,
        }
    ]
