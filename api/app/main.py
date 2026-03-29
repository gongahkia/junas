from __future__ import annotations

from contextlib import asynccontextmanager
import json
import shutil
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .auth import generate_id, generate_session_token, hash_password, now_iso, verify_password
from .database import IMAGES_DIR, decode_json, get_connection, init_db, rows_to_dicts
from .detection import default_color_for_role, detect_board_holds
from .schemas import (
    AttemptRequest,
    ClimbQueryRequest,
    CreateClimbRequest,
    LoginRequest,
    RatingRequest,
    RegisterRequest,
    SessionResponse,
    SurfaceRequest,
    UpdateBoardHoldsRequest,
)


@asynccontextmanager
async def _lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Kilter Together Cornifer API",
    version="0.1.0",
    lifespan=_lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/media", StaticFiles(directory=IMAGES_DIR), name="media")


def _bearer_token(authorization: str | None = Header(default=None)) -> str:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authorization header.")
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token.")
    return authorization[len(prefix) :].strip()


def require_user(token: str = Depends(_bearer_token)) -> dict[str, str]:
    connection = get_connection()
    try:
        row = connection.execute(
            """
            SELECT users.id, users.username
            FROM sessions
            JOIN users ON users.id = sessions.user_id
            WHERE sessions.token = ?
            """,
            (token,),
        ).fetchone()
    finally:
        connection.close()

    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown session.")
    return {"id": row["id"], "username": row["username"], "token": token}


def _surface_response(id_value: str, kind: str, name: str, description: str | None = None, parent_id: str | None = None, meta: dict[str, str] | None = None) -> dict[str, object]:
    return {
        "id": id_value,
        "kind": kind,
        "name": name,
        "description": description,
        "parent_id": parent_id,
        "meta": meta or {},
    }


def _board_image_url(filename: str) -> str:
    return f"/media/{filename}"


