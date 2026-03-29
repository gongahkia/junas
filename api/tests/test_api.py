from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")

from app.database import DATA_DIR, DB_PATH
from app.main import app


def _make_board_image() -> bytes:
    image = np.full((220, 220, 3), 255, dtype=np.uint8)
    cv2.circle(image, (60, 60), 18, (0, 0, 0), -1)
    cv2.circle(image, (150, 70), 18, (0, 0, 0), -1)
    cv2.circle(image, (80, 150), 18, (0, 0, 0), -1)
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    return encoded.tobytes()


def _auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/cornifer/auth/register",
        json={"username": "tester", "password": "secret123"},
    )
    response.raise_for_status()
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def setup_function() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()
    images_dir = DATA_DIR / "images"
    if images_dir.exists():
        for child in images_dir.iterdir():
            if child.name != ".gitkeep":
                child.unlink()


def test_cornifer_flow() -> None:
    client = TestClient(app)
    headers = _auth_headers(client)

    board_response = client.post(
        "/api/cornifer/boards",
        headers=headers,
        data={"name": "Main Board", "location": "Test Gym", "description": "Steep wall"},
        files={"image": ("board.png", BytesIO(_make_board_image()), "image/png")},
    )
    assert board_response.status_code == 200
    board = board_response.json()["board"]
    assert board["draft"] is True

    detected_response = client.post(
        f"/api/cornifer/boards/{board['id']}/detect-holds",
        headers=headers,
    )
    assert detected_response.status_code == 200
    detected = detected_response.json()["board"]
    assert len(detected["holds"]) >= 3

    confirm_response = client.put(
        f"/api/cornifer/boards/{board['id']}/holds",
        headers=headers,
        json={"holds": detected["holds"], "publish": False},
    )
    assert confirm_response.status_code == 200
    reviewed_board = confirm_response.json()["board"]
    assert reviewed_board["draft"] is True

    publish_response = client.put(
        f"/api/cornifer/boards/{board['id']}/holds",
        headers=headers,
        json={"holds": reviewed_board["holds"], "publish": True},
    )
    assert publish_response.status_code == 200
    confirmed_board = publish_response.json()["board"]
    assert confirmed_board["draft"] is False

    surfaces = client.post("/api/solo/providers/cornifer/surfaces", json={})
    assert surfaces.status_code == 200
    assert surfaces.json()["surfaces"][0]["id"] == "Test Gym"

    child_surfaces = client.post(
        "/api/solo/providers/cornifer/surfaces",
        json={"parent_id": "Test Gym"},
    )
    assert child_surfaces.status_code == 200
    board_surface = child_surfaces.json()["surfaces"][0]
    assert board_surface["kind"] == "board"

    holds = confirmed_board["holds"][:2]
    climb_response = client.post(
        "/api/cornifer/climbs",
        headers=headers,
        json={
            "board_id": board["id"],
            "name": "Warmup",
            "grade": "V2",
            "description": "Two move opener",
            "holds": [
                {"board_hold_id": holds[0]["id"], "role": "start"},
                {"board_hold_id": holds[1]["id"], "role": "end"},
            ],
        },
    )
    assert climb_response.status_code == 200
    climb = climb_response.json()["climb"]
    assert climb["provider_id"] == "cornifer"
    assert len(climb["highlighted_holds"]) == 2

    list_response = client.post(
        "/api/solo/providers/cornifer/climbs",
        json={"surface_id": board["id"]},
    )
    assert list_response.status_code == 200
    assert list_response.json()["climbs"][0]["id"] == climb["id"]

    location_list_response = client.post(
        "/api/solo/providers/cornifer/climbs",
        json={"surface_id": "Test Gym"},
    )
    assert location_list_response.status_code == 200
    assert location_list_response.json()["climbs"][0]["id"] == climb["id"]

    detail_response = client.post(
        f"/api/solo/providers/cornifer/climbs/{climb['id']}",
        json={},
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["climb"]["name"] == "Warmup"

    attempt_response = client.post(
        f"/api/cornifer/climbs/{climb['id']}/attempts",
        headers=headers,
        json={"tries": 3},
    )
    assert attempt_response.status_code == 200
    assert attempt_response.json()["attempt_count"] == 3
    assert attempt_response.json()["attempt_entries"] == 1

    rating_response = client.post(
        f"/api/cornifer/climbs/{climb['id']}/rating",
        headers=headers,
        json={"value": 1},
    )
    assert rating_response.status_code == 200
    assert rating_response.json()["upvotes"] == 1