def _board_holds(board_id: str) -> list[dict[str, object]]:
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT id, position, centroid_x, centroid_y, contour_json
            FROM board_holds
            WHERE board_id = ?
            ORDER BY position ASC
            """,
            (board_id,),
        ).fetchall()
    finally:
        connection.close()

    holds: list[dict[str, object]] = []
    for row in rows:
        holds.append(
            {
                "id": row["id"],
                "position": row["position"],
                "centroid_x": row["centroid_x"],
                "centroid_y": row["centroid_y"],
                "contour": decode_json(row["contour_json"], []),
            }
        )
    return holds


def _attempt_summary(climb_id: str) -> dict[str, int]:
    connection = get_connection()
    try:
        row = connection.execute(
            """
            SELECT COALESCE(SUM(tries), 0) AS total_tries, COUNT(*) AS entry_count
            FROM attempts
            WHERE climb_id = ?
            """,
            (climb_id,),
        ).fetchone()
    finally:
        connection.close()

    if row is None:
        return {"attempt_count": 0, "attempt_entries": 0}
    return {
        "attempt_count": int(row["total_tries"] or 0),
        "attempt_entries": int(row["entry_count"] or 0),
    }


def _climb_to_provider(climb_row: dict[str, object], board_row: dict[str, object], rating_summary: dict[str, int], selected_rating: int | None = None) -> dict[str, object]:
    connection = get_connection()
    try:
        hold_rows = rows_to_dicts(
            connection.execute(
                """
                SELECT climb_holds.role, climb_holds.color, board_holds.position, board_holds.centroid_x, board_holds.centroid_y
                FROM climb_holds
                JOIN board_holds ON board_holds.id = climb_holds.board_hold_id
                WHERE climb_holds.climb_id = ?
                ORDER BY board_holds.position ASC
                """,
                (climb_row["id"],),
            ).fetchall()
        )
    finally:
        connection.close()

    highlighted_holds = [
        {
            "position": int(row["position"]),
            "x": float(row["centroid_x"]),
            "y": float(row["centroid_y"]),
            "role": row["role"],
            "color": row["color"],
        }
        for row in hold_rows
    ]
    attempt_summary = _attempt_summary(str(climb_row["id"]))
    attempt_count = attempt_summary["attempt_count"]
    return {
        "id": climb_row["id"],
        "external_id": climb_row["id"],
        "provider_id": "cornifer",
        "surface_id": board_row["id"],
        "name": climb_row["name"],
        "description": climb_row["description"],
        "setter_name": board_row["creator_username"],
        "primary_grade": climb_row["grade"],
        "secondary_grade": None,
        "created_at": climb_row["created_at"],
        "popularity": rating_summary["upvotes"] - rating_summary["downvotes"] + attempt_count,
        "media": [
            {
                "url": _board_image_url(board_row["image_filename"]),
                "kind": "image",
            }
        ],
        "highlighted_holds": highlighted_holds,
        "meta": {
            "location": str(board_row["location"]),
            "board_name": str(board_row["name"]),
            "upvotes": str(rating_summary["upvotes"]),
            "downvotes": str(rating_summary["downvotes"]),
            "my_rating": str(selected_rating or 0),
            "attempt_count": str(attempt_count),
            "attempt_entries": str(attempt_summary["attempt_entries"]),
        },
    }


def _rating_summary(climb_id: str) -> dict[str, int]:
    connection = get_connection()
    try:
        rows = rows_to_dicts(
            connection.execute(
                """
                SELECT value, COUNT(*) AS count
                FROM ratings
                WHERE climb_id = ?
                GROUP BY value
                """,
                (climb_id,),
            ).fetchall()
        )
    finally:
        connection.close()

    summary = {"upvotes": 0, "downvotes": 0}
    for row in rows:
        if int(row["value"]) > 0:
            summary["upvotes"] = int(row["count"])
        elif int(row["value"]) < 0:
            summary["downvotes"] = int(row["count"])
    return summary


@app.get("/api/providers/capabilities")
def get_provider_capabilities() -> dict[str, object]:
    return {
        "providers": [
            {
                "id": "kilter",
                "label": "Kilter",
                "room_supported": True,
                "solo_supported": True,
                "surface_hierarchy": "board",
                "auth_fields": [],
                "features": ["offline_catalog", "room", "solo", "plans"],
            },
            {
                "id": "crux",
                "label": "Crux",
                "room_supported": True,
                "solo_supported": True,
                "surface_hierarchy": "hierarchy",
                "auth_fields": [],
                "features": ["room", "solo", "plans"],
            },
            {
                "id": "cornifer",
                "label": "Cornifer",
                "room_supported": True,
                "solo_supported": True,
                "surface_hierarchy": "hierarchy",
                "auth_fields": [],
                "features": [
                    "community_boards",
                    "community_climbs",
                    "attempts",
                    "ratings",
                    "hold_detection",
                    "room",
                    "solo",
                    "plans",
                ],
            },
        ]
    }


@app.post("/api/cornifer/auth/register", response_model=SessionResponse)
def register(request: RegisterRequest) -> SessionResponse:
    connection = get_connection()
    try:
        existing = connection.execute(
            "SELECT id FROM users WHERE username = ?",
            (request.username.strip().lower(),),
        ).fetchone()
        if existing is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists.")
        user_id = generate_id("user")
        token = generate_session_token()
        now = now_iso()
        connection.execute(
            "INSERT INTO users (id, username, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (user_id, request.username.strip().lower(), hash_password(request.password), now),
        )
        connection.execute(
            "INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)",
            (token, user_id, now),
        )
        connection.commit()
        return SessionResponse(token=token, username=request.username.strip().lower())
    finally:
        connection.close()


@app.post("/api/cornifer/auth/login", response_model=SessionResponse)
def login(request: LoginRequest) -> SessionResponse:
    connection = get_connection()
    try:
        row = connection.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (request.username.strip().lower(),),
        ).fetchone()
        if row is None or not verify_password(request.password, row["password_hash"]):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")
        token = generate_session_token()
        connection.execute(
            "INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)",
            (token, row["id"], now_iso()),
        )
        connection.commit()
        return SessionResponse(token=token, username=row["username"])
    finally:
        connection.close()


@app.post("/api/cornifer/auth/logout")
def logout(user: dict[str, str] = Depends(require_user)) -> dict[str, bool]:
    connection = get_connection()
    try:
        connection.execute("DELETE FROM sessions WHERE token = ?", (user["token"],))
        connection.commit()
        return {"ok": True}
    finally:
        connection.close()


@app.get("/api/cornifer/me")
def me(user: dict[str, str] = Depends(require_user)) -> dict[str, str]:
    return {"id": user["id"], "username": user["username"]}


@app.post("/api/cornifer/boards")
async def create_board(
    name: str = Form(...),
    location: str = Form(...),
    description: str = Form(""),
    image: UploadFile = File(...),
    user: dict[str, str] = Depends(require_user),
) -> dict[str, object]:
    board_id = generate_id("board")
    suffix = Path(image.filename or "board.jpg").suffix or ".jpg"
    filename = f"{board_id}{suffix}"
    target = IMAGES_DIR / filename
    with target.open("wb") as handle:
        shutil.copyfileobj(image.file, handle)

    connection = get_connection()
    try:
        connection.execute(
            """
            INSERT INTO boards (id, name, location, description, creator_id, image_filename, draft, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (board_id, name.strip(), location.strip(), description.strip(), user["id"], filename, now_iso()),
        )
        connection.commit()
    finally:
        connection.close()

    return {
        "board": {
            "id": board_id,
            "name": name.strip(),
            "location": location.strip(),
            "description": description.strip(),
            "image_url": _board_image_url(filename),
            "draft": True,
            "holds": [],
        }
    }


@app.post("/api/cornifer/boards/{board_id}/detect-holds")
def detect_holds(board_id: str, user: dict[str, str] = Depends(require_user)) -> dict[str, object]:
    connection = get_connection()
    try:
        board = connection.execute(
            """
            SELECT boards.id, boards.name, boards.location, boards.description, boards.image_filename
            FROM boards
            WHERE boards.id = ? AND boards.creator_id = ?
            """,
            (board_id, user["id"]),
        ).fetchone()
        if board is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found.")
        holds = detect_board_holds(IMAGES_DIR / board["image_filename"])
        connection.execute("DELETE FROM board_holds WHERE board_id = ?", (board_id,))
        for hold in holds:
            connection.execute(
                """
                INSERT INTO board_holds (id, board_id, position, centroid_x, centroid_y, contour_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    generate_id("hold"),
                    board_id,
                    int(hold["position"]),
                    float(hold["centroid_x"]),
                    float(hold["centroid_y"]),
                    json.dumps(hold["contour"]),
                    now_iso(),
                ),
            )
        connection.commit()
        saved_holds = _board_holds(board_id)
        return {
            "board": {
                "id": board["id"],
                "name": board["name"],
                "location": board["location"],
                "description": board["description"],
                "image_url": _board_image_url(board["image_filename"]),
                "draft": True,
                "holds": saved_holds,
            }
        }
    finally:
        connection.close()


@app.put("/api/cornifer/boards/{board_id}/holds")
def update_board_holds(
    board_id: str,
    request: UpdateBoardHoldsRequest,
    user: dict[str, str] = Depends(require_user),
) -> dict[str, object]:
    connection = get_connection()
    try:
        board = connection.execute(
            "SELECT id, image_filename, name, location, description FROM boards WHERE id = ? AND creator_id = ?",
            (board_id, user["id"]),
        ).fetchone()
        if board is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found.")
        connection.execute("DELETE FROM board_holds WHERE board_id = ?", (board_id,))
        for index, hold in enumerate(request.holds):
            connection.execute(
                """
                INSERT INTO board_holds (id, board_id, position, centroid_x, centroid_y, contour_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(hold.get("id") or generate_id("hold")),
                    board_id,
                    index,
                    float(hold.get("centroid_x") or 0.0),
                    float(hold.get("centroid_y") or 0.0),
                    json.dumps(hold.get("contour") or []),
                    now_iso(),
                ),
            )
        connection.execute(
            "UPDATE boards SET draft = ? WHERE id = ?",
            (0 if request.publish else 1, board_id),
        )
        connection.commit()
        return {
            "board": {
                "id": board["id"],
                "name": board["name"],
                "location": board["location"],
                "description": board["description"],
                "image_url": _board_image_url(board["image_filename"]),
                "draft": not request.publish,
                "holds": _board_holds(board_id),
            }
        }
    finally:
        connection.close()


@app.post("/api/cornifer/climbs")
def create_climb(
    request: CreateClimbRequest,
    user: dict[str, str] = Depends(require_user),
) -> dict[str, object]:
    connection = get_connection()
    try:
        board = connection.execute(
            """
            SELECT boards.id, boards.name, boards.location, boards.description, boards.image_filename,
                   boards.draft, users.username AS creator_username
            FROM boards
            JOIN users ON users.id = boards.creator_id
            WHERE boards.id = ?
            """,
            (request.board_id,),
        ).fetchone()
        if board is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found.")
        if int(board["draft"]) == 1:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Board holds must be confirmed before climbs can be created.")
        climb_id = generate_id("climb")
        connection.execute(
            """
            INSERT INTO climbs (id, board_id, creator_id, name, grade, description, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                climb_id,
                request.board_id,
                user["id"],
                request.name.strip(),
                request.grade.strip(),
                request.description.strip(),
                now_iso(),
            ),
        )
        for selection in request.holds:
            connection.execute(
                """
                INSERT INTO climb_holds (id, climb_id, board_hold_id, role, color)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    generate_id("climb_hold"),
                    climb_id,
                    selection.board_hold_id,
                    selection.role,
                    default_color_for_role(selection.role),
                ),
            )
        connection.commit()
        climb_row = dict(
            connection.execute("SELECT * FROM climbs WHERE id = ?", (climb_id,)).fetchone()
        )
        provider_climb = _climb_to_provider(climb_row, dict(board), _rating_summary(climb_id))
        return {"climb": provider_climb}
    finally:
        connection.close()


@app.post("/api/cornifer/climbs/{climb_id}/attempts")
def create_attempt(
    climb_id: str,
    request: AttemptRequest,
    user: dict[str, str] = Depends(require_user),
) -> dict[str, object]:
    connection = get_connection()
    try:
        exists = connection.execute("SELECT id FROM climbs WHERE id = ?", (climb_id,)).fetchone()
        if exists is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Climb not found.")
        connection.execute(
            "INSERT INTO attempts (id, climb_id, user_id, tries, created_at) VALUES (?, ?, ?, ?, ?)",
            (generate_id("attempt"), climb_id, user["id"], request.tries, now_iso()),
        )
        connection.commit()
        return _attempt_summary(climb_id)
    finally:
        connection.close()


@app.post("/api/cornifer/climbs/{climb_id}/rating")
def rate_climb(
    climb_id: str,
    request: RatingRequest,
    user: dict[str, str] = Depends(require_user),
) -> dict[str, object]:
    connection = get_connection()
    try:
        exists = connection.execute("SELECT id FROM climbs WHERE id = ?", (climb_id,)).fetchone()
        if exists is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Climb not found.")
        connection.execute(
            """
            INSERT INTO ratings (id, climb_id, user_id, value, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(climb_id, user_id)
            DO UPDATE SET value = excluded.value, created_at = excluded.created_at
            """,
            (generate_id("rating"), climb_id, user["id"], request.value, now_iso()),
        )
        connection.commit()
        return _rating_summary(climb_id)
    finally:
        connection.close()


@app.post("/api/solo/providers/cornifer/surfaces")
def list_surfaces(request: SurfaceRequest) -> dict[str, object]:
    connection = get_connection()
    try:
        if request.parent_id:
            rows = rows_to_dicts(
                connection.execute(
                    """
                    SELECT id, name, location, description
                    FROM boards
                    WHERE location = ? AND draft = 0
                    ORDER BY name ASC
                    """,
                    (request.parent_id,),
                ).fetchall()
            )
            return {
                "surfaces": [
                    _surface_response(
                        row["id"],
                        "board",
                        row["name"],
                        row["description"],
                        parent_id=row["location"],
                        meta={"location": row["location"], "board_id": row["id"]},
                    )
                    for row in rows
                ]
            }

        rows = rows_to_dicts(
            connection.execute(
                """
                SELECT DISTINCT location
                FROM boards
                WHERE draft = 0
                ORDER BY location ASC
                """
            ).fetchall()
        )
        return {
            "surfaces": [
                _surface_response(row["location"], "location", row["location"])
                for row in rows
            ]
        }
    finally:
        connection.close()


@app.post("/api/solo/providers/cornifer/climbs")
def list_climbs(request: ClimbQueryRequest) -> dict[str, object]:
    connection = get_connection()
    try:
        conditions = ["boards.draft = 0"]
        params: list[object] = []
        if request.surface_id:
            conditions.append("(boards.id = ? OR boards.location = ?)")
            params.extend([request.surface_id, request.surface_id])
        query = (request.q or "").strip().lower()
        if query:
            conditions.append("(LOWER(climbs.name) LIKE ? OR LOWER(climbs.description) LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%"])
        if request.grade_min:
            conditions.append("LOWER(climbs.grade) >= ?")
            params.append(request.grade_min.lower())
        if request.grade_max:
            conditions.append("LOWER(climbs.grade) <= ?")
            params.append(request.grade_max.lower())

        order_by = "climbs.created_at DESC"
        if (request.sort or "popular") == "popular":
            order_by = "(SELECT COUNT(*) FROM ratings WHERE ratings.climb_id = climbs.id AND ratings.value = 1) DESC, climbs.created_at DESC"

        rows = rows_to_dicts(
            connection.execute(
                f"""
                SELECT climbs.*, boards.name AS board_name, boards.location, boards.description AS board_description,
                       boards.image_filename, users.username AS creator_username, boards.id AS board_id
                FROM climbs
                JOIN boards ON boards.id = climbs.board_id
                JOIN users ON users.id = boards.creator_id
                WHERE {" AND ".join(conditions)}
                ORDER BY {order_by}
                LIMIT ?
                """,
                (*params, request.page_size + 1),
            ).fetchall()
        )
        visible = rows[: request.page_size]
        climbs = [
            _climb_to_provider(row, row, _rating_summary(str(row["id"])))
            for row in visible
        ]
        return {
            "climbs": climbs,
            "has_more": len(rows) > request.page_size,
            "page_size": request.page_size,
        }
    finally:
        connection.close()


@app.post("/api/solo/providers/cornifer/climbs/{climb_id}")
def get_climb_detail(climb_id: str, request: ClimbQueryRequest) -> dict[str, object]:
    connection = get_connection()
    try:
        row = connection.execute(
            """
            SELECT climbs.*, boards.name AS board_name, boards.location, boards.description AS board_description,
                   boards.image_filename, users.username AS creator_username, boards.id AS board_id
            FROM climbs
            JOIN boards ON boards.id = climbs.board_id
            JOIN users ON users.id = boards.creator_id
            WHERE climbs.id = ? AND boards.draft = 0
            """,
            (climb_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Climb not found.")
        return {"climb": _climb_to_provider(dict(row), dict(row), _rating_summary(climb_id))}
    finally:
        connection.close()
